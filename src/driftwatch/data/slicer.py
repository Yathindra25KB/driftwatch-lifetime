"""The time slicer: initial training window, then evaluation slots one at a time.

Dataset-agnostic. A :class:`SlotSource` is anything that can list time slots with their
class counts (without touching features) and load one slot's rows: an in-memory table
(:mod:`driftwatch.data.tables`) or the dataset caches (:mod:`driftwatch.data.presets`).

Planning is features-free:

1. :func:`plan_slots` applies the size gate (ADR-0004): a slot is usable only if it is not
   empty, not partial, and keeps at least ``min_malware`` malware after C3 subsampling at the
   target ratio. Every other slot is skipped with a reason.
2. :func:`plan_windows` carves windows from maximal runs of consecutive usable slots. A window
   (``nT`` training slots then ``nE`` evaluation slots) never contains a gap or a skipped slot.
   ``nE=None`` is the single-run protocol: train on the first ``nT`` slots of a run and
   evaluate on the rest of it.

Iteration is lazy: :func:`slice_windows` yields a :class:`Window` whose training slots are
loaded (raw rows), and :meth:`Window.eval_slots` then loads, subsamples and checks one
evaluation slot per step. Each evaluation slot passes C3, C2 and C1 (the constraints module)
before it is yielded, so a slot that violates a constraint cannot leave the iterator.

Selectors, policies and monitors must only ever see :meth:`EvalSlot.public`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import platform
import zlib
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
import scipy.sparse as sp

from driftwatch.data import constraints
from driftwatch.data.constraints import C3Result

log = logging.getLogger(__name__)

_PUBLIC_ORDER_TAG = 0x70756231  # separates the public-order draw from the C3 draw

SKIP_GAP, SKIP_PARTIAL, SKIP_SIZE_GATE = "gap", "partial", "size_gate"
SKIP_RUN_SHORT = "shorter_than_window"


class SlicerError(Exception):
    """The slicer's own invariants broke (grid, counts, densification), not a C1-C3 check."""


# --- configuration --------------------------------------------------------------------------


@dataclass(frozen=True)
class WindowSpec:
    """One slicing configuration: window shape, target ratio, size gate and seed."""

    nT: int
    nE: int | None
    stride: int
    target_ratio: float = 0.10
    min_malware: int = 50
    seed: int = 0

    def __post_init__(self) -> None:
        if self.nT < 1:
            raise ValueError("nT must be at least 1")
        if self.nE is not None and self.nE < 1:
            raise ValueError("nE must be at least 1, or None for the single-run protocol")
        if self.stride < 1:
            raise ValueError("stride must be at least 1")
        if not 0.0 < self.target_ratio < 1.0:
            raise ValueError("target_ratio must lie strictly between 0 and 1")
        if self.min_malware < 1:
            raise ValueError("min_malware must be at least 1")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")

    def at_ratio(self, ratio: float) -> WindowSpec:
        return dataclasses.replace(self, target_ratio=ratio)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()[:16]


@dataclass(frozen=True)
class RowFilter:
    """A named, label-free rule that marks rows to exclude (True = exclude).

    The rule only ever sees the columns it declares, so a filter cannot read labels (or
    family, VT counts, categories) unless it names them, and a reviewer can see that it does.
    """

    name: str
    fn: Callable[[pd.DataFrame], Any]
    columns: tuple[str, ...] = ()

    def __call__(self, meta: pd.DataFrame) -> np.ndarray:
        return np.asarray(self.fn(meta.loc[:, list(self.columns)]), dtype=bool)


# --- data model -----------------------------------------------------------------------------


@dataclass(frozen=True)
class SlotRef:
    slot_id: str
    start: np.datetime64  # inclusive, UTC, ns
    end: np.datetime64  # exclusive
    index: int  # position in the slot grid, gaps counted


@dataclass(frozen=True)
class SlotInfo:
    """One grid slot as a source reports it (counts exclude rows the source filtered out)."""

    ref: SlotRef
    n_rows: int
    n_malware: int
    n_benign: int
    n_excluded: int = 0
    structural: str = ""  # "" or "partial" (a base unit of the slot is missing or emptied)
    n_naive_ts: int = 0  # kept rows whose timestamp was published without a UTC offset


