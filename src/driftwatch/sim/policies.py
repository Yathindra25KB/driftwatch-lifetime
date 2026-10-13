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
    """Interface for the drift-monitor trigger; the monitors arrive in Phase 9."""

    name = "monitor"

    def should_retrain(self, slot_index: int) -> bool:
        raise NotImplementedError("monitor-triggered retraining is implemented in Phase 9")


def make_policy(name: str, period: int = 3) -> Policy:
    if name == "never":
        return Never()
    if name == "periodic":
        return Periodic(period)
    if name == "monitor":
        return MonitorTriggered()
    raise ValueError(f"unknown policy {name!r}")
