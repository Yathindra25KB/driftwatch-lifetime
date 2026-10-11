"""The detector interface: fit on one training window, score with a fixed threshold.

- ``fit(X, y, window_id)`` is the only place labels enter. Scoring takes features only.
- The decision threshold is fixed at construction (default 0.5, ADR-0006). A threshold tuned
  on data may use only the final training slot, and is passed in here, never learned here.
- A fitted detector carries the id of the window it was fitted on. Passing another window's
  id to ``predict_proba`` raises, so a model cannot silently score under the wrong window.
- Scalers and any other fitted state are built inside ``_fit`` from the training rows only.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Self

import numpy as np

DEFAULT_THRESHOLD = 0.5


class NotFittedError(RuntimeError):
    """A detector was asked to score before it was fitted."""


class WindowMismatch(RuntimeError):
    """A detector fitted on one window was asked to score under another window's id."""


class Detector(ABC):
    name: ClassVar[str]

    def __init__(self, seed: int, threshold: float = DEFAULT_THRESHOLD) -> None:
        if not 0.0 < float(threshold) < 1.0:
            raise ValueError(f"threshold must lie strictly between 0 and 1, got {threshold!r}")
        if int(seed) < 0:
            raise ValueError("seed must be non-negative")
        self.seed = int(seed)
        self.threshold = float(threshold)
        self.fitted_window_id: str | None = None
        self.fit_info: dict[str, Any] = {}

    # -- configuration -----------------------------------------------------------------------

    @abstractmethod
    def _params(self) -> dict[str, Any]:
        """The model's own hyperparameters (everything but name, threshold and seed)."""

    def spec(self) -> dict[str, Any]:
        """Name, threshold and hyperparameters: what ``make_model`` needs, and what is logged."""
        return {"name": self.name, "threshold": self.threshold, **self._params()}

    # -- fitting and scoring -----------------------------------------------------------------

    @abstractmethod
    def _fit(self, X: Any, y: np.ndarray) -> dict[str, Any]:
        """Fit on the training window; return extra facts for ``fit_info``."""

    @abstractmethod
    def _score(self, X: Any) -> np.ndarray:
        """P(malware) for each row, float64."""

    def fit(self, X: Any, y: Any, window_id: str) -> Self:
        labels = np.asarray(y)
        if labels.ndim != 1 or X.shape[0] != labels.shape[0]:
            raise ValueError(f"features {tuple(X.shape)} and labels {labels.shape} do not line up")
        if not np.isin(labels, (0, 1)).all():
            raise ValueError("labels must be 0 or 1")
        if not ((labels == 1).any() and (labels == 0).any()):
            raise ValueError("the training window needs both classes")
        self.fitted_window_id = None  # a failed refit must not leave a stale id behind
        t0 = time.perf_counter()
        extra = self._fit(X, labels.astype(np.int8, copy=False))
        self.fit_info = {
            "fit_seconds": time.perf_counter() - t0,
            "n_train": int(labels.shape[0]),
            "n_features": int(X.shape[1]),
            "window_id": window_id,
            **extra,
        }
        self.fitted_window_id = window_id
        return self

    def _check(self, window_id: str | None) -> None:
        if self.fitted_window_id is None:
            raise NotFittedError(f"{self.name} has not been fitted")
        if window_id is not None and window_id != self.fitted_window_id:
            raise WindowMismatch(
                f"{self.name} was fitted on {self.fitted_window_id!r}, asked to score under "
                f"{window_id!r}"
            )

    def predict_proba(self, X: Any, window_id: str | None = None) -> np.ndarray:
        self._check(window_id)
        p = np.asarray(self._score(X), dtype=np.float64)
        if p.shape != (X.shape[0],):
            raise RuntimeError(f"{self.name} returned scores of shape {p.shape}")
        return p

    def decide(self, proba: np.ndarray) -> np.ndarray:
        """Malware (1) when P(malware) is strictly above the fixed threshold."""
        return (np.asarray(proba) > self.threshold).astype(np.int8)

    def predict(self, X: Any, window_id: str | None = None) -> np.ndarray:
        return self.decide(self.predict_proba(X, window_id))

    @property
    def seed_sensitive(self) -> bool:
        """False when the fit cannot depend on the seed, so one fit serves every seed."""
        return True
