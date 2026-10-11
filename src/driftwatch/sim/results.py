"""The result store: Parquet tables and a run record under ``results/<config hash>/``.

One directory per run, named by the first 16 hex digits of the config hash:

- ``predictions.parquet``: one row per (config hash, variant, model, ratio, seed, window,
  slot, row id) with the true label, the probability (float32) and the 0/1 decision. This is
  the raw output every table is regenerated from.
- ``slots.parquet``: one row per (config hash, variant, model, ratio, seed, window, slot):
  confusion counts, F1, FPR, FNR, achieved ratio and C3 status.
- ``windows.parquet``: one row per (config hash, variant, model, ratio, seed, window): AUT,
  fit time, random-split F1 and counts.
- ``run.json``: config, config hash, code version, lock hash, package versions, seeds,
  machine, source provenance and ``predictions_sha256``.

``predictions_sha256`` covers the predictions only (not the code version), so a rerun on a
later commit can still be compared with an earlier run. ``results/`` is never committed.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

PREDICTION_SCHEMA = pa.schema(
    [
        ("config_hash", pa.string()),
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
_TABLES = (
    "predictions.parquet",
    "slots.parquet",
    "windows.parquet",
    "run.json",
    "run_failed.json",  # an overwritten run must not keep an earlier failure beside it
)


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


class ResultStore:
    def __init__(self, root: Path | str, config_hash: str, overwrite: bool = False) -> None:
        self.config_hash = config_hash
        self.dir = Path(root) / config_hash[:16]
        if (self.dir / "run.json").exists() and not overwrite:
            raise FileExistsError(
                f"{self.dir} already holds a finished run; rerun with overwrite to replace it"
            )
        for name in _TABLES:  # leftovers of a failed or replaced run
            (self.dir / name).unlink(missing_ok=True)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._slots: list[dict[str, Any]] = []
        self._windows: list[dict[str, Any]] = []

    @contextmanager
    def predictions(self) -> Iterator[Callable[..., None]]:
        """A writer for ``predictions.parquet``; rows are appended one slot at a time."""
        writer = pq.ParquetWriter(
            self.dir / "predictions.parquet", PREDICTION_SCHEMA, compression="zstd"
        )

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
            for name in KEY_COLUMNS:
                columns[name] = pa.array([key[name]] * n)
            columns["row_id"] = pa.array(np.asarray(row_id, dtype=np.int64))
            columns["y_true"] = pa.array(np.asarray(y_true, dtype=np.int8))
            columns["proba"] = pa.array(np.asarray(proba, dtype=np.float32))
            columns["pred"] = pa.array(np.asarray(pred, dtype=np.int8))
            writer.write_table(pa.table(columns, schema=PREDICTION_SCHEMA))

        try:
            yield write
        finally:
            writer.close()

    def add_slot(self, row: dict[str, Any]) -> None:
        self._slots.append({"config_hash": self.config_hash, **row})

    def add_window(self, row: dict[str, Any]) -> None:
        self._windows.append({"config_hash": self.config_hash, **row})

    def finalize(self, record: dict[str, Any]) -> Path:
        pd.DataFrame(self._slots).to_parquet(self.dir / "slots.parquet", index=False)
        pd.DataFrame(self._windows).to_parquet(self.dir / "windows.parquet", index=False)
        body = {"status": "complete", **record}
        text = json.dumps(body, indent=2, sort_keys=True, default=_jsonable) + "\n"
        (self.dir / "run.json").write_text(text, encoding="utf-8")
        return self.dir

    def fail(self, reason: dict[str, Any]) -> Path:
        """Record why a run stopped; the failure is kept, never silently rerun."""
        path = self.dir / "run_failed.json"
        body = {"status": "failed", "config_hash": self.config_hash, **reason}
        path.write_text(json.dumps(body, indent=2, default=_jsonable) + "\n", encoding="utf-8")
        return path
