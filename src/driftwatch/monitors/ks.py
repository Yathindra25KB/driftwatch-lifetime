"""Two-sample KS on the top-k features, Holm-corrected (addendum v3).

At the start of each window the ``k`` features with the largest absolute standardised
class-mean difference on the window's proper training rows are chosen (training labels of the
initial window only; the evaluated slots' labels are never seen). They stay fixed for the
window, so the statistic of a pair (reference slot, current slot) does not depend on the
policy and is cached.

Per slot: a two-sample KS test per chosen feature between the reference sample and a seeded
subsample of the slot, Holm adjustment over the ``k`` tests; the slot alarms when the smallest
adjusted p-value is at most ``alpha``. KS on discrete (count) features is conservative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import scipy.sparse as sp
from scipy.stats import ks_2samp

from driftwatch.monitors.base import (
    ALPHA,
    N_SUB,
    Alarm,
    MonitorState,
    SlotView,
    cache_key,
    current_sample,
    dense,
    make_alarm,
)


def top_features(X: Any, y: np.ndarray, k: int) -> np.ndarray:
    """Indices of the ``k`` features with the largest |standardised class-mean difference|."""
    y = np.asarray(y)
    if not ((y == 0).any() and (y == 1).any()):
        raise ValueError("feature choice needs both classes in the training rows")
    stats = []
    for c in (0, 1):
        Xc = X[np.flatnonzero(y == c)]
        if sp.issparse(Xc):
            m = np.asarray(Xc.mean(axis=0)).ravel()
            m2 = np.asarray(Xc.multiply(Xc).mean(axis=0)).ravel()
        else:
            Xc = np.asarray(Xc, dtype=np.float64)
            m, m2 = Xc.mean(axis=0), (Xc * Xc).mean(axis=0)
        stats.append((m, np.maximum(m2 - m * m, 0.0)))
    (m0, v0), (m1, v1) = stats
    pooled = np.sqrt((v0 + v1) / 2.0)
    score = np.where(pooled > 0, np.abs(m1 - m0) / np.where(pooled > 0, pooled, 1.0), 0.0)
    order = np.lexsort((np.arange(score.size), -score))  # largest first, ties by index
    return np.sort(order[: min(k, score.size)])


@dataclass(frozen=True)
class KSTopK:
    k: int = 20
    alpha: float = ALPHA
    n_sub: int = N_SUB
    name: str = "ks"

    @property
    def settings(self) -> str:
        return f"k{self.k}-n{self.n_sub}"

    def start(
        self, state: MonitorState, train_X: Any, train_y: np.ndarray, ref_full_X: Any
    ) -> None:
        state.fitted["features"] = top_features(train_X, train_y, self.k)

    def update(self, view: SlotView, state: MonitorState) -> Alarm:
        key = cache_key(self.name, self.settings, state, view)
        hit = state.cache.get(key)
        if hit is None:
            feats = state.fitted["features"]
            ref = dense(state.ref_X[:, feats])
            _, cur_rows = current_sample(view, state, self.n_sub)
            cur = dense(cur_rows[:, feats])
            d_max, p_min = 0.0, 1.0
            for j in range(len(feats)):
                res = ks_2samp(ref[:, j], cur[:, j])
                d_max = max(d_max, float(res.statistic))
                p_min = min(p_min, float(res.pvalue))
            p_adj = min(1.0, len(feats) * p_min)  # the smallest Holm-adjusted p-value
            hit = [d_max, p_adj, int(ref.shape[0]), int(cur.shape[0])]
            state.cache[key] = hit
        d_max, p_adj, n_ref, n_cur = hit
        return make_alarm(self.name, view, state, self.alpha, d_max, p_adj, n_ref, n_cur)
