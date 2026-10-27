"""Class-conditional (Mondrian) conformal p-values and credibility.

For a class ``c`` the calibration set keeps the nonconformity scores ``s_i`` of the labelled
calibration samples whose true class is ``c``. A new sample ``x`` with nonconformity ``s_c(x)``
for class ``c`` gets

    p_c(x) = (1 + #{i : y_i = c, s_i >= s_c(x)}) / (n_c + 1)

(build guide section 5, PROTOCOL.md section 4). The comparison is inclusive: a tie counts as
"at least as nonconforming". A class with no calibration sample has ``n_c = 0`` and gets
``p = 1``: nothing in the calibration set says the sample is unusual. The credibility of a
sample is the p-value of its predicted class; a low credibility says the sample looks unlike
what the model knows for that class.

Validity (``P(p <= eps) <= eps`` for a sample exchangeable with the calibration samples of its
class) holds only when the calibration samples are a fair draw from the current data. That is
why calibration labels come only from the reserved random slice (``recalibrate.py``).

Pure numpy; no model code and no labels of the evaluated slot.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ClassCalibration:
    """Sorted nonconformity scores of the calibration samples, one array per class."""

    scores: tuple[np.ndarray, ...]  # index = class; each sorted ascending

    @property
    def n_classes(self) -> int:
        return len(self.scores)

    def counts(self) -> tuple[int, ...]:
        return tuple(int(len(s)) for s in self.scores)

    @classmethod
    def from_scores(
        cls, own_scores: np.ndarray, labels: np.ndarray, n_classes: int = 2
    ) -> ClassCalibration:
        """``own_scores[i]`` is the nonconformity of calibration sample ``i`` for its own label."""
        s = np.asarray(own_scores, dtype=np.float64)
        y = np.asarray(labels)
        if s.ndim != 1 or s.shape != y.shape:
            raise ValueError("scores and labels must be one-dimensional and the same length")
        if len(y) and (y.min() < 0 or y.max() >= n_classes):
            raise ValueError(f"labels must lie in 0..{n_classes - 1}")
        if not np.isfinite(s).all():
            raise ValueError("calibration scores must be finite")
        return cls(tuple(np.sort(s[y == c]) for c in range(n_classes)))


def pvalues(calibration: ClassCalibration, test_scores: np.ndarray) -> np.ndarray:
    """Mondrian p-values, shape ``(n, n_classes)``.

    ``test_scores[:, c]`` is the nonconformity ``s_c(x)`` of each test sample for class ``c``.
    """
    t = np.asarray(test_scores, dtype=np.float64)
    if t.ndim != 2 or t.shape[1] != calibration.n_classes:
        raise ValueError(f"test scores must have shape (n, {calibration.n_classes})")
    if not np.isfinite(t).all():
        raise ValueError("test scores must be finite")
    out = np.empty_like(t)
    for c, cal in enumerate(calibration.scores):
        n_c = len(cal)
        # #{s_i >= s} = n_c - #{s_i < s}: searchsorted 'left' counts the strictly smaller ones
        at_least = n_c - np.searchsorted(cal, t[:, c], side="left")
        out[:, c] = (1.0 + at_least) / (n_c + 1.0)
    return out


def credibility(p: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    """The p-value of the predicted class, per sample."""
    p = np.asarray(p)
    pred = np.asarray(predicted, dtype=np.int64)
    if p.ndim != 2 or pred.shape != (p.shape[0],):
        raise ValueError("p must be (n, classes) and predicted must be (n,)")
    if len(pred) and (pred.min() < 0 or pred.max() >= p.shape[1]):
        raise ValueError("predicted class outside the p-value columns")
    return p[np.arange(len(pred)), pred]
