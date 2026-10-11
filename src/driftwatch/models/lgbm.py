"""LightGBM with two fixed profiles.

``default`` is LightGBM's library defaults (100 trees). ``fast`` keeps the tree count and
shape and lowers the cost of a fit: 63 histogram bins, half the features per tree and 80%
row bagging. Neither is tuned (PREREG): the values are fixed before E0 and recorded there.

Determinism: ``deterministic=True``, ``force_col_wise=True``, a fixed thread count and the
run's seed. The count of threads is part of the logged spec because LightGBM's results are
only guaranteed identical for a fixed number of threads.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import scipy.sparse as sp
from lightgbm import LGBMClassifier

from driftwatch.models.base import DEFAULT_THRESHOLD, Detector

PROFILES: dict[str, dict[str, Any]] = {
    "default": {
        "n_estimators": 100,
        "learning_rate": 0.1,
        "num_leaves": 31,
        "min_child_samples": 20,
        "max_bin": 255,
        "colsample_bytree": 1.0,
        "subsample": 1.0,
        "subsample_freq": 0,
    },
    "fast": {
        "n_estimators": 100,
        "learning_rate": 0.1,
        "num_leaves": 31,
        "min_child_samples": 20,
        "max_bin": 63,
        "colsample_bytree": 0.5,
        "subsample": 0.8,
        "subsample_freq": 1,
    },
}


def _as_float32(X: Any) -> Any:
    if sp.issparse(X):
        return X.tocsr().astype(np.float32, copy=False)
    return np.asarray(X, dtype=np.float32)


class LightGBMDetector(Detector):
    name = "lgbm"

    def __init__(
        self,
        seed: int,
        threshold: float = DEFAULT_THRESHOLD,
        profile: str = "fast",
        n_jobs: int = 4,
    ) -> None:
        super().__init__(seed, threshold)
        if profile not in PROFILES:
            raise ValueError(
                f"unknown LightGBM profile {profile!r}; choose from {sorted(PROFILES)}"
            )
        if n_jobs < 1:
            raise ValueError("n_jobs must be at least 1")
        self.profile, self.n_jobs = profile, int(n_jobs)

    def _params(self) -> dict[str, Any]:
        return {"profile": self.profile, "n_jobs": self.n_jobs}

    @property
    def seed_sensitive(self) -> bool:
        p = PROFILES[self.profile]
        return p["subsample"] < 1.0 or p["colsample_bytree"] < 1.0  # bagging uses the seed

    def _fit(self, X: Any, y: np.ndarray) -> dict[str, Any]:
        self.clf_ = LGBMClassifier(
            **PROFILES[self.profile],
            deterministic=True,
            force_col_wise=True,
            n_jobs=self.n_jobs,
            random_state=self.seed,
            verbose=-1,
        )
        self.clf_.fit(_as_float32(X), y)
        return {"n_trees": int(self.clf_.booster_.num_trees())}

    def _score(self, X: Any) -> np.ndarray:
        return self.clf_.predict_proba(_as_float32(X))[:, 1]
