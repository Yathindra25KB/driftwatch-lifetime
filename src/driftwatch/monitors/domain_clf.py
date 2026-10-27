"""Domain classifier: can a classifier tell the reference from the current slot? (addendum v3)

Per slot: the reference sample (label 0) and a seeded subsample of the slot (label 1), a
logistic regression (C = 1, features scaled inside each fold), 5-fold stratified
cross-validated AUC. Under no drift the AUC is near 0.5.

Permutation null, capped (ADR-0010): computed **once per window**, before any evaluation
slot, on the initial reference (the window's time-ordered hold-out): ``n_null`` times, two
disjoint random halves of it get domain labels 0 and 1 and the same cross-validated AUC is
computed. ``p = (1 + #{null AUC >= observed}) / (n_null + 1)``. The null does not depend on
the seed or the policy; the same null serves every reference of the window (an approximation
recorded in ADR-0010). The pair statistic depends only on features and seeded draws, so it is
cached.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.sparse as sp
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from driftwatch.monitors.base import (
    ALPHA,
    N_SUB,
    Alarm,
    MonitorState,
    SlotView,
    cache_key,
    current_sample,
    make_alarm,
    rng_for,
    undecided,
)

_NULL_SEED = 0  # the null is shared by every seed of a window


def _stack(a: Any, b: Any) -> Any:
    if sp.issparse(a) or sp.issparse(b):
        return sp.vstack([sp.csr_matrix(a), sp.csr_matrix(b)], format="csr")
    return np.vstack([np.asarray(a), np.asarray(b)])


def cv_auc(a: Any, b: Any, folds: int, rng: np.random.Generator) -> float:
    """Cross-validated AUC of a logistic regression telling rows of ``a`` from rows of ``b``."""
    X = _stack(a, b)
    y = np.r_[np.zeros(a.shape[0], dtype=np.int8), np.ones(b.shape[0], dtype=np.int8)]
    k = int(min(folds, a.shape[0], b.shape[0]))
    if k < 2:
        raise ValueError("each side needs at least two rows for cross-validation")
    # lbfgs (the detector LR's solver): about 6x faster than liblinear on 1,000 x 2,381 dense
    # rows; an unconverged fit after 200 iterations is accepted (a monitor statistic, not a
    # model), so its warning is silenced here
    clf = make_pipeline(
        StandardScaler(with_mean=not sp.issparse(X)),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=200),
    )
    cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=int(rng.integers(2**31 - 1)))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        score = cross_val_predict(clf, X, y, cv=cv, method="decision_function")
    return float(roc_auc_score(y, score))


@dataclass(frozen=True)
class DomainClassifier:
    folds: int = 5
    n_null: int = 99
    n_sub: int = N_SUB
    alpha: float = ALPHA
    name: str = "domain_clf"

    @property
    def settings(self) -> str:
        return f"f{self.folds}-b{self.n_null}-n{self.n_sub}"

    def null_key(self, state: MonitorState) -> str:
        return f"{self.name}|{self.settings}|{state.window_key}|null"

    def start(self, state: MonitorState, train_X: Any, train_y: np.ndarray, ref_full_X: Any):
        key = self.null_key(state)
        if key in state.cache:
            state.fitted["null"] = np.asarray(state.cache[key], dtype=np.float64)
            return
        n_rows = ref_full_X.shape[0]
        half = min(self.n_sub, n_rows // 2)
        if half < 2:
            state.fitted["null"] = None  # too few hold-out rows: the monitor cannot decide
            return
        null = np.empty(self.n_null)
        for b in range(self.n_null):
            rng = rng_for(_NULL_SEED, state.window_key, "dc-null", b)
            pick = rng.choice(n_rows, size=2 * half, replace=False)
            null[b] = cv_auc(ref_full_X[np.sort(pick[:half])], ref_full_X[np.sort(pick[half:])],
                             self.folds, rng)  # fmt: skip
        state.fitted["null"] = null
        state.cache[key] = null.tolist()

    def update(self, view: SlotView, state: MonitorState) -> Alarm:
        null = state.fitted.get("null")
        if null is None or state.ref_X is None:
            return undecided(self.name, view, state, self.alpha)
        key = cache_key(self.name, self.settings, state, view)
        hit = state.cache.get(key)
        if hit is None:
            _, cur = current_sample(view, state, self.n_sub)
            if min(state.ref_X.shape[0], cur.shape[0]) < 2:
                return undecided(self.name, view, state, self.alpha)
            rng = rng_for(state.seed, state.window_key, "dc-cv", state.ref_slot, view.slot_id)
            auc = cv_auc(state.ref_X, cur, self.folds, rng)
            p = (1.0 + float((null >= auc - 1e-12).sum())) / (len(null) + 1.0)
            hit = [auc, p, int(state.ref_X.shape[0]), int(cur.shape[0])]
            state.cache[key] = hit
        auc, p, n_ref, n_cur = hit
        return make_alarm(self.name, view, state, self.alpha, auc, p, n_ref, n_cur)
