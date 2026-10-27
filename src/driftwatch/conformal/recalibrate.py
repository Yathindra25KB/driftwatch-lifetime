"""Calibration buffer and the explicit recalibration rule (E3).

The rule, written down before any E3 run (docs/prereg/addendum-v2.md):

1. **Initial calibration** comes from a time-ordered hold-out inside the initial training
   window: the newest ``holdout_fraction`` of the window's rows by timestamp, which the model
   was **not** trained on (:func:`time_ordered_holdout`).
2. **Later calibration labels come only from the reserved random slice** of each slot's
   budget, and only when they have arrived through the label queue (so the delay applies to
   calibration too). A row that a selector chose by score never enters the buffer: adding one
   raises :class:`CalibrationContamination`. The 0% reserved-slice arm of the ablation is a
   deliberate trap demonstration and has to say so (``allow_selected=True``).
3. The buffer keeps the most recent ``buffer_size`` rows (oldest evicted first).
4. **Recalibration** recomputes the nonconformity of every buffered row under the *current*
   model, once per refit, and needs at least ``min_per_class`` rows of each class. Otherwise
   the previous calibration is kept and ``n_skipped`` is incremented.

Calibration rows are not training rows: split conformal needs the calibration set to be
disjoint from the rows the scoring model was fitted on (ADR-0009).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.sparse as sp

from driftwatch.conformal.mondrian import ClassCalibration

ORIGIN_RANDOM = "random_slice"
ORIGIN_HOLDOUT = "holdout"
ORIGIN_SELECTED = "selected"
ALLOWED_ORIGINS = (ORIGIN_RANDOM, ORIGIN_HOLDOUT)


class CalibrationContamination(RuntimeError):
    """A sample that a selector chose entered the calibration buffer."""


@dataclass(frozen=True)
class RecalibrationRule:
    holdout_fraction: float = 0.20
    min_per_class: int = 20
    buffer_size: int = 1000

    def __post_init__(self) -> None:
        if not 0.0 < self.holdout_fraction < 1.0:
            raise ValueError("holdout_fraction must lie strictly between 0 and 1")
        if self.min_per_class < 1 or self.buffer_size < 2 * self.min_per_class:
            raise ValueError("buffer_size must hold at least min_per_class rows of both classes")


def time_ordered_holdout(ts: np.ndarray, fraction: float) -> tuple[np.ndarray, np.ndarray]:
    """Indices ``(train, holdout)``: the newest ``fraction`` of rows by timestamp.

    The boundary is moved to a change of timestamp so that no timestamp sits on both sides:
    every hold-out row is strictly newer than every proper-training row (C1 inside the
    window). Returns index arrays in time order.
    """
    t = np.asarray(ts)
    n = len(t)
    if n < 2:
        raise ValueError("need at least two rows to hold one out")
    order = np.argsort(t, kind="stable")
    cut = max(1, min(n - 1, int(round((1.0 - fraction) * n))))
    ordered = t[order]
    while cut < n and ordered[cut] == ordered[cut - 1]:
        cut += 1  # keep equal timestamps on one side
    if cut >= n:  # all later rows share one timestamp: move the boundary down instead
        cut = int(np.searchsorted(ordered, ordered[-1], side="left"))
        if cut == 0:
            raise ValueError("all rows share one timestamp; a time-ordered hold-out is undefined")
    return order[:cut], order[cut:]


@dataclass(frozen=True)
class Calibration:
    """The calibration in force: per-class sorted scores and when it was computed."""

    classes: ClassCalibration
    n_rows: int
    built_at: int  # slot index of the (re)calibration; -1 for the initial one


class CalibrationBuffer:
    """Recent calibration rows with their labels; scores are recomputed at recalibration."""

    def __init__(self, rule: RecalibrationRule | None = None, *, allow_selected: bool = False):
        self.rule = rule or RecalibrationRule()
        self.allow_selected = allow_selected
        self._X: list[Any] = []
        self._y: list[np.ndarray] = []
        self._origin: list[np.ndarray] = []
        self._n = 0
        self.n_skipped = 0
        self.n_recalibrations = 0
        self.current: Calibration | None = None

    def __len__(self) -> int:
        return self._n

    def add(self, X: Any, y: np.ndarray, origin: np.ndarray | list[str] | str) -> None:
        """Append arrived labelled rows with the origin of each (see ``ALLOWED_ORIGINS``)."""
        y = np.asarray(y)
        if y.size == 0:
            return
        org = (
            np.full(len(y), origin, dtype=object)
            if isinstance(origin, str)
            else np.asarray(origin, dtype=object)
        )
        if org.shape != y.shape or X.shape[0] != y.shape[0]:
            raise ValueError("rows, labels and origins must line up")
        bad = [o for o in set(org.tolist()) if o not in ALLOWED_ORIGINS]
        if bad:
            if ORIGIN_SELECTED in bad and not self.allow_selected:
                raise CalibrationContamination(
                    "a sample chosen by a selector may not enter the calibration buffer "
                    "(exchangeability); only the random reserved slice and the initial "
                    "hold-out are calibration data"
                )
            if any(o != ORIGIN_SELECTED for o in bad):
                raise ValueError(f"unknown calibration origin(s) {bad}")
        self._X.append(X)
        self._y.append(y.astype(np.int8, copy=False))
        self._origin.append(org)
        self._n += len(y)
        self._evict()

    def _evict(self) -> None:
        extra = self._n - self.rule.buffer_size
        while extra > 0 and self._y:
            head = len(self._y[0])
            if head <= extra:
                self._X.pop(0), self._y.pop(0), self._origin.pop(0)
                self._n -= head
                extra -= head
            else:
                self._X[0] = self._X[0][extra:]
                self._y[0] = self._y[0][extra:]
                self._origin[0] = self._origin[0][extra:]
                self._n -= extra
                extra = 0

    def rows(self) -> tuple[Any, np.ndarray]:
        if not self._y:
            raise ValueError("the calibration buffer is empty")
        X = sp.vstack(self._X, format="csr") if sp.issparse(self._X[0]) else np.vstack(self._X)
        return X, np.concatenate(self._y)

    def class_counts(self) -> tuple[int, int]:
        if not self._y:
            return (0, 0)
        y = np.concatenate(self._y)
        return int((y == 0).sum()), int((y == 1).sum())

    def recalibrate(
        self, own_scores: Callable[[Any, np.ndarray], np.ndarray], slot_index: int
    ) -> Calibration | None:
        """Recompute the calibration under the current model, or keep the previous one.

        ``own_scores(X, y)`` returns each row's nonconformity for its own label under the
        current model. Returns the calibration in force (``None`` before the first).
        """
        n0, n1 = self.class_counts()
        if min(n0, n1) < self.rule.min_per_class:
            self.n_skipped += 1
            return self.current
        X, y = self.rows()
        cal = ClassCalibration.from_scores(own_scores(X, y), y)
        self.current = Calibration(cal, len(y), slot_index)
        self.n_recalibrations += 1
        return self.current
