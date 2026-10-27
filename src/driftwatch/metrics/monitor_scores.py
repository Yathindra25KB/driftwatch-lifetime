"""Monitor quality against drop events defined from true labels (PROTOCOL section 3, addendum v3).

True labels enter here and only here, through the per-slot F1 the metric code computed; a
monitor never sees them (hard rule 4).

- **Drop event** at slot ``t``: F1 at least 0.05 below the mean of the 3 slots before it, as
  :func:`driftwatch.metrics.slot.drop_events` defines it (the registered definition shared
  with recovery time; events do not overlap, and the scan stops at an event that never
  recovers).
- **Match**: an alarm at slot ``s`` (raised after slot ``s`` was scored, from slot ``s``'s
  features) matches a drop at slot ``t`` when ``t <= s <= t + horizon`` (horizon 2).
- **Alarm precision** = matched alarms / alarms, counting only alarms at slots ``s >= 3``
  (before that no drop can be defined). **Alarm recall** = drops with a matching alarm /
  drops. **Detection delay** = first matching ``s`` minus ``t``, over detected drops.

Per (window, seed) the counts are kept separately, so the two-stage bootstrap of v1 can
resample them; ratios are ratios of pooled counts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from driftwatch.metrics.slot import drop_events

HORIZON = 2
DROP = 0.05
TRAILING = 3


@dataclass(frozen=True)
class AlarmCounts:
    n_drops: int
    n_alarms: int  # alarms at slots >= TRAILING
    n_true_alarms: int
    n_detected: int
    delay_sum: int  # sum of detection delays over detected drops
    n_slots: int  # slots at which an alarm is scored (>= TRAILING)

    def __add__(self, other: AlarmCounts) -> AlarmCounts:
        return AlarmCounts(*(a + b for a, b in zip(self.as_tuple(), other.as_tuple(), strict=True)))

    def as_tuple(self) -> tuple[int, ...]:
        return (self.n_drops, self.n_alarms, self.n_true_alarms, self.n_detected,
                self.delay_sum, self.n_slots)  # fmt: skip

    @property
    def precision(self) -> float:
        return self.n_true_alarms / self.n_alarms if self.n_alarms else float("nan")

    @property
    def recall(self) -> float:
        return self.n_detected / self.n_drops if self.n_drops else float("nan")

    @property
    def mean_delay(self) -> float:
        return self.delay_sum / self.n_detected if self.n_detected else float("nan")

    @property
    def alarm_rate(self) -> float:
        return self.n_alarms / self.n_slots if self.n_slots else float("nan")


def score_alarms(
    f1: Sequence[float],
    alarms: Sequence[bool],
    *,
    horizon: int = HORIZON,
    drop: float = DROP,
    trailing: int = TRAILING,
) -> AlarmCounts:
    """Counts for one per-slot F1 series and the alarms raised on the same slots."""
    f = np.asarray(f1, dtype=np.float64)
    a = np.asarray(alarms, dtype=bool)
    if f.shape != a.shape:
        raise ValueError("one alarm decision per slot of the F1 series")
    drops = [e.index for e in drop_events(f, drop=drop, trailing=trailing)]
    alarm_slots = [int(s) for s in np.flatnonzero(a) if s >= trailing]
    n_true = sum(any(t <= s <= t + horizon for t in drops) for s in alarm_slots)
    detected, delay_sum = 0, 0
    for t in drops:
        hits = [s for s in alarm_slots if t <= s <= t + horizon]
        if hits:
            detected += 1
            delay_sum += hits[0] - t
    return AlarmCounts(len(drops), len(alarm_slots), n_true, detected, delay_sum,
                       max(0, f.size - trailing))  # fmt: skip


__all__ = ["DROP", "HORIZON", "TRAILING", "AlarmCounts", "score_alarms"]
