"""The leakage canary (Build Guide section 8): shuffle timestamps, AUT must move.

For a chosen window it measures three things with one trivial model (nearest class
centroid, fitted on the window's training slots only):

1. ``aut_true``: AUT of per-slot malware F1 over the window's evaluation slots, sliced by
   the real timestamps (C1-C3 enforced by the slicer).
2. ``aut_shuffled``: the same after the window's rows swap timestamps at random, on the same
   slot grid. Training and evaluation slots become exchangeable.
3. ``f1_random``: a random split of the same rows (same training size, malware-only
   subsampling of the test side to the same ratio): what a time-blind evaluation reports.

If time matters, ``aut_true`` sits below ``f1_random`` and shuffling must close most of that
gap. If shuffling does not move AUT toward ``f1_random``, the slicer is not using time the way
it claims (stop rule: fix the slicer first). If ``aut_true`` is already at the random-split
level there is no gap to close (``NO_GAP``): either nothing decays, or something leaks. An
AUT above 0.9 on a hard split is a leakage warning in its own right (guide section 9).

AUT here is the guide's formula ``1/(N-1) * sum (f_k + f_{k+1}) / 2``; PROTOCOL D17 asks
Phase 4 to check it against TESSERACT v4. The canary only compares like with like.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import scipy.sparse as sp

from driftwatch.data import constraints
from driftwatch.data.slicer import (
    SlotSource,
    WindowSpec,
    _stack,
    plan_slots,
    plan_windows,
    slice_windows,
)
from driftwatch.data.tables import ExplicitScheme, TableSource

LEAKAGE_AUT = 0.90  # guide section 9: treat any AUT above 0.9 on a hard split as a warning


class CanaryError(Exception):
    """The canary cannot be computed (no window, one class missing, too few slots)."""


# --- the trivial model and the metric -------------------------------------------------------


def f1_malware(y_true: Any, y_pred: Any) -> float:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    denom = 2 * tp + fp + fn
    return 0.0 if denom == 0 else 2 * tp / denom


def aut(f1_per_slot: Sequence[float]) -> float:
    """``AUT(f, N) = 1/(N-1) * sum_{k=1..N-1} (f_k + f_{k+1}) / 2`` (guide section 3)."""
    f = np.asarray(f1_per_slot, dtype=float)
    if f.size < 2:
        raise CanaryError("AUT needs at least two evaluation slots")
    return float(np.mean((f[:-1] + f[1:]) / 2.0))


def _column_mean(X: Any) -> np.ndarray:
    if sp.issparse(X):
        return np.asarray(X.mean(axis=0), dtype=np.float64).ravel()
    return np.asarray(X, dtype=np.float32).mean(axis=0, dtype=np.float64)


class NearestCentroid:
    """Score = projection onto (malware mean - benign mean), threshold at the midpoint."""

    def fit(self, X: Any, y: Any) -> NearestCentroid:
        y = np.asarray(y)
        if not ((y == 1).any() and (y == 0).any()):
            raise CanaryError("the training window needs both classes")
        mu1, mu0 = _column_mean(X[y == 1]), _column_mean(X[y == 0])
        self.w_ = mu1 - mu0
        self.b_ = -0.5 * float((mu1 + mu0) @ self.w_)
        return self

    def decision_function(self, X: Any) -> np.ndarray:
        scores = X.dot(self.w_) if sp.issparse(X) else np.asarray(X, dtype=np.float64) @ self.w_
        return np.asarray(scores).ravel() + self.b_

    def predict(self, X: Any) -> np.ndarray:
        return (self.decision_function(X) > 0.0).astype(np.int8)


def shuffle_timestamps(table: pd.DataFrame, seed: int, ts_col: str = "ts") -> pd.DataFrame:
    """A copy with the timestamp column permuted across rows (labels and features stay)."""
    out = table.copy()
    perm = np.random.default_rng(seed).permutation(len(table))
    out[ts_col] = table[ts_col].to_numpy()[perm]
    return out


# --- the canary -----------------------------------------------------------------------------


@dataclass(frozen=True)
class CanaryResult:
    verdict: str  # PASS | FAIL | NO_GAP
    aut_true: float
    aut_shuffled: float
    f1_random: float
    gap: float  # f1_random - aut_true
    closure: float | None  # share of the gap that shuffling closes; None when there is no gap
    leakage_warning: bool  # aut_true above 0.9
    n_windows: int
    min_gap: float
    min_closure: float
    per_window: tuple[dict[str, Any], ...]

    def as_record(self) -> dict[str, Any]:
        record = dataclasses.asdict(self)
        record["per_window"] = list(self.per_window)
        return record


def _spread(n: int, k: int) -> list[int]:
    """Up to k positions spread evenly over range(n), first and last included."""
    if n <= k:
        return list(range(n))
    return sorted({round(i * (n - 1) / (k - 1)) for i in range(k)}) if k > 1 else [0]


def _eval_f1(model: NearestCentroid, slots: Any) -> list[float]:
    return [f1_malware(s.y, model.predict(s.X)) for s in slots]


def _one_window(
    source: SlotSource, spec: WindowSpec, position: int, seed: int
) -> dict[str, float | int | str]:
    (window,) = slice_windows(source, spec, only=[position])
    plan = window.plan
    # The honest training size comes from the plan, not from what the slicer handed back:
    # a leaky slicer returns more rows, and the random-split baseline must not inherit that.
    counts = {p.ref.slot_id: p.n_rows for p in plan_slots(source, spec)}
    n_train = sum(counts[ref.slot_id] for ref in plan.train)
    model = NearestCentroid().fit(window.train.X, window.train.y)
    f1_true = _eval_f1(model, window.eval_slots())
    aut_true = aut(f1_true)

    # The window's raw rows on the window's own slot grid, for the other two conditions.
    raw = [*window.train.slots, *(source.load_slot(ref.slot_id) for ref in plan.eval)]
    X = _stack([r.X for r in raw])
    y = np.concatenate([r.y for r in raw])
    ts = np.concatenate([r.ts for r in raw])
    row_id = np.concatenate([r.row_id for r in raw])
    del window, raw
    _, first = np.unique(row_id, return_index=True)  # a leaky slicer repeats rows: keep one
    if first.size != row_id.size:
        first.sort()
        X, y, ts, row_id = X[first], y[first], ts[first], row_id[first]

    rng = np.random.default_rng([seed, position])
    table = pd.DataFrame({"ts": rng.permutation(ts), "label": y, "row_id": row_id})
    scheme = ExplicitScheme([*plan.train, *plan.eval])
    shuffled_source = TableSource(table, scheme, x=X, name=f"{source.name}-shuffled")
    shuffled_spec = dataclasses.replace(spec, nE=len(plan.eval), stride=1, min_malware=1)
    shuffled = list(slice_windows(shuffled_source, shuffled_spec))
    if len(shuffled) != 1:
        raise CanaryError(f"{plan.window_id}: the shuffled pool did not form one window")
    s_model = NearestCentroid().fit(shuffled[0].train.X, shuffled[0].train.y)
    aut_shuffled = aut(_eval_f1(s_model, shuffled[0].eval_slots()))

    perm = rng.permutation(len(y))
    train_idx, test_idx = perm[:n_train], perm[n_train:]
    kept = constraints.subsample_malware(
        y[test_idx], spec.target_ratio, spec.seed, f"canary-random:{position}"
    )
    r_model = NearestCentroid().fit(X[train_idx], y[train_idx])
    test_rows = test_idx[kept]
    f1_random = f1_malware(y[test_rows], r_model.predict(X[test_rows]))
    return {
        "window_id": plan.window_id,
        "n_train_slots": len(plan.train),
        "n_eval_slots": len(plan.eval),
        "aut_true": aut_true,
        "aut_shuffled": aut_shuffled,
        "f1_random": f1_random,
    }


def run_canary(
    source: SlotSource,
    spec: WindowSpec,
    *,
    seed: int = 0,
    max_windows: int = 3,
    min_gap: float = 0.05,
    min_closure: float = 0.5,
) -> CanaryResult:
    """Run the canary on up to ``max_windows`` windows spread over the schedule."""
    n = len(plan_windows(plan_slots(source, spec), spec).windows)
    if n == 0:
        raise CanaryError("the spec yields no window on this source: nothing to test")
    rows = tuple(_one_window(source, spec, p, seed) for p in _spread(n, max_windows))
    mean = {
        k: float(np.mean([r[k] for r in rows])) for k in ("aut_true", "aut_shuffled", "f1_random")
    }
    gap = mean["f1_random"] - mean["aut_true"]
    if gap < min_gap:
        verdict, closure = "NO_GAP", None
    else:
        closure = (mean["aut_shuffled"] - mean["aut_true"]) / gap
        verdict = "PASS" if closure >= min_closure else "FAIL"
    return CanaryResult(
        verdict=verdict,
        gap=gap,
        closure=closure,
        leakage_warning=mean["aut_true"] > LEAKAGE_AUT,
        n_windows=len(rows),
        min_gap=min_gap,
        min_closure=min_closure,
        per_window=rows,
        **mean,
    )
