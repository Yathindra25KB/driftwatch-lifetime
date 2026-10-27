"""Pluggable nonconformity scores: ``s_c(x)`` is how unlike class ``c`` a sample looks.

Two scores (build guide section 5; a research variable, compared in E3):

- :class:`ProbabilityScore`: one minus the model's probability of the class,
  ``s_1 = 1 - P(malware | x)`` and ``s_0 = P(malware | x)``. Needs only the detector's score.
- :class:`CentroidScore`: the Euclidean distance from a sample to the centroid of class ``c``
  in feature space (after an optional transform such as the detector's scaler). The centroids
  are fitted on the **current training rows only** (hard rule 5); the object carries the
  window id it was fitted for and refuses to score under another.

Scores take features and probabilities only. Nothing here reads a label of an evaluated
slot; ``fit`` receives the labels of the training pool, which is where labels belong.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import numpy as np
import scipy.sparse as sp


class NonconformityScore(Protocol):
    name: str

    def scores(self, X: Any, proba: np.ndarray) -> np.ndarray:
        """``(n, 2)``: column ``c`` is ``s_c(x)``."""
        ...


class ProbabilityScore:
    name = "probability"

    def scores(self, X: Any, proba: np.ndarray) -> np.ndarray:
        del X  # the score is a function of the model output only
        p = np.asarray(proba, dtype=np.float64)
        if p.ndim != 1 or (p < 0).any() or (p > 1).any():
            raise ValueError("proba must be a vector of probabilities in [0, 1]")
        return np.column_stack([p, 1.0 - p])


class WindowMismatch(RuntimeError):
    """A centroid score fitted for one training window was asked to score under another."""


class CentroidScore:
    """Distance to the class centroid, centroids from the training pool of one window."""

    name = "centroid"
    CHUNK = 4096  # rows transformed at a time

    def __init__(self, transform: Callable[[Any], Any] | None = None) -> None:
        self._transform = transform
        self.centroids_: np.ndarray | None = None
        self._c_sq: np.ndarray | None = None
        self.window_id: str | None = None

    def fit(self, X: Any, y: np.ndarray, window_id: str) -> CentroidScore:
        y = np.asarray(y)
        if X.shape[0] != y.shape[0]:
            raise ValueError("features and labels do not line up")
        if not ((y == 0).any() and (y == 1).any()):
            raise ValueError("a centroid needs at least one training row of each class")
        # chunked: the transformed matrix of a whole window may not fit next to the model
        sums = [None, None]
        counts = [0, 0]
        for lo in range(0, X.shape[0], self.CHUNK):
            Z = self._apply(X[lo : lo + self.CHUNK])
            yc = y[lo : lo + self.CHUNK]
            for c in (0, 1):
                idx = np.flatnonzero(yc == c)
                if len(idx) == 0:
                    continue
                part = np.asarray(Z[idx].sum(axis=0), dtype=np.float64).ravel()
                sums[c] = part if sums[c] is None else sums[c] + part
                counts[c] += len(idx)
        self.centroids_ = np.vstack([sums[c] / counts[c] for c in (0, 1)])
        self._c_sq = (self.centroids_**2).sum(axis=1)
        self.window_id = window_id
        return self

    def _apply(self, X: Any) -> Any:
        Z = self._transform(X) if self._transform is not None else X
        return Z.tocsr() if sp.issparse(Z) else np.asarray(Z, dtype=np.float64)

    def scores(self, X: Any, proba: np.ndarray | None = None, *, window_id: str | None = None):
        if self.centroids_ is None or self._c_sq is None:
            raise RuntimeError("fit the centroid score before scoring")
        if window_id is not None and window_id != self.window_id:
            raise WindowMismatch(f"fitted for {self.window_id!r}, asked for {window_id!r}")
        Z = self._apply(X)
        if sp.issparse(Z):
            x_sq = np.asarray(Z.multiply(Z).sum(axis=1)).ravel()
            cross = np.column_stack([np.asarray(Z @ self.centroids_[c]).ravel() for c in (0, 1)])
        else:
            x_sq = (Z**2).sum(axis=1)
            cross = Z @ self.centroids_.T
        d2 = x_sq[:, None] - 2.0 * cross + self._c_sq[None, :]
        return np.sqrt(np.maximum(d2, 0.0))  # rounding can leave tiny negatives
