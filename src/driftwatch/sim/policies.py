"""Retraining policies: when the detector is refitted on the pool.

A policy decides *when*; it is given the slot index and nothing else, so it cannot see a
label (hard rule 4). Retraining itself uses only labels that have arrived (the queue's
release), and the pool it fits on is defined by ADR-0007.

Anchor (ADR-0007, decision D7): slot indices count evaluation slots from the first one of the
window, which is scored by the initial model. A periodic policy with period ``p`` fires
before scoring slots ``p, 2p, 3p, ...``. If no new label has arrived since the last fit the
runner logs the event as a no-op; it does not refit and it does not drop the event silently.
"""

from __future__ import annotations

from typing import Protocol


class Policy(Protocol):
    name: str

    def should_retrain(self, slot_index: int) -> bool: ...


class Never:
    name = "never"

    def should_retrain(self, slot_index: int) -> bool:
        return False


class Periodic:
    name = "periodic"

    def __init__(self, period: int = 3) -> None:
        if isinstance(period, bool) or not isinstance(period, int) or period < 1:
            raise ValueError(f"period must be a positive integer, got {period!r}")
        self.period = period

    def should_retrain(self, slot_index: int) -> bool:
        return slot_index > 0 and slot_index % self.period == 0


class MonitorTriggered:
    """Retrain when the drift monitor alarmed on the previous slot (addendum v3).

    Timeline: the monitor looks at slot ``s`` after it is scored; its alarm is passed in with
    :meth:`notify` and is *pending* for slot ``s + 1`` only. Before slot ``s + 1`` is scored,
    a pending alarm makes a retrain event when at least ``min_gap`` slots have passed since the
    last actual refit (the initial model counts as a fit at slot 0). The runner then refits if
    new labels have arrived, or logs a no-op if none has. Either way the alarm is consumed:
    it is never carried to a later slot (a monitor that still sees drift alarms again). The
    policy sees the slot index and one bit per slot, never a label.
    """

    name = "monitor"

    def __init__(self, trigger: str, min_gap: int = 2) -> None:
        if isinstance(min_gap, bool) or not isinstance(min_gap, int) or min_gap < 1:
            raise ValueError(f"min_gap must be a positive integer, got {min_gap!r}")
        self.trigger = trigger
        self.min_gap = min_gap
        self._pending = False
        self._last_fit = 0

    def notify(self, alarm: bool) -> None:
        """The trigger monitor's decision on the slot just scored."""
        self._pending = bool(alarm)

    def should_retrain(self, slot_index: int) -> bool:
        return self._pending and slot_index - self._last_fit >= self.min_gap

    def record(self, slot_index: int, refitted: bool) -> None:
        """After the event check of a slot: the alarm is consumed; a refit restarts the gap."""
        self._pending = False
        if refitted:
            self._last_fit = slot_index


class Scheduled:
    """Retrain events at a fixed set of slots (the matched-count control of E4)."""

    name = "matched"

    def __init__(self, slots: list[int] | tuple[int, ...]) -> None:
        self.slots = frozenset(int(s) for s in slots)

    def should_retrain(self, slot_index: int) -> bool:
        return slot_index in self.slots


def even_schedule(k: int, first: int, last: int) -> tuple[int, ...]:
    """``k`` retrain slots spread evenly over ``first..last`` (all of them if ``k`` is larger).

    The matched-count control: the same number of refits as a monitor arm, placed without
    looking at any data. Slot ``j`` of ``k`` is ``first + floor((j + 1) * n / (k + 1))`` with
    ``n = last - first + 1``, which keeps the events distinct and away from both ends.
    """
    if k < 0:
        raise ValueError("k must be non-negative")
    if last < first or k == 0:
        return ()
    n = last - first + 1
    if k >= n:
        return tuple(range(first, last + 1))
    return tuple(first + (j + 1) * n // (k + 1) for j in range(k))


def make_policy(
    name: str, period: int = 3, *, trigger: str | None = None, min_gap: int = 2
) -> Policy:
    if name == "never":
        return Never()
    if name == "periodic":
        return Periodic(period)
    if name == "monitor":
        if trigger is None:
            raise ValueError("a monitor-triggered policy needs its trigger monitor")
        return MonitorTriggered(trigger, min_gap)
    raise ValueError(f"unknown policy {name!r}")
