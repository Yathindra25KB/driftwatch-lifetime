"""One alarm interface for every drift monitor (Phase 9, docs/prereg/addendum-v3.md).

A monitor answers one question per evaluation slot: does slot ``s`` look unlike the reference
the model in force knows? It is called as ``monitor.update(view, state) -> Alarm``.

- :class:`SlotView` is everything a monitor may see of slot ``s``: the public features, the
  model's malware probability, and the *features* of the calibration rows that have already
  arrived (with their scores under the model in force). It has no label field, and the
  runner builds it from the label-free ``OpaqueSlot`` view, so a monitor cannot reach a
  held-back label (hard rule 4; spy test in tests/test_sim_sealed.py).
- :class:`MonitorState` is the per-(window, seed, arm) state: the reference sample and its
  slot (rule R, ADR-0010), what the monitor fitted at the start of the window, and a cache of
  policy-independent statistics.
- :class:`Alarm` is the decision with its statistic, p-value and threshold. ``decided`` is
  false when the monitor cannot test (for example too few calibration rows); such a slot never
  alarms and is counted.

Every random draw (subsamples, permutations, folds) is seeded by ``(seed, window, slot,
role)`` only, so the same pair (reference slot, current slot) gives the same statistic in
every arm that meets it.

Monitors are frozen by addendum v3 and never tuned (CLAUDE.md rule 10).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import scipy.sparse as sp

ALPHA = 0.01  # one nominal false-alarm rate per slot for every monitor (addendum v3)
N_SUB = 500  # rows per side for KS, the domain classifier and p-uniformity (addendum v3)
INITIAL_REF = -1  # ref_slot of the initial reference (the window's time-ordered hold-out)


@dataclass(frozen=True, eq=False)
class SlotView:
    """What a monitor may see of evaluation slot ``slot_index``: no labels."""

    slot_index: int
    slot_id: str
    X: Any  # public features of the slot, rows in the public (handle) order
    proba: np.ndarray | None = None  # P(malware) under the model in force, same order
    ref_proba: np.ndarray | None = None  # the reference rows scored by the model in force
    cal_X: Any | None = None  # features of the calibration rows that have arrived
    cal_proba: np.ndarray | None = None  # those rows scored by the model in force

    def __post_init__(self) -> None:
        n = _n_rows(self.X)
        if self.proba is not None and len(self.proba) != n:
            raise ValueError("proba must have one entry per row of the slot")
        if (self.cal_X is None) != (self.cal_proba is None):
            raise ValueError("cal_X and cal_proba come together")
        if self.cal_X is not None and len(self.cal_proba) != _n_rows(self.cal_X):
            raise ValueError("cal_proba must have one entry per calibration row")


@dataclass(frozen=True)
class Alarm:
    monitor: str
    slot_index: int
    fired: bool
    decided: bool
    statistic: float
    p_value: float
    threshold: float
    ref_slot: int
    n_ref: int
    n_cur: int


@dataclass
class MonitorState:
    """Per-(window, seed, arm) state of one monitor."""

    seed: int
    window_key: str
    ref_X: Any = None  # reference sample (at most N_SUB rows), features only
    ref_slot: int = INITIAL_REF
    fitted: dict[str, Any] = field(default_factory=dict)  # what ``start`` fitted
    cache: dict[str, Any] = field(default_factory=dict)  # policy-independent statistics
    n_undecided: int = 0
    n_alarms: int = 0

    def reset_reference(self, X: Any, ref_slot: int) -> None:
        """Rule R (ADR-0010): the reference becomes the newest slot the model was fitted on."""
        self.ref_X = X
        self.ref_slot = int(ref_slot)


class Monitor(Protocol):
    name: str
    alpha: float

    def start(
        self, state: MonitorState, train_X: Any, train_y: np.ndarray, ref_full_X: Any
    ) -> None:
        """Fit what the monitor needs once per window, from the initial training window only."""
        ...

    def update(self, view: SlotView, state: MonitorState) -> Alarm: ...


# --- helpers shared by the monitors ------------------------------------------------------


def rng_for(seed: int, window_key: str, *parts: object) -> np.random.Generator:
    """A generator that depends on (seed, window, parts) only, never on the policy."""
    entropy = [int(seed), zlib.crc32(window_key.encode("utf-8"))]
    entropy += [zlib.crc32(str(p).encode("utf-8")) for p in parts]
    return np.random.default_rng(np.random.SeedSequence(entropy))


def _n_rows(X: Any) -> int:
    return int(X.shape[0])


def subsample_index(n_rows: int, n: int, rng: np.random.Generator) -> np.ndarray:
    """At most ``n`` row positions, drawn without replacement and returned sorted."""
    if n_rows <= n:
        return np.arange(n_rows)
    return np.sort(rng.choice(n_rows, size=n, replace=False))


def take_rows(X: Any, idx: np.ndarray) -> Any:
    return X[idx]


def dense(X: Any) -> np.ndarray:
    return np.asarray(X.toarray() if sp.issparse(X) else X, dtype=np.float64)


def reference_sample(X: Any, seed: int, window_key: str, ref_slot: int, n: int = N_SUB) -> Any:
    """The seeded reference sample of a slot (or of the initial hold-out, ``ref_slot = -1``)."""
    idx = subsample_index(_n_rows(X), n, rng_for(seed, window_key, "ref", ref_slot))
    return take_rows(X, idx)


def current_sample(view: SlotView, state: MonitorState, n: int = N_SUB) -> tuple[np.ndarray, Any]:
    """Seeded positions and rows of the current slot (same draw in every arm)."""
    idx = subsample_index(_n_rows(view.X), n, rng_for(state.seed, state.window_key, "cur",
                                                      view.slot_id))  # fmt: skip
    return idx, take_rows(view.X, idx)


def make_alarm(
    name: str, view: SlotView, state: MonitorState, alpha: float, statistic: float,
    p_value: float, n_ref: int, n_cur: int,
) -> Alarm:  # fmt: skip
    fired = bool(p_value <= alpha)
    state.n_alarms += int(fired)
    return Alarm(name, view.slot_index, fired, True, float(statistic), float(p_value), alpha,
                 state.ref_slot, n_ref, n_cur)  # fmt: skip


def undecided(name: str, view: SlotView, state: MonitorState, alpha: float) -> Alarm:
    state.n_undecided += 1
    return Alarm(name, view.slot_index, False, False, float("nan"), float("nan"), alpha,
                 state.ref_slot, 0, 0)  # fmt: skip


def cache_key(name: str, settings: str, state: MonitorState, view: SlotView) -> str:
    return f"{name}|{settings}|{state.window_key}|s{state.seed}|r{state.ref_slot}|{view.slot_id}"


__all__ = [
    "ALPHA",
    "INITIAL_REF",
    "N_SUB",
    "Alarm",
    "Monitor",
    "MonitorState",
    "SlotView",
    "current_sample",
    "dense",
    "make_alarm",
    "reference_sample",
    "rng_for",
    "subsample_index",
    "undecided",
]
