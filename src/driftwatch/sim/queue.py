"""The label queue: the only module that knows about the delay ``d`` (hard rule 3).

Rule (PROTOCOL.md section 4): a label queried while evaluation slot ``t`` is being streamed
becomes usable from slot ``t + 1 + d`` (``d = 0`` means the next slot). A slot is scored
before any label queried in it exists, so a label can never inform the slot it came from.

Window end (documented rule): evaluation slots are indexed ``0..n_slots-1`` within a window.
A label whose release slot ``t + 1 + d`` is ``>= n_slots`` has no slot left to inform, so it
is **ignored** and counted in :attr:`LabelQueue.n_ignored`. Windows are independent runs;
nothing carries over into the next window.

Sealed labels (hard rule 4): :class:`SealedSlot` wraps an :class:`EvalSlot` so that nothing
else in ``sim/`` holds the true labels. They leave it by two doors only: the queue's
:meth:`LabelQueue.query` (which hands them back, delayed, through :meth:`LabelQueue.release`)
and :meth:`SealedSlot.score` (metric code). Selectors, policies and the pool receive
``OpaqueSlot`` views and released rows, never the slot.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np

from driftwatch.data import constraints
from driftwatch.data.constraints import C3Result
from driftwatch.data.slicer import EvalSlot, OpaqueSlot, SlotRef, _stack
from driftwatch.metrics.slot import SlotScores, score_slot
from driftwatch.sim.selectors import Selection


@dataclass(frozen=True, eq=False)
class Scored:
    """One scored slot: the labels metric code saw and the scores computed from them."""

    y_true: np.ndarray
    row_id: np.ndarray
    scores: SlotScores


def _frozen(public: OpaqueSlot) -> OpaqueSlot:
    """Make the cached public view read-only.

    The same arrays back every consumer and the scoring door, so an in-place edit (a shuffle
    of the handles, a write into the features) would silently pair predictions with the
    wrong labels. The slicer builds both arrays fresh per call, so freezing them here does
    not touch the evaluation slot itself.
    """
    public.handle.setflags(write=False)
    X = public.X
    if hasattr(X, "indptr"):  # CSR
        for part in (X.data, X.indices, X.indptr):
            part.setflags(write=False)
    elif X is not None:
        X.setflags(write=False)
    return public


class SealedSlot:
    """An evaluation slot whose true labels are reachable only by the queue and metric code."""

    __slots__ = ("_public", "_slot")

    def __init__(self, slot: EvalSlot) -> None:
        self._slot = slot
        self._public = _frozen(slot.public())

    @property
    def slot_id(self) -> str:
        return self._slot.ref.slot_id

    @property
    def ref(self) -> SlotRef:
        return self._slot.ref

    @property
    def c3(self) -> C3Result:
        return self._slot.c3

    @property
    def n_seen_in_initial_train(self) -> int | None:
        return self._slot.n_seen_in_initial_train

    @property
    def n(self) -> int:
        return len(self._public.handle)

    def n_seen_in(self, pool_fv_hash: np.ndarray | None) -> int | None:
        """Rows of this slot whose feature vector is already in the training pool.

        A count only: the hashes stay inside the slot. ``None`` when either side carries no
        hashes (a synthetic source without them).
        """
        if pool_fv_hash is None or self._slot.fv_hash is None:
            return None
        return int(np.isin(self._slot.fv_hash, pool_fv_hash).sum())

    def public(self) -> OpaqueSlot:
        """The label-free view (the same object every call, so scoring order is stable)."""
        return self._public

    def assert_c1(self, train_ts: np.ndarray) -> None:
        """C1 against the rows a model was trained on, including released labels."""
        constraints.check_c1(train_ts, np.asarray(self._slot.ts))

    def score(self, pred: np.ndarray) -> Scored:
        """Metric code's door: ``pred`` is in the public (handle) order of this slot."""
        positions = self._slot.resolve(self._public.slot_id, self._public.handle)
        y_true = np.asarray(self._slot.y[positions])
        return Scored(y_true, np.asarray(self._slot.row_id[positions]), score_slot(y_true, pred))

    def _take(self, selection: Selection) -> _Rows:
        """The queue's door: the labelled rows behind a selection, in selection order."""
        positions = self._slot.resolve(selection.slot_id, selection.handles)
        if self._slot.X is None:
            raise ValueError("the slot carries no features; the pool cannot be built from it")
        return _Rows(
            X=self._slot.X[positions],
            y=np.asarray(self._slot.y[positions]),
            ts=np.asarray(self._slot.ts[positions]),
            row_id=np.asarray(self._slot.row_id[positions]),
            fv_hash=None if self._slot.fv_hash is None else self._slot.fv_hash[positions],
            origin=selection.origin,
        )


@dataclass(frozen=True, eq=False)
class _Rows:
    X: Any
    y: np.ndarray
    ts: np.ndarray
    row_id: np.ndarray
    fv_hash: np.ndarray | None = None
    origin: np.ndarray | None = None  # per row: "random_slice" or "selected" (E3), else None


