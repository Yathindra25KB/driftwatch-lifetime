"""Maximum mean discrepancy with an RBF kernel and a permutation threshold (addendum v3).

The guide asks for MMD "on embeddings". Logistic regression and LightGBM have no learned
embedding, so the representation is (ADR-0010): a TruncatedSVD projection fitted, without
labels, on the window's proper training rows, plus the logit of the malware probability under
the model in force. Both sides (the reference sample and the current slot) are scored by the
same model, so a refit changes the representation of both. Columns are standardised with the
reference sample's mean and standard deviation; the kernel bandwidth is the median pairwise
distance within the reference sample (median heuristic).

Per slot: ``n_sub`` rows per side, the biased MMD^2 estimate, and ``n_perm`` seeded
permutations of the pooled rows; ``p = (1 + #{perm >= observed}) / (n_perm + 1)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.decomposition import TruncatedSVD

from driftwatch.monitors.base import (
    ALPHA,
    Alarm,
    MonitorState,
    SlotView,
    make_alarm,
    rng_for,
    subsample_index,
    undecided,
)

_CLIP = 1e-6


def _logit(p: np.ndarray) -> np.ndarray:
    q = np.clip(np.asarray(p, dtype=np.float64), _CLIP, 1.0 - _CLIP)
    return np.log(q / (1.0 - q))


def mmd_permutation(
    a: np.ndarray, b: np.ndarray, n_perm: int, rng: np.random.Generator
) -> tuple[float, float]:
    """(biased MMD^2, permutation p-value) of two samples of row vectors."""
    z = np.vstack([a, b])
    n, m = len(a), len(b)
    sq = (z * z).sum(axis=1)
    d2 = np.maximum(sq[:, None] + sq[None, :] - 2.0 * z @ z.T, 0.0)
    ref_d2 = d2[:n, :n][np.triu_indices(n, 1)]
    med = float(np.median(ref_d2)) if ref_d2.size else 0.0
    if med <= 0.0:
        med = float(np.median(d2[np.triu_indices(n + m, 1)])) or 1.0
    K = np.exp(-d2 / med)  # exp(-d^2 / (2 sigma^2)) with sigma^2 = median(d^2) / 2

    def weights(first: np.ndarray) -> np.ndarray:
        w = np.full(n + m, -1.0 / m)
        w[first] = 1.0 / n
        return w

    obs_w = weights(np.arange(n))
    observed = float(obs_w @ K @ obs_w)
    W = np.empty((n + m, n_perm))
    for b_i in range(n_perm):
        W[:, b_i] = weights(rng.permutation(n + m)[:n])
    null = np.einsum("ij,ij->j", W, K @ W)
    p = (1.0 + float((null >= observed - 1e-12).sum())) / (n_perm + 1.0)
    return observed, p


@dataclass(frozen=True)
class MMD:
    n_components: int = 16
    n_sub: int = 200
    n_perm: int = 199
    alpha: float = ALPHA
    name: str = "mmd"

    def start(self, state: MonitorState, train_X: Any, train_y: np.ndarray, ref_full_X: Any):
        k = max(1, min(self.n_components, train_X.shape[1] - 1))
        svd = TruncatedSVD(n_components=k, random_state=int(state.seed))
        svd.fit(train_X)
        state.fitted["svd"] = svd

    def _embed(self, state: MonitorState, X: Any, proba: np.ndarray) -> np.ndarray:
        proj = state.fitted["svd"].transform(X)
        return np.column_stack([proj, _logit(proba)])

    def update(self, view: SlotView, state: MonitorState) -> Alarm:
        if view.proba is None or view.ref_proba is None or state.ref_X is None:
            return undecided(self.name, view, state, self.alpha)
        rng_ref = rng_for(state.seed, state.window_key, "mmd-ref", state.ref_slot)
        rng_cur = rng_for(state.seed, state.window_key, "mmd-cur", view.slot_id)
        ri = subsample_index(state.ref_X.shape[0], self.n_sub, rng_ref)
        ci = subsample_index(view.X.shape[0], self.n_sub, rng_cur)
        ref = self._embed(state, state.ref_X[ri], np.asarray(view.ref_proba)[ri])
        cur = self._embed(state, view.X[ci], np.asarray(view.proba)[ci])
        mu, sd = ref.mean(axis=0), ref.std(axis=0)
        sd = np.where(sd > 0, sd, 1.0)
        rng = rng_for(state.seed, state.window_key, "mmd-perm", state.ref_slot, view.slot_id)
        stat, p = mmd_permutation((ref - mu) / sd, (cur - mu) / sd, self.n_perm, rng)
        return make_alarm(self.name, view, state, self.alpha, stat, p, len(ri), len(ci))
