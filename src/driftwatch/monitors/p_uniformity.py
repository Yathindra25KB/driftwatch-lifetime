"""Uniformity of conformal p-values, tested against the finite calibration set (addendum v3).

The p-values are **label-free** (ADR-0010), so the monitor needs no label at all, not even of
the calibration rows:

- score ``s(x) = 1 - max(P(malware | x), P(benign | x))`` under the model in force;
- Mondrian by **predicted** class (decision threshold 0.5, ADR-0006): a slot row predicted
  ``c`` is compared with the calibration rows predicted ``c``.

A conformal p-value is ``p(x) = 1 - F_cal(s(x))`` up to ties, where ``F_cal`` is the empirical
distribution of the calibration scores of that class. Its uniformity is therefore the question
"do the slot's scores follow the calibration scores?". A one-sample KS of the p-values against
U(0, 1) treats ``F_cal`` as exact and, with a fixed calibration set of a few hundred rows,
alarmed in 25% of the slots of a no-drift synthetic stream at alpha = 0.01 (tests/
test_monitors.py; ADR-0010). The test used is the two-sample KS between the slot's scores and
the calibration scores, whose null accounts for both sample sizes, per predicted class, with a
Bonferroni correction over the classes present.

The calibration rows are the features of the rows in the calibration buffer: the initial
hold-out plus reserved-slice rows **that have already arrived** through the label queue. Under
delay they are older, which is part of what E4 measures.

Per slot: a seeded subsample of ``n_sub`` rows; the slot alarms when the corrected p-value is
at most ``alpha``. If a predicted class present in the subsample has fewer than
``min_per_class`` calibration rows, the slot is undecided and counted. (The guide's sandbox
used a fraction-of-small-p-values rule that never fired; it is not used.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.stats import ks_2samp

from driftwatch.monitors.base import (
    ALPHA,
    N_SUB,
    Alarm,
    MonitorState,
    SlotView,
    current_sample,
    make_alarm,
    undecided,
)

THRESHOLD = 0.5  # the fixed decision threshold of ADR-0006


def label_free_scores(proba: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(nonconformity 1 - max class probability, predicted class)."""
    p = np.asarray(proba, dtype=np.float64)
    return 1.0 - np.maximum(p, 1.0 - p), (p > THRESHOLD).astype(np.int8)


@dataclass(frozen=True)
class PUniformity:
    n_sub: int = N_SUB
    min_per_class: int = 20
    alpha: float = ALPHA
    name: str = "p_uniformity"

    def start(self, state: MonitorState, train_X: Any, train_y: np.ndarray, ref_full_X: Any):
        return None  # nothing to fit: the reference is the calibration buffer

    def update(self, view: SlotView, state: MonitorState) -> Alarm:
        if view.proba is None or view.cal_proba is None:
            return undecided(self.name, view, state, self.alpha)
        idx, _ = current_sample(view, state, self.n_sub)
        s, pred = label_free_scores(np.asarray(view.proba)[idx])
        cs, cpred = label_free_scores(view.cal_proba)
        classes = np.unique(pred)
        d_max, p_min = 0.0, 1.0
        for c in classes:
            cal_c = cs[cpred == c]
            if len(cal_c) < self.min_per_class:
                return undecided(self.name, view, state, self.alpha)
            res = ks_2samp(s[pred == c], cal_c)
            d_max = max(d_max, float(res.statistic))
            p_min = min(p_min, float(res.pvalue))
        p = min(1.0, len(classes) * p_min)
        return make_alarm(self.name, view, state, self.alpha, d_max, p, len(cs), len(s))
