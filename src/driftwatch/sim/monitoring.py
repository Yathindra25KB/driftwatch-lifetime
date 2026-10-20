"""Drift monitors inside the simulator (E4): references, views, the statistic cache.

The runner owns the label door; this module only receives label-free things: public slot
features, model scores (through a scoring callable) and the *features* of the calibration
rows that have arrived. It builds the :class:`~driftwatch.monitors.base.SlotView` each monitor
sees and applies rule R (ADR-0010):

- the initial reference is a seeded sample of the window's time-ordered hold-out (the newest
  rows of the initial window, features only);
- after a refit, the reference becomes the seeded sample of the newest evaluation slot whose
  labelled rows were in the pool at that fit (under delay ``d`` that slot is at most
  ``s - 1 - d``). An arm that never refits keeps the initial reference.

Policy-independent statistics (KS, the domain classifier and its null) are kept in one cache
per window and, when the config names a cache directory, on disk under
``<cache>/<code version>/<window digest>.json``, so another cell of the same grid (another
policy, delay or model) reuses them instead of refitting. A cached value equals a fresh one
(every draw is seeded by seed, window and slot), so the cache changes cost, not results.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from driftwatch.monitors import make_monitor
from driftwatch.monitors.base import (
    INITIAL_REF,
    Alarm,
    MonitorState,
    SlotView,
    reference_sample,
)

log = logging.getLogger(__name__)
Scorer = Callable[[Any], np.ndarray]


class MonitorCache:
    """A per-window dict of statistics, optionally persisted as JSON."""

    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        if path is not None and path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        self._n_loaded = len(self.data)

    def save(self) -> None:
        if self.path is None or len(self.data) == self._n_loaded:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(self.data, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)
        self._n_loaded = len(self.data)


def cache_path(cache_dir: str | None, version: str, identity: str) -> Path | None:
    """Where a window's statistics persist, or ``None`` (memory only).

    ``identity`` names everything a cached statistic depends on besides the slot pair (window,
    hold-out fraction, data source digest). A dirty or unknown code version gets no disk
    cache: its statistics could come from code that is not committed anywhere.
    """
    if cache_dir is None:
        return None
    if version.endswith("-dirty") or version in ("", "unknown"):
        log.warning("code version %r: monitor statistics are not cached on disk", version)
        return None
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
    return Path(cache_dir) / version / f"{digest}.json"


class WindowMonitoring:
    """What the monitors of one window share across arms and models."""

    def __init__(
        self, names: tuple[str, ...], seed: int, window_key: str, cache: MonitorCache
    ) -> None:
        self.names = names
        self.seed = seed
        self.window_key = window_key
        self.cache = cache
        self.monitors = {n: make_monitor(n) for n in names}
        self.fitted: dict[str, dict[str, Any]] = {}
        self.initial_ref: Any = None
        self.slot_refs: dict[int, Any] = {}

    def start(self, train_X: Any, train_y: np.ndarray, holdout_X: Any) -> None:
        """Fit what each monitor needs, once per window, from the initial window only."""
        self.initial_ref = reference_sample(holdout_X, self.seed, self.window_key, INITIAL_REF)
        for name, mon in self.monitors.items():
            st = MonitorState(self.seed, self.window_key, cache=self.cache.data)
            mon.start(st, train_X, train_y, holdout_X)
            self.fitted[name] = st.fitted

    def remember_slot(self, slot_index: int, public_X: Any) -> None:
        """Keep the seeded reference sample of a streamed slot (features only)."""
        self.slot_refs[slot_index] = reference_sample(
            public_X, self.seed, self.window_key, slot_index
        )

    def arm(self) -> ArmMonitors:
        return ArmMonitors(self)


class ArmMonitors:
    """The monitors of one arm (one model of one window): reference, states, alarms."""

    def __init__(self, win: WindowMonitoring) -> None:
        self.win = win
        self.states: dict[str, MonitorState] = {}
        for name in win.names:
            st = MonitorState(win.seed, win.window_key, fitted=win.fitted[name],
                              cache=win.cache.data)  # fmt: skip
            st.reset_reference(win.initial_ref, INITIAL_REF)
            self.states[name] = st
        self.ref_X = win.initial_ref
        self.ref_slot = INITIAL_REF
        self.newest_in_pool = INITIAL_REF
        self.seconds = 0.0

    def note_arrived(self, queried_in: np.ndarray) -> None:
        """Training rows that entered the pool, by the slot they were queried in."""
        if len(queried_in):
            self.newest_in_pool = max(self.newest_in_pool, int(np.max(queried_in)))

    def on_refit(self) -> None:
        """Rule R: after a refit the reference is the newest slot represented in the pool."""
        q = self.newest_in_pool
        if q > self.ref_slot and q in self.win.slot_refs:
            self.ref_X, self.ref_slot = self.win.slot_refs[q], q
            for st in self.states.values():
                st.reset_reference(self.ref_X, q)

    def update(
        self,
        slot_index: int,
        slot_id: str,
        X: Any,
        proba: np.ndarray,
        score: Scorer,
        calibration_X: Callable[[], Any],
    ) -> dict[str, Alarm]:
        t0 = time.perf_counter()
        names = self.win.names
        ref_proba = score(self.ref_X) if "mmd" in names else None
        cal_X = cal_proba = None
        if "p_uniformity" in names:
            cal_X = calibration_X()
            cal_proba = score(cal_X)
        view = SlotView(slot_index, slot_id, X, proba=proba, ref_proba=ref_proba,
                        cal_X=cal_X, cal_proba=cal_proba)  # fmt: skip
        out = {n: self.win.monitors[n].update(view, self.states[n]) for n in names}
        self.seconds += time.perf_counter() - t0
        return out

    def columns(self, alarms: dict[str, Alarm]) -> dict[str, Any]:
        row: dict[str, Any] = {"monitor_ref_slot": self.ref_slot}
        for n, a in alarms.items():
            row[f"alarm_{n}"] = a.fired
            row[f"decided_{n}"] = a.decided
            row[f"stat_{n}"] = a.statistic
            row[f"p_{n}"] = a.p_value
        return row

    def totals(self) -> dict[str, Any]:
        out: dict[str, Any] = {"monitor_seconds_total": round(self.seconds, 3)}
        for n, st in self.states.items():
            out[f"n_alarms_{n}"] = st.n_alarms
            out[f"n_undecided_{n}"] = st.n_undecided
        return out


__all__ = ["ArmMonitors", "MonitorCache", "WindowMonitoring", "cache_path"]