@dataclass(frozen=True, eq=False)
class SlotRows:
    ref: SlotRef
    y: np.ndarray  # int8, 1 = malware
    ts: np.ndarray  # datetime64[ns], naive UTC
    row_id: np.ndarray  # int64
    X: Any = None  # scipy CSR or ndarray, rows aligned with the arrays above
    fv_hash: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.y.shape[0])


class SlotSource(Protocol):
    name: str
    sparse: bool

    def slot_table(self) -> list[SlotInfo]: ...

    def load_slot(self, slot_id: str) -> SlotRows: ...

    def provenance(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class PlannedSlot:
    ref: SlotRef
    n_rows: int
    n_malware: int
    n_benign: int
    n_excluded: int
    n_malware_kept: int  # min(n_malware, target count) at the spec's ratio
    structural: str
    usable: bool
    skip_reason: str  # "" when usable
    n_naive_ts: int = 0


@dataclass(frozen=True)
class WindowPlan:
    window_id: str
    segment: int
    train: tuple[SlotRef, ...]
    eval: tuple[SlotRef, ...]


@dataclass(frozen=True)
class SkippedRun:
    first_slot: str
    last_slot: str
    n_slots: int
    reason: str


@dataclass(frozen=True)
class Schedule:
    windows: tuple[WindowPlan, ...]
    skipped_slots: tuple[PlannedSlot, ...]
    skipped_runs: tuple[SkippedRun, ...]


# --- planning -------------------------------------------------------------------------------


def _fails_size_gate(kept: int, spec: WindowSpec) -> bool:
    """The gate of ADR-0004: fewer than M malware would survive C3 subsampling."""
    return kept < spec.min_malware


def plan_slots(source: SlotSource, spec: WindowSpec) -> list[PlannedSlot]:
    """Apply the size gate to every grid slot. Reads counts only, never features."""
    table = source.slot_table()
    ids = [t.ref.slot_id for t in table]
    if len(set(ids)) != len(ids):
        raise SlicerError("slot ids are not unique")
    if [t.ref.index for t in table] != list(range(len(table))):
        raise SlicerError("the slot grid is not consecutive: a window could silently span a hole")
    planned = []
    for info in table:
        kept = min(
            info.n_malware, constraints.target_malware_count(info.n_benign, spec.target_ratio)
        )
        if info.n_rows == 0:
            reason = SKIP_GAP
        elif info.structural == SKIP_PARTIAL:
            reason = SKIP_PARTIAL
        elif _fails_size_gate(kept, spec):
            reason = SKIP_SIZE_GATE
        else:
            reason = ""
        planned.append(
            PlannedSlot(
                ref=info.ref,
                n_rows=info.n_rows,
                n_malware=info.n_malware,
                n_benign=info.n_benign,
                n_excluded=info.n_excluded,
                n_malware_kept=kept,
                structural=info.structural,
                usable=reason == "",
                skip_reason=reason,
                n_naive_ts=info.n_naive_ts,
            )
        )
    return planned


def _usable_runs(planned: list[PlannedSlot]) -> list[list[PlannedSlot]]:
    """Maximal runs of consecutive usable slots; any skipped slot or gap ends a run."""
    runs: list[list[PlannedSlot]] = []
    for slot in planned:
        if not slot.usable:
            continue
        if runs and slot.ref.index == runs[-1][-1].ref.index + 1:
            runs[-1].append(slot)
        else:
            runs.append([slot])
    return runs


def _window_starts(length: int, spec: WindowSpec) -> list[int]:
    if spec.nE is None:
        return [0] if length > spec.nT else []
    if length < spec.nT + spec.nE:
        return []
    return list(range(0, length - (spec.nT + spec.nE) + 1, spec.stride))


def plan_windows(planned: list[PlannedSlot], spec: WindowSpec, source_digest: str = "") -> Schedule:
    """Carve windows from runs of usable slots; ``source_digest`` keys results by source."""
    windows: list[WindowPlan] = []
    skipped_runs: list[SkippedRun] = []
    for segment, run in enumerate(_usable_runs(planned)):
        starts = _window_starts(len(run), spec)
        if not starts:
            skipped_runs.append(
                SkippedRun(run[0].ref.slot_id, run[-1].ref.slot_id, len(run), SKIP_RUN_SHORT)
            )
            continue
        for start in starts:
            train = tuple(p.ref for p in run[start : start + spec.nT])
            rest = run[start + spec.nT :]
            evaluation = tuple(p.ref for p in (rest if spec.nE is None else rest[: spec.nE]))
            n_e = "all" if spec.nE is None else spec.nE
            # Digests keep results at another ratio, seed, gate or source (row filter, anchor,
            # manifest) from colliding on (window_id, slot_id).
            head = spec.digest() if not source_digest else f"{spec.digest()}-{source_digest}"
            window_id = f"{head}|{train[0].slot_id}|T{spec.nT}|E{n_e}"
            windows.append(WindowPlan(window_id, segment, train, evaluation))
    skipped = tuple(p for p in planned if not p.usable)
    return Schedule(tuple(windows), skipped, tuple(skipped_runs))


# --- iteration ------------------------------------------------------------------------------


def seen_before_mask(current_fv: np.ndarray, pool_fv: np.ndarray) -> np.ndarray:
    """True where a row's feature vector is already in ``pool_fv``.

    "Past only" is the caller's contract: pass the training pool that existed when the row
    was evaluated, never a set that includes later slots (ADR-0004 item 6).
    """
    return np.isin(np.asarray(current_fv), np.asarray(pool_fv))


def _stack(parts: list[Any]) -> Any:
    if any(p is None for p in parts):
        return None
    if sp.issparse(parts[0]):
        return sp.vstack(parts, format="csr")
    return np.concatenate(parts, axis=0)


@dataclass(frozen=True, eq=False)
class TrainWindow:
    """The initial training window: raw rows (no C3), kept slot by slot.

    Hold-outs for calibration or early stopping must be cut at slot boundaries with
    :meth:`split_at_slot`, never by row position inside a slot (ADR-0004 item 8).
    """

    slots: tuple[SlotRows, ...]

    @property
    def y(self) -> np.ndarray:
        return np.concatenate([s.y for s in self.slots])

    @property
    def ts(self) -> np.ndarray:
        return np.concatenate([s.ts for s in self.slots])

    @property
    def row_id(self) -> np.ndarray:
        return np.concatenate([s.row_id for s in self.slots])

    @property
    def X(self) -> Any:
        return _stack([s.X for s in self.slots])

    @property
    def fv_hash(self) -> np.ndarray | None:
        parts = [s.fv_hash for s in self.slots]
        return None if any(p is None for p in parts) else np.concatenate(parts)

    def split_at_slot(self, k: int) -> tuple[TrainWindow, TrainWindow]:
        """(older ``k`` slots, newer slots); ``k`` must leave both sides non-empty."""
        if not 0 < k < len(self.slots):
            raise ValueError(f"split must leave both sides non-empty, got {k} of {len(self.slots)}")
        return TrainWindow(self.slots[:k]), TrainWindow(self.slots[k:])


@dataclass(frozen=True, eq=False)
class OpaqueSlot:
    """What a selector, policy or monitor may see of an evaluation slot.

    A distinct type from the loader's ``PublicSlot`` (which keeps the dataset's own row ids
    and order, and is for loader-level code only), so a type check can tell them apart.
    There is deliberately no ``row_id`` and no back-reference to the slot.
    """

    dataset: str
    slot_id: str
    X: Any
    handle: np.ndarray  # 0..n-1 in a seeded, label-independent order


@dataclass(frozen=True, eq=False)
class EvalSlot:
    """One evaluation slot after C3 subsampling, already checked against C1, C2 and C3."""

    ref: SlotRef
    dataset: str
    X: Any
    y: np.ndarray
    ts: np.ndarray
    row_id: np.ndarray
    c3: C3Result
    perm: np.ndarray  # seeded, label-independent shuffle that defines the public order
    n_seen_in_initial_train: int | None = None

    def public(self) -> OpaqueSlot:
        """The label-free view (hard rule 4): features and opaque handles only.

        Rows come in a seeded shuffle that depends on ``(seed, slot id)`` and nothing else,
        and the ids are the handles ``0..n-1`` of that order. Neither the order nor the ids
        say anything about time rank, malware drops, source file or class. The features are a
        copy, so a consumer cannot alter what is later scored. Only the label queue and the
        metrics map handles back, with :meth:`resolve`.
        """
        X = None if self.X is None else self.X[self.perm]
        handles = np.arange(len(self.perm), dtype=np.int64)
        return OpaqueSlot(self.dataset, self.ref.slot_id, X, handles)

    def resolve(self, slot_id: str, handles: Any) -> np.ndarray:
        """Positions in this slot (indexing ``y``, ``ts``, ``row_id``) of public handles.

        Handles are slot-local, so the slot id they came with must match: resolving a
        slot's handles against another slot would release the wrong labels.
        """
        if slot_id != self.ref.slot_id:
            raise SlicerError(
                f"handles from slot {slot_id!r} resolved against slot {self.ref.slot_id!r}"
            )
        h = np.asarray(handles, dtype=np.int64)
        if h.size and (h.min() < 0 or h.max() >= len(self.perm)):
            raise SlicerError("a handle lies outside the slot")
        return self.perm[h]


def _load(source: SlotSource, planned: dict[str, PlannedSlot], ref: SlotRef) -> SlotRows:
    rows = source.load_slot(ref.slot_id)
    if rows.X is not None and source.sparse and not sp.issparse(rows.X):
        raise SlicerError(
            f"{ref.slot_id}: a sparse source returned a dense matrix; refusing to densify"
        )
    plan = planned[ref.slot_id]
    n_mal = int((rows.y == 1).sum())
    if (len(rows), n_mal) != (plan.n_rows, plan.n_malware):
        raise SlicerError(
            f"{ref.slot_id}: loaded {len(rows)} rows / {n_mal} malware, planned "
            f"{plan.n_rows} / {plan.n_malware}; the source changed under the plan"
        )
    return rows


@dataclass(eq=False)
class Window:
    plan: WindowPlan
    dataset: str
    train: TrainWindow
    spec: WindowSpec
    _source: SlotSource = field(repr=False)
    _planned: dict[str, PlannedSlot] = field(repr=False)
    _log: SliceLog | None = field(default=None, repr=False)

    def eval_slots(self) -> Iterator[EvalSlot]:
        """Load, subsample and check one evaluation slot per step, in time order."""
        train_ts = self.train.ts
        train_fv = self.train.fv_hash
        for ref in self.plan.eval:
            rows = _load(self._source, self._planned, ref)
            # C2 on the whole raw slot first: a stray row must not escape by being subsampled.
            constraints.check_c2(rows.ts, rows.y, ref.start, ref.end)
            kept = constraints.subsample_malware(
                rows.y, self.spec.target_ratio, self.spec.seed, ref.slot_id
            )
            c3 = constraints.check_c3(rows.y, kept, self.spec.target_ratio)
            ts, y, row_id = rows.ts[kept], rows.y[kept], rows.row_id[kept]
            constraints.check_c2(ts, y, ref.start, ref.end)
            constraints.check_c1(train_ts, ts)
            seen = None
            if train_fv is not None and rows.fv_hash is not None:
                seen = int(seen_before_mask(rows.fv_hash[kept], train_fv).sum())
            entropy = [self.spec.seed, zlib.crc32(ref.slot_id.encode("utf-8")), _PUBLIC_ORDER_TAG]
            perm = np.random.default_rng(np.random.SeedSequence(entropy)).permutation(len(y))
            slot = EvalSlot(
                ref=ref,
                dataset=self.dataset,
                X=None if rows.X is None else rows.X[kept],
                y=y,
                ts=ts,
                row_id=row_id,
                c3=c3,
                perm=perm,
                n_seen_in_initial_train=seen,
            )
            log.info(
                "C3 %s: malware %d -> %d, benign %d -> %d, %.1f%% of malware discarded, "
                "ratio %.4f (%s)",
                ref.slot_id,
                c3.n_malware_before,
                c3.n_malware_after,
                c3.n_benign_before,
                c3.n_benign_after,
                100 * c3.share_malware_discarded,
                c3.achieved_ratio,
                c3.status,
            )
            if self._log is not None:
                self._log.record_eval(self.plan, slot)
            yield slot


def _train_rows(
    source: SlotSource, planned: dict[str, PlannedSlot], plan: WindowPlan
) -> tuple[SlotRows, ...]:
    """The raw rows of a window's training slots, in time order."""
    return tuple(_load(source, planned, ref) for ref in plan.train)


def _open_window(
    source: SlotSource,
    plan: WindowPlan,
    spec: WindowSpec,
    planned: dict[str, PlannedSlot],
    slicelog: SliceLog | None,
) -> Window:
    refs = (*plan.train, *plan.eval)
    if [r.index for r in refs] != list(range(refs[0].index, refs[0].index + len(refs))):
        raise SlicerError(f"{plan.window_id}: window spans a gap or a skipped slot")
    for ref in refs:
        if not planned[ref.slot_id].usable:
            raise SlicerError(f"{plan.window_id}: {ref.slot_id} failed the gate but is in a window")
    rows = _train_rows(source, planned, plan)
    for ref, slot_rows in zip(plan.train, rows, strict=True):
        # Training rows must belong to their slot's window too; "no gap spanned" would
        # otherwise rest on how the cache was routed.
        constraints.check_c2(slot_rows.ts, slot_rows.y, ref.start, ref.end)
    train = TrainWindow(rows)
    if slicelog is not None:
        slicelog.record_train(plan, train)
    return Window(plan, source.name, train, spec, source, planned, slicelog)


def slice_windows(
    source: SlotSource,
    spec: WindowSpec,
    slicelog: SliceLog | None = None,
    *,
    only: Sequence[int] | None = None,
) -> Iterator[Window]:
    """Plan once, then yield each window with its training slots loaded.

    Skipped slots and runs are logged through :mod:`logging` and recorded in ``slicelog``.
    ``only`` restricts iteration to those positions of the schedule (other windows are not
    loaded), which keeps spot checks such as the canary cheap.
    """
    planned = plan_slots(source, spec)
    schedule = plan_windows(planned, spec, _source_digest(source))
    for slot in schedule.skipped_slots:
        if slot.skip_reason != SKIP_GAP:
            log.info(
                "skipped %s: %s (malware %d, benign %d, kept at target %d)",
                slot.ref.slot_id,
                slot.skip_reason,
                slot.n_malware,
                slot.n_benign,
                slot.n_malware_kept,
            )
    for run in schedule.skipped_runs:
        log.info("skipped run %s..%s: %s", run.first_slot, run.last_slot, run.reason)
    if slicelog is not None:
        slicelog.record_plan(planned, schedule)
    by_id = {p.ref.slot_id: p for p in planned}
    wanted = None if only is None else set(only)
    for position, plan in enumerate(schedule.windows):
        if wanted is None or position in wanted:
            yield _open_window(source, plan, spec, by_id, slicelog)


def _source_digest(source: SlotSource) -> str:
    text = json.dumps(source.provenance(), sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def count_windows(source: SlotSource, spec: WindowSpec) -> int:
    """How many windows the spec yields on this source (features-free)."""
    return len(plan_windows(plan_slots(source, spec), spec).windows)


# --- manifest -------------------------------------------------------------------------------


def _iso(value: np.datetime64) -> str:
    return str(np.datetime64(value, "s"))


def _package_versions() -> dict[str, str]:
    out = {"python": platform.python_version()}
    for name in ("numpy", "pandas", "scipy", "pyarrow", "driftwatch-lifetime"):
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "unknown"
    return out


class SliceLog:
    """Collects the per-slot manifest of a slicing run and writes it."""

    SLOT_COLUMNS = (
        "slot_id",
        "start",
        "end",
        "index",
        "n_rows",
        "n_malware",
        "n_benign",
        "n_excluded",
        "n_naive_ts",
        "n_malware_kept",
        "structural",
        "usable",
        "skip_reason",
    )
    WINDOW_COLUMNS = (
        "window_id",
        "segment",
        "role",
        "slot_id",
        "start",
        "end",
        "n_rows",
        "n_malware_before",
        "n_benign_before",
        "n_malware_after",
        "n_benign_after",
        "share_malware_discarded",
        "achieved_ratio",
        "target_ratio",
        "c3_status",
        "n_seen_in_initial_train",
    )

    def __init__(self) -> None:
        self.slot_rows: list[dict[str, Any]] = []
        self.window_rows: list[dict[str, Any]] = []
        self.skipped_runs: list[dict[str, Any]] = []

    def record_plan(self, planned: list[PlannedSlot], schedule: Schedule | None) -> None:
        self.slot_rows = [
            {
                "slot_id": p.ref.slot_id,
                "start": _iso(p.ref.start),
                "end": _iso(p.ref.end),
                "index": p.ref.index,
                "n_rows": p.n_rows,
                "n_malware": p.n_malware,
                "n_benign": p.n_benign,
                "n_excluded": p.n_excluded,
                "n_naive_ts": p.n_naive_ts,
                "n_malware_kept": p.n_malware_kept,
                "structural": p.structural,
                "usable": p.usable,
                "skip_reason": p.skip_reason,
            }
            for p in planned
        ]
        runs = [] if schedule is None else schedule.skipped_runs
        self.skipped_runs = [dataclasses.asdict(r) for r in runs]

    def _put(self, row: dict[str, Any]) -> None:
        """Insert or replace by (window_id, role, slot_id): re-iterating never double-counts."""
        key = (row["window_id"], row["role"], row["slot_id"])
        for i, old in enumerate(self.window_rows):
            if (old["window_id"], old["role"], old["slot_id"]) == key:
                self.window_rows[i] = row
                return
        self.window_rows.append(row)

    def record_train(self, plan: WindowPlan, train: TrainWindow) -> None:
        for rows in train.slots:
            n_mal = int((rows.y == 1).sum())
            self._put(
                {
                    "window_id": plan.window_id,
                    "segment": plan.segment,
                    "role": "train",
                    "slot_id": rows.ref.slot_id,
                    "start": _iso(rows.ref.start),
                    "end": _iso(rows.ref.end),
                    "n_rows": len(rows),
                    "n_malware_before": n_mal,
                    "n_benign_before": len(rows) - n_mal,
                    "n_malware_after": n_mal,
                    "n_benign_after": len(rows) - n_mal,
                    "share_malware_discarded": 0.0,
                    "achieved_ratio": n_mal / len(rows) if len(rows) else None,
                    "target_ratio": None,
                    "c3_status": "raw",
                    "n_seen_in_initial_train": None,
                }
            )

    def record_eval(self, plan: WindowPlan, slot: EvalSlot) -> None:
        c3 = slot.c3
        self._put(
            {
                "window_id": plan.window_id,
                "segment": plan.segment,
                "role": "eval",
                "slot_id": slot.ref.slot_id,
                "start": _iso(slot.ref.start),
                "end": _iso(slot.ref.end),
                "n_rows": c3.n_malware_before + c3.n_benign_before,
                "n_malware_before": c3.n_malware_before,
                "n_benign_before": c3.n_benign_before,
                "n_malware_after": c3.n_malware_after,
                "n_benign_after": c3.n_benign_after,
                "share_malware_discarded": c3.share_malware_discarded,
                "achieved_ratio": c3.achieved_ratio,
                "target_ratio": c3.target_ratio,
                "c3_status": c3.status,
                "n_seen_in_initial_train": slot.n_seen_in_initial_train,
            }
        )

    def write(
        self,
        out_dir: Path | str,
        *,
        spec: WindowSpec,
        source: SlotSource,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Path]:
        """Write slot_manifest.csv, window_manifest.csv and slicing_run.json under out_dir.

        ``extra`` (wall-clock, peak memory, row counts) is stored under ``run``.
        """
        from driftwatch.data.cache import code_version

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        paths = {
            "slot_manifest": out / "slot_manifest.csv",
            "window_manifest": out / "window_manifest.csv",
            "run": out / "slicing_run.json",
        }
        slots = pd.DataFrame(self.slot_rows, columns=list(self.SLOT_COLUMNS))
        windows = pd.DataFrame(self.window_rows, columns=list(self.WINDOW_COLUMNS))
        slots.to_csv(paths["slot_manifest"], index=False, lineterminator="\n")
        windows.to_csv(paths["window_manifest"], index=False, lineterminator="\n")
        usable = int(slots["usable"].sum()) if len(slots) else 0
        run = {
            "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "spec": spec.to_dict(),
            "spec_digest": spec.digest(),
            "source": source.provenance(),
            "code_version": code_version(),
            "packages": _package_versions(),
            "counts": {
                "slots": len(slots),
                "usable_slots": usable,
                "skipped_slots": len(slots) - usable,
                "skipped_runs": len(self.skipped_runs),
                "windows": int(windows["window_id"].nunique()) if len(windows) else 0,
            },
            "skipped_runs": self.skipped_runs,
            "run": extra or {},
        }
        paths["run"].write_text(json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return paths
