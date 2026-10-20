"""Drift monitors behind one alarm interface (Phase 9, docs/prereg/addendum-v3.md)."""

from __future__ import annotations

from driftwatch.monitors.base import Alarm, Monitor, MonitorState, SlotView
from driftwatch.monitors.domain_clf import DomainClassifier
from driftwatch.monitors.ks import KSTopK
from driftwatch.monitors.mmd import MMD
from driftwatch.monitors.p_uniformity import PUniformity

MONITORS = ("ks", "mmd", "domain_clf", "p_uniformity")


def make_monitor(name: str) -> Monitor:
    """The monitor with the settings frozen by addendum v3 (no free parameters)."""
    if name == "ks":
        return KSTopK()
    if name == "mmd":
        return MMD()
    if name == "domain_clf":
        return DomainClassifier()
    if name == "p_uniformity":
        return PUniformity()
    raise ValueError(f"unknown monitor {name!r}; choose from {MONITORS}")


__all__ = ["MONITORS", "Alarm", "Monitor", "MonitorState", "SlotView", "make_monitor"]
