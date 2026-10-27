"""The result store: Parquet tables and a run record under ``results/<config hash>/``.

One directory per run, named by the first 16 hex digits of the config hash:

- ``predictions.parquet``: one row per (config hash, series, policy, selector, delay, budget,
  variant, model, ratio, seed, window, slot, row id) with the true label, the probability
  (float32) and the 0/1 decision. This is the raw output every table is regenerated from.
- ``slots.parquet``: one row per (config hash, ..., window, slot): confusion counts, F1, FPR,
  FNR, achieved ratio, C3 status and (simulation) budget and pool counts.
- ``windows.parquet``: one row per (config hash, ..., window): AUT, fit time, random-split F1.
- ``run.json``: config, config hash, code version, lock hash, package versions, seeds,
  machine, source provenance and ``predictions_sha256``.

``predictions_sha256`` covers the predictions only (not the code version), so a rerun on a
later commit can still be compared with an earlier run. ``results/`` is never committed.

Checkpoints (resume): the runner works in *units* (one window of one seed of one variant). A
finished unit is written to ``units/`` and marked done last, so a killed run leaves only
whole units. ``ResultStore(..., resume=True)`` restores them; ``finalize`` merges the units in
the order they were visited, so a resumed run writes the same tables as an uninterrupted one
and no row is duplicated. The merged tables replace the checkpoints.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

PREDICTION_SCHEMA = pa.schema(
    [
        ("config_hash", pa.string()),
        ("series", pa.string()),
        ("policy", pa.string()),
        ("selector", pa.string()),
        ("delay", pa.int32()),
        ("budget_pct", pa.float64()),
        ("variant", pa.string()),
        ("model", pa.string()),
        ("ratio", pa.float64()),
        ("seed", pa.int32()),
        ("window_id", pa.string()),
        ("slot_id", pa.string()),
        ("row_id", pa.int64()),
        ("y_true", pa.int8()),
        ("proba", pa.float32()),
        ("pred", pa.int8()),
    ]
)
KEY_COLUMNS = ("variant", "model", "ratio", "seed", "window_id", "slot_id")
# What kind of series a row belongs to and under which simulator settings. Baseline (E0) rows
# are time-aware, never retrained, and have no selector, delay or budget.
ARM_DEFAULTS: dict[str, Any] = {
    "series": "time_aware",
    "policy": "never",
    "selector": None,
    "delay": None,
    "budget_pct": None,
}
ARM_COLUMNS = tuple(ARM_DEFAULTS)
_TABLES = (
    "predictions.parquet",
    "slots.parquet",
    "windows.parquet",
    "run.json",
    "run_failed.json",  # an overwritten run must not keep an earlier failure beside it
)
_UNITS = "units"


class PredictionHasher:
    """SHA-256 over predictions in the order they are written (order is part of the value)."""

    def __init__(self) -> None:
        self._h = hashlib.sha256()
        self.n_rows = 0

    def update(
        self,
        cell: str,
        window_id: str,
        slot_id: str,
        row_id: np.ndarray,
        pred: np.ndarray,
        proba: np.ndarray,
    ) -> None:
        for part in (cell, window_id, slot_id):
            self._h.update(part.encode("utf-8") + b"\x00")
        self._h.update(np.ascontiguousarray(row_id, dtype=np.int64).tobytes())
        self._h.update(np.ascontiguousarray(pred, dtype=np.int8).tobytes())
        self._h.update(np.ascontiguousarray(proba, dtype=np.float32).tobytes())
        self.n_rows += int(len(row_id))

    def hexdigest(self) -> str:
        return self._h.hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    return str(value)


@dataclass(frozen=True, eq=False)
class Block:
    """A run of consecutive prediction rows that share one key (one ``write`` call)."""

    key: dict[str, Any]
    row_id: np.ndarray
    y_true: np.ndarray
    proba: np.ndarray
    pred: np.ndarray


def iter_blocks(
    table: pa.Table, columns: tuple[str, ...] = (*ARM_COLUMNS, *KEY_COLUMNS)
) -> Iterator[Block]:
    """Split a predictions table back into the contiguous blocks it was written in."""
    n = table.num_rows
    if n == 0:
        return
    cols = [c for c in columns if c in table.column_names]
    keys = table.select(cols).to_pandas()
    # missing values compare unequal to themselves; spell them out so a run of nulls is one run
    as_text = keys.astype(object).where(keys.notna(), "<null>").astype(str)
    change = np.array((as_text != as_text.shift()).any(axis=1).to_numpy(), dtype=bool)
    change[0] = True
    starts = np.flatnonzero(change)
    stops = np.append(starts[1:], n)
    row_id = table.column("row_id").to_numpy()
    y_true = table.column("y_true").to_numpy() if "y_true" in table.column_names else None
    proba = table.column("proba").to_numpy()
    pred = table.column("pred").to_numpy()
    for a, b in zip(starts, stops, strict=True):
        first = keys.iloc[int(a)].to_dict()
        yield Block(
            {k: (None if pd.isna(v) else v) for k, v in first.items()},
            row_id[a:b],
            None if y_true is None else y_true[a:b],
            proba[a:b],
            pred[a:b],
        )


class _Unit:
    def __init__(self, unit_id: str | None) -> None:
        self.id = unit_id
        self.tables: list[pa.Table] = []
        self.slots: list[dict[str, Any]] = []
        self.windows: list[dict[str, Any]] = []
        self.restored = False


class ResultStore:
    def __init__(
        self,
        root: Path | str,
        config_hash: str,
        overwrite: bool = False,
        resume: bool = False,
    ) -> None:
        self.config_hash = config_hash
        self.dir = Path(root) / config_hash[:16]
        if (self.dir / "run.json").exists() and not overwrite:
            raise FileExistsError(
                f"{self.dir} already holds a finished run; rerun with overwrite to replace it"
            )
        self._units_dir = self.dir / _UNITS
        self._done: dict[str, Path] = {}
        if resume:
            self.dir.mkdir(parents=True, exist_ok=True)
            self._keep_failure_record()
            self._scan_done()
        else:
            for name in _TABLES:  # leftovers of a failed or replaced run
                (self.dir / name).unlink(missing_ok=True)
            shutil.rmtree(self._units_dir, ignore_errors=True)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._default = _Unit(None)
        self._current = self._default
        self._order: list[tuple[str, Path | None, _Unit | None]] = []
        self._visited: set[str] = set()

    # -- checkpoints -------------------------------------------------------------------------

    def _keep_failure_record(self) -> None:
        failed = self.dir / "run_failed.json"
        if not failed.exists():
            return
        n = 1
        while (self.dir / f"run_failed.{n}.json").exists():
            n += 1
        failed.rename(self.dir / f"run_failed.{n}.json")

    def _scan_done(self) -> None:
        if not self._units_dir.exists():
            return
        for marker in sorted(self._units_dir.glob("*.done")):
            meta = json.loads(marker.read_text(encoding="utf-8"))
            self._done[meta["unit_id"]] = marker.with_suffix("")

    @staticmethod
    def _stem(unit_id: str) -> str:
        return hashlib.sha256(unit_id.encode("utf-8")).hexdigest()[:20]

    def begin_unit(self, unit_id: str) -> bool:
        """Open a unit. True means a finished copy was restored: skip the computation."""
        if self._current is not self._default:
            raise ValueError(f"unit {self._current.id!r} is still open; end it first")
        if unit_id in self._visited:
            raise ValueError(f"unit {unit_id!r} was already started in this run")
        self._visited.add(unit_id)
        unit = _Unit(unit_id)
        stem = self._done.get(unit_id)
        if stem is not None:
            unit.tables = [pq.read_table(stem.with_suffix(".pred.parquet"))]
            unit.slots = json.loads(stem.with_suffix(".slots.json").read_text(encoding="utf-8"))
            unit.windows = json.loads(stem.with_suffix(".windows.json").read_text(encoding="utf-8"))
            unit.restored = True
        self._current = unit
        return unit.restored

    @property
    def unit_n_slots(self) -> int:
        return len(self._current.slots)

    @property
    def unit_n_windows(self) -> int:
        return len(self._current.windows)

    def unit_blocks(self) -> Iterator[Block]:
        """The restored unit's predictions, in the blocks they were written in."""
        for table in self._current.tables:
            yield from iter_blocks(table)

    def end_unit(self) -> None:
        unit = self._current
        if unit is self._default:
            raise ValueError("no unit is open")
        if unit.restored:
            self._order.append((unit.id or "", self._done[unit.id or ""], None))
        else:
            self._units_dir.mkdir(parents=True, exist_ok=True)
            stem = self._units_dir / self._stem(unit.id or "")
            table = (
                pa.concat_tables(unit.tables) if unit.tables else PREDICTION_SCHEMA.empty_table()
            )
            self._atomic(
                stem.with_suffix(".pred.parquet"),
                lambda p: pq.write_table(table, p, compression="zstd"),
            )
            for suffix, rows in ((".slots.json", unit.slots), (".windows.json", unit.windows)):
                self._atomic(
                    stem.with_suffix(suffix),
                    lambda p, rows=rows: p.write_text(
                        json.dumps(rows, default=_jsonable), encoding="utf-8"
                    ),
                )
            marker = {"unit_id": unit.id, "n_rows": table.num_rows}
            self._atomic(
                stem.with_suffix(".done"),
                lambda p: p.write_text(json.dumps(marker), encoding="utf-8"),
            )
            self._order.append((unit.id or "", stem, None))
        self._current = self._default

    @staticmethod
    def _atomic(path: Path, writer: Callable[[Path], None]) -> None:
        tmp = path.with_name(path.name + ".tmp")
        writer(tmp)
        tmp.replace(path)

    # -- writing -----------------------------------------------------------------------------

    @contextmanager
    def predictions(self) -> Iterator[Callable[..., None]]:
        """A writer for the open unit's predictions (rows are appended one slot at a time)."""

        def write(
            key: dict[str, Any],
            *,
            row_id: np.ndarray,
            y_true: np.ndarray,
            proba: np.ndarray,
            pred: np.ndarray,
        ) -> None:
            n = int(len(row_id))
            columns: dict[str, Any] = {"config_hash": pa.array([self.config_hash] * n)}
            for name in ARM_COLUMNS:
                value = key.get(name, ARM_DEFAULTS[name])
                columns[name] = pa.array([value] * n, type=PREDICTION_SCHEMA.field(name).type)
            for name in KEY_COLUMNS:
                columns[name] = pa.array([key[name]] * n)
            columns["row_id"] = pa.array(np.asarray(row_id, dtype=np.int64))
            columns["y_true"] = pa.array(np.asarray(y_true, dtype=np.int8))
            columns["proba"] = pa.array(np.asarray(proba, dtype=np.float32))
            columns["pred"] = pa.array(np.asarray(pred, dtype=np.int8))
            self._current.tables.append(pa.table(columns, schema=PREDICTION_SCHEMA))

        yield write

    def add_slot(self, row: dict[str, Any]) -> None:
        self._current.slots.append({"config_hash": self.config_hash, **row})

    def add_window(self, row: dict[str, Any]) -> None:
        self._current.windows.append({"config_hash": self.config_hash, **row})

    # -- finishing ---------------------------------------------------------------------------

    def finalize(self, record: dict[str, Any]) -> Path:
        if self._current is not self._default:
            raise ValueError(f"unit {self._current.id!r} is still open")
        slots: list[dict[str, Any]] = []
        windows: list[dict[str, Any]] = []
        writer = pq.ParquetWriter(
            self.dir / "predictions.parquet", PREDICTION_SCHEMA, compression="zstd"
        )
        try:
            for _, stem, _ in self._order:
                assert stem is not None
                writer.write_table(
                    pq.read_table(stem.with_suffix(".pred.parquet")).cast(PREDICTION_SCHEMA)
                )
                slots += json.loads(stem.with_suffix(".slots.json").read_text(encoding="utf-8"))
                windows += json.loads(stem.with_suffix(".windows.json").read_text(encoding="utf-8"))
            for table in self._default.tables:
                writer.write_table(table)
            slots += self._default.slots
            windows += self._default.windows
        finally:
            writer.close()
        pd.DataFrame(slots).to_parquet(self.dir / "slots.parquet", index=False)
        pd.DataFrame(windows).to_parquet(self.dir / "windows.parquet", index=False)
        body = {"status": "complete", **record}
        text = json.dumps(body, indent=2, sort_keys=True, default=_jsonable) + "\n"
        (self.dir / "run.json").write_text(text, encoding="utf-8")
        shutil.rmtree(self._units_dir, ignore_errors=True)
        return self.dir

    def fail(self, reason: dict[str, Any]) -> Path:
        """Record why a run stopped; the failure is kept, never silently rerun."""
        path = self.dir / "run_failed.json"
        body = {"status": "failed", "config_hash": self.config_hash, **reason}
        path.write_text(json.dumps(body, indent=2, default=_jsonable) + "\n", encoding="utf-8")
        return path
