"""Per-slot scores, labels spent, drop events and recovery time.

True labels are read here and only here (CLAUDE.md hard rule 4): selectors, policies and
monitors never see them. A slot is scored at a fixed decision threshold chosen elsewhere
(ADR-0006); this module only counts.

Drop and recovery follow PROTOCOL section 3 and ADR-0006 (PROTOCOL D6): a drop event at slot
``t`` is an F1 at least ``drop`` (0.05) below the mean of the ``trailing`` (3) slots before
it. That mean is the pre-drop level. Recovery is the first later slot whose F1 is at least
``fraction`` (0.90) of that level; the time is the number of slots from the drop. An event
that never recovers within the series is censored (``None``). Events do not overlap: the
scan resumes after a recovery and stops at a censored one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

_EPS = 1e-9  # float slack so that "exactly 0.05 below" counts as a drop


@dataclass(frozen=True)
class SlotScores:
    n: int
    n_malware: int
    n_benign: int
    tp: int
    fp: int
    fn: int
    tn: int
    f1: float  # of the malware class
    fpr: float
    fnr: float


def score_slot(y_true: Any, y_pred: Any) -> SlotScores:
    """Confusion counts, F1 of the malware class, FPR and FNR for one evaluation slot."""
    y, p = np.asarray(y_true), np.asarray(y_pred)
    if y.ndim != 1 or y.shape != p.shape:
        raise ValueError(f"labels {y.shape} and predictions {p.shape} do not line up")
    if not (np.isin(y, (0, 1)).all() and np.isin(p, (0, 1)).all()):
        raise ValueError("labels and predictions must be 0 or 1")
    n_malware, n_benign = int((y == 1).sum()), int((y == 0).sum())
    if n_malware == 0 or n_benign == 0:
        raise ValueError("a slot needs both classes to be scored (C2)")
    tp = int(((y == 1) & (p == 1)).sum())
    fn = n_malware - tp
    fp = int(((y == 0) & (p == 1)).sum())
    tn = n_benign - fp
    return SlotScores(
        n=int(y.size),
        n_malware=n_malware,
        n_benign=n_benign,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        f1=2 * tp / (2 * tp + fp + fn),
        fpr=fp / n_benign,
        fnr=fn / n_malware,
    )


def labels_spent(queries_per_slot: Sequence[float]) -> int:
    """Total analyst queries (0 in E0, which never queries)."""
    q = np.asarray(queries_per_slot, dtype=np.float64)
    if q.size and (q < 0).any():
        raise ValueError("query counts cannot be negative")
    if q.size and not np.array_equal(q, np.floor(q)):
        raise ValueError("query counts must be whole numbers")
    return int(q.sum())


@dataclass(frozen=True)
class DropEvent:
    index: int  # slot position of the drop within the series
    level: float  # trailing mean before the drop
    f1: float  # F1 at the drop
    recovery_slots: int | None  # slots until F1 >= fraction * level; None = censored


def recovery_time(
    f1: Sequence[float], index: int, level: float, fraction: float = 0.9
) -> int | None:
    """Slots after ``index`` until F1 first reaches ``fraction * level``; None if it never does."""
    series = np.asarray(f1, dtype=np.float64)
    target = fraction * level
    for s in range(index + 1, series.size):
        if series[s] >= target - _EPS:
            return s - index
    return None


def drop_events(
    f1: Sequence[float], drop: float = 0.05, trailing: int = 3, fraction: float = 0.9
) -> list[DropEvent]:
    """Non-overlapping drop events of a per-slot F1 series, with their recovery times."""
    series = np.asarray(f1, dtype=np.float64)
    events: list[DropEvent] = []
    t = trailing
    while t < series.size:
        level = float(series[t - trailing : t].mean())
        if level - series[t] >= drop - _EPS:
            rec = recovery_time(series, t, level, fraction)
            events.append(DropEvent(t, level, float(series[t]), rec))
            if rec is None:
                break
            t += rec + 1
        else:
            t += 1
    return events