@dataclass(frozen=True, eq=False)
class Released:
    """The labels that become usable at one slot. ``X`` is ``None`` when nothing arrived."""

    slot_index: int
    X: Any
    y: np.ndarray
    ts: np.ndarray
    row_id: np.ndarray
    queried_in: np.ndarray  # evaluation-slot index each row was queried in
    fv_hash: np.ndarray | None = None  # feature-vector hashes (for the pool's seen-before count)
    origin: np.ndarray | None = None  # how each row was chosen (E3); None when not tracked

    def __len__(self) -> int:
        return len(self.y)

    def take(self, mask: np.ndarray) -> Released:
        """The rows where ``mask`` is true (for example the calibration rows of a release)."""
        m = np.asarray(mask, dtype=bool)
        if m.shape != (len(self),):
            raise ValueError("mask must have one entry per released row")
        if len(self) == 0:
            return self
        return Released(
            self.slot_index,
            self.X[m],
            self.y[m],
            self.ts[m],
            self.row_id[m],
            self.queried_in[m],
            None if self.fv_hash is None else self.fv_hash[m],
            None if self.origin is None else self.origin[m],
        )


@dataclass(frozen=True)
class QueryReceipt:
    n_queried: int
    release_slot: int | None  # None when the label would arrive after the window ends
    n_ignored: int


def _check_delay(delay: Any) -> int:
    if isinstance(delay, bool) or not isinstance(delay, int) or delay < 0:
        raise ValueError(f"delay must be a non-negative integer number of slots, got {delay!r}")
    return delay


class LabelQueue:
    """Holds queried labels back and releases each one at slot ``t + 1 + delay``."""

    def __init__(self, delay: int, n_slots: int) -> None:
        self._delay = _check_delay(delay)
        if isinstance(n_slots, bool) or not isinstance(n_slots, int) or n_slots < 1:
            raise ValueError(f"n_slots must be a positive integer, got {n_slots!r}")
        self._n_slots = n_slots
        self._pending: dict[int, list[tuple[int, _Rows]]] = defaultdict(list)
        self._queried: set[int] = set()
        self._next_release = 0
        self.n_queued = 0
        self.n_released = 0
        self.n_ignored = 0

    def release_slot(self, query_slot: int) -> int:
        """The slot from which a label queried at ``query_slot`` is usable (the delay rule)."""
        return query_slot + 1 + self._delay

    @property
    def n_pending(self) -> int:
        return self.n_queued - self.n_released - self.n_ignored

    def release(self, slot_index: int) -> Released:
        """The labels that arrive at ``slot_index``. Call once per slot, in order from 0."""
        if slot_index != self._next_release:
            raise ValueError(
                f"releases must be in order: expected slot {self._next_release}, got {slot_index}"
            )
        if slot_index >= self._n_slots:
            raise ValueError(f"slot index {slot_index} is outside the window of {self._n_slots}")
        self._next_release += 1
        batches = self._pending.pop(slot_index, [])
        self.n_released += sum(len(rows.y) for _, rows in batches)
        if not batches:
            empty_i = np.empty(0, dtype=np.int64)
            return Released(
                slot_index,
                None,
                np.empty(0, dtype=np.int8),
                np.empty(0, dtype="datetime64[ns]"),
                empty_i,
                empty_i,
            )
        return Released(
            slot_index,
            _stack([rows.X for _, rows in batches]),
            np.concatenate([rows.y for _, rows in batches]),
            np.concatenate([rows.ts for _, rows in batches]),
            np.concatenate([rows.row_id for _, rows in batches]),
            np.concatenate([np.full(len(rows.y), t, dtype=np.int64) for t, rows in batches]),
            None
            if any(rows.fv_hash is None for _, rows in batches)
            else np.concatenate([rows.fv_hash for _, rows in batches]),
            None
            if any(rows.origin is None for _, rows in batches)
            else np.concatenate([rows.origin for _, rows in batches]),
        )

    def query(self, slot_index: int, slot: SealedSlot, selection: Selection) -> QueryReceipt:
        """Spend budget on ``selection`` of the slot being streamed; labels arrive later.

        Only the slot just released may be queried (stream order: it was already scored).
        """
        if slot_index in self._queried:
            raise ValueError(f"slot {slot_index} was already queried")
        if slot_index != self._next_release - 1:
            raise ValueError(
                f"slot index {slot_index} is not the slot being streamed "
                f"({self._next_release - 1}); release it first"
            )
        handles = np.asarray(selection.handles, dtype=np.int64)
        if len(np.unique(handles)) != len(handles):
            raise ValueError("duplicate handles in one selection")
        rows = slot._take(selection)  # resolves against this slot's id, raises on mismatch
        self._queried.add(slot_index)
        n = len(rows.y)
        self.n_queued += n
        release_slot = self.release_slot(slot_index)
        if release_slot >= self._n_slots:
            self.n_ignored += n
            return QueryReceipt(n, None, n)
        if n:
            self._pending[release_slot].append((slot_index, rows))
        return QueryReceipt(n, release_slot, 0)
