"""A small real-slicer stream for simulator tests (seeded synthetic data, never evidence)."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from driftwatch.data.slicer import Window, WindowSpec, slice_windows
from driftwatch.data.synthetic import drifting_timeline
from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.sim.queue import SealedSlot
from driftwatch.sim.selectors import Selection

ANCHOR = np.datetime64("2019-01-07", "ns")
WIDTH = np.timedelta64(14, "D")
N_TRAIN = 3
N_EVAL = 6


def make_source(n_slots: int = 12, rows: int = 300, drift: float = 1.0, seed: int = 3):
    table, X = drifting_timeline(n_slots=n_slots, rows_per_slot=rows, drift=drift, seed=seed)
    return TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, name="synthetic")


def first_window(source=None, *, seed: int = 0) -> Window:
    spec = WindowSpec(N_TRAIN, N_EVAL, 2, 0.10, min_malware=5, seed=seed)
    return next(iter(slice_windows(source or make_source(), spec)))


@lru_cache(maxsize=1)
def eval_slots():
    """The first window's evaluation slots: real EvalSlots from the real slicer."""
    return tuple(first_window().eval_slots())


@lru_cache(maxsize=1)
def train_window():
    return first_window().train


def sealed() -> list[SealedSlot]:
    return [SealedSlot(s) for s in eval_slots()]


def pick(slot: SealedSlot, handles) -> Selection:
    return Selection(slot_id=slot.slot_id, handles=np.asarray(handles, dtype=np.int64))


class Spy:
    """Array stand-in: records who reads it and refuses anything but indexing and conversion."""

    def __init__(self, arr: np.ndarray, field: str, log: list[tuple[str, str, str]]) -> None:
        object.__setattr__(self, "_arr", arr)
        object.__setattr__(self, "_field", field)
        object.__setattr__(self, "_log", log)

    def _note(self, op: str) -> None:
        import sys

        caller = sys._getframe(2).f_globals.get("__name__", "?")
        self._log.append((caller, self._field, op))

    def __getitem__(self, idx):
        self._note("getitem")
        return self._arr[idx]

    def __len__(self) -> int:
        self._note("len")
        return len(self._arr)

    def __array__(self, dtype=None, copy=None):
        self._note("array")
        return np.asarray(self._arr, dtype=dtype)

    def __getattr__(self, name: str):
        if name in {"__array_struct__", "__array_interface__", "__array_priority__"}:
            raise AttributeError(name)  # numpy probes these before __array__
        self._note(f"attr:{name}")
        raise AssertionError(f"unexpected read of {self._field}.{name}")


def spied(slot, log):
    """An EvalSlot whose y, ts and row_id are spies."""
    import dataclasses

    return dataclasses.replace(
        slot,
        y=Spy(slot.y, "y", log),
        ts=Spy(slot.ts, "ts", log),
        row_id=Spy(slot.row_id, "row_id", log),
    )
