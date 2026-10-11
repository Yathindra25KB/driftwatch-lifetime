"""Logistic regression and LightGBM behind one fit/predict_proba interface (Phase 4)."""

from __future__ import annotations

import inspect
from typing import Any

from driftwatch.models.base import Detector
from driftwatch.models.lgbm import LightGBMDetector
from driftwatch.models.linear import LogisticDetector

_REGISTRY: dict[str, type[Detector]] = {"lr": LogisticDetector, "lgbm": LightGBMDetector}
MODEL_NAMES = tuple(_REGISTRY)


def make_model(spec: dict[str, Any], seed: int) -> Detector:
    """Build a detector from ``{"name": ..., **hyperparameters}`` and an explicit seed."""
    params = dict(spec)
    name = params.pop("name", None)
    if name not in _REGISTRY:
        raise ValueError(f"unknown model {name!r}; choose from {sorted(_REGISTRY)}")
    cls = _REGISTRY[name]
    allowed = set(inspect.signature(cls.__init__).parameters) - {"self", "seed"}
    extra = sorted(set(params) - allowed)
    if extra:
        raise ValueError(
            f"unknown hyperparameter(s) for {name!r}: {extra}; allowed {sorted(allowed)}"
        )
    return cls(seed=seed, **params)
