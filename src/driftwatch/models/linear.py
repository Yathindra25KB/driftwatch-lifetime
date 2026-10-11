"""Logistic regression with feature scaling fitted on the training window only.

Scaling policy (ADR-0006): ``StandardScaler`` built inside ``fit`` from the training rows,
centred only for dense features. Sparse input (LAMDA) is scaled by the standard deviation
without centring, so it stays sparse. Features with zero variance are left unscaled.
Dense input keeps its float32 dtype (moments are accumulated in float64).

The fit is L2-regularised lbfgs with a fixed iteration cap. A fit that stops at the cap is
recorded as ``converged = False`` in ``fit_info``, never hidden.
"""

from __future__ import annotations

import warnings
from typing import Any

import numpy as np
import scipy.sparse as sp
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from driftwatch.models.base import DEFAULT_THRESHOLD, Detector

SCALING = "standard(with_mean=dense_only)"


class LogisticDetector(Detector):
    name = "lr"

    def __init__(
        self,
        seed: int,
        threshold: float = DEFAULT_THRESHOLD,
        C: float = 1.0,
        max_iter: int = 1000,  # ADR-0006: 300 stopped short of convergence on LAMDA
        tol: float = 1e-4,
        scaling: str = SCALING,
    ) -> None:
        super().__init__(seed, threshold)
        if C <= 0 or max_iter < 1 or tol <= 0:
            raise ValueError("C and tol must be positive and max_iter at least 1")
        if scaling != SCALING:
            raise ValueError(f"scaling policy {scaling!r} is not implemented; only {SCALING!r}")
        self.C, self.max_iter, self.tol = float(C), int(max_iter), float(tol)

    def _params(self) -> dict[str, Any]:
        return {"C": self.C, "max_iter": self.max_iter, "tol": self.tol, "scaling": SCALING}

    @property
    def seed_sensitive(self) -> bool:
        return False  # lbfgs on a convex objective: the seed is not used

    @staticmethod
    def _prepare(X: Any) -> Any:
        if sp.issparse(X):
            return X.tocsr()
        # float32 stays float32: StandardScaler accumulates in float64, and a float64 copy of
        # a dense BODMAS window would double the peak memory on the 8 GB laptop.
        arr = np.asarray(X)
        return arr if arr.dtype in (np.float32, np.float64) else arr.astype(np.float32)

    def _fit(self, X: Any, y: np.ndarray) -> dict[str, Any]:
        X = self._prepare(X)
        self.scaler_ = StandardScaler(with_mean=not sp.issparse(X))
        Xs = self.scaler_.fit_transform(X)
        self.clf_ = LogisticRegression(
            C=self.C,
            solver="lbfgs",
            max_iter=self.max_iter,
            tol=self.tol,
            random_state=self.seed,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)  # recorded below instead
            self.clf_.fit(Xs, y)
        n_iter = int(np.max(self.clf_.n_iter_))
        return {"n_iter": n_iter, "converged": n_iter < self.max_iter}

    def _score(self, X: Any) -> np.ndarray:
        return self.clf_.predict_proba(self.scaler_.transform(self._prepare(X)))[:, 1]
