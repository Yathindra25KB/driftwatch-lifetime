"""Seeded synthetic timelines with planted concept drift, for the leakage canary and tests.

The committed fixture has features that are independent of labels, so nothing on it can
decay. This generator plants a drift a time-aware evaluation must show and a shuffled one
must not: malware is separable in one feature block early and in another block late. A
detector fitted on early slots loses the signal as time passes; one fitted on a random
sample of all slots keeps both blocks.

Fixture and synthetic numbers are never evidence (CLAUDE.md hard rule 8).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def drifting_timeline(
    *,
    n_slots: int = 16,
    rows_per_slot: int = 300,
    malware_share: float = 0.30,
    n_features: int = 24,
    drift: float = 1.0,
    signal: float = 2.0,
    width_days: int = 14,
    start: str = "2019-01-07",
    seed: int = 0,
) -> tuple[pd.DataFrame, np.ndarray]:
    """(table with ts, label, row_id; dense float32 features), rows in time order.

    ``drift`` in [0, 1]: 0 keeps the malware signal in the first feature block for ever (no
    decay); 1 moves it linearly from the first block to the second over the timeline.
    """
    if not 0.0 <= drift <= 1.0:
        raise ValueError("drift must lie in [0, 1]")
    if n_features < 2 or n_slots < 2:
        raise ValueError("need at least two slots and two features")
    rng = np.random.default_rng(seed)
    half = n_features // 2
    t0 = pd.Timestamp(start)
    slot_width = pd.Timedelta(days=width_days)
    n = n_slots * rows_per_slot
    slot = np.repeat(np.arange(n_slots), rows_per_slot)
    y = (rng.random(n) < malware_share).astype(np.int8)
    offset = rng.integers(0, int(slot_width.total_seconds()), size=n)
    ts = t0 + slot * slot_width + pd.to_timedelta(offset, unit="s")
    u = np.clip(drift * slot / (n_slots - 1), 0.0, 1.0)  # how far the signal has moved
    X = rng.normal(size=(n, n_features)).astype(np.float32)
    X[:, :half] += (y * signal * (1.0 - u))[:, None].astype(np.float32)
    X[:, half:] += (y * signal * u)[:, None].astype(np.float32)
    table = pd.DataFrame({"ts": ts, "label": y, "row_id": np.arange(n, dtype=np.int64)})
    order = np.lexsort((table["row_id"].to_numpy(), table["ts"].astype("int64").to_numpy()))
    return table.iloc[order].reset_index(drop=True), X[order]


def change_point_stream(
    *,
    n_slots: int = 12,
    rows_per_slot: int = 600,
    change_at: int | None = 6,
    shift: float = 1.0,
    malware_share: float = 0.30,
    n_features: int = 24,
    signal: float = 2.0,
    seed: int = 0,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Per-slot ``(X, y)`` with one abrupt covariate shift at slot ``change_at`` (None: never).

    Before the change every slot is drawn from the same distribution (malware separable in the
    first feature block). From ``change_at`` on, every row's first feature block moves by
    ``shift``: the features the detector relies on change, and so do its scores. Used by the
    monitor change-point and false-alarm tests; never evidence.
    """
    if n_features < 2 or n_slots < 1:
        raise ValueError("need at least one slot and two features")
    rng = np.random.default_rng(seed)
    half = n_features // 2
    out = []
    for t in range(n_slots):
        y = (rng.random(rows_per_slot) < malware_share).astype(np.int8)
        X = rng.normal(size=(rows_per_slot, n_features))
        X[:, :half] += (y * signal)[:, None]
        if change_at is not None and t >= change_at:
            X[:, :half] += shift
        out.append((X.astype(np.float32), y))
    return out
