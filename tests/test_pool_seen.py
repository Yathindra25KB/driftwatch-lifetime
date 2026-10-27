"""Feature-vector repeats through the label queue: ``n_seen_in_pool`` (review item, Phase 6).

A vector that was queried in one slot and repeats in a later slot is already in the pool once
its label has arrived, so the label spent on it can look like detection gain. The slot table
carries the count next to the initial-window-only count. Seeded synthetic stream, never
evidence.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from driftwatch.data.synthetic import drifting_timeline
from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.sim.config import RunConfig
from driftwatch.sim.runner import run

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = np.datetime64("2019-01-07", "ns")
WIDTH = np.timedelta64(14, "D")
ROWS = 200


def source_with_repeats() -> TableSource:
    """Slot 7 (evaluation index 4) repeats the first 60 vectors of slot 4 (evaluation index 1)."""
    table, X = drifting_timeline(n_slots=12, rows_per_slot=ROWS, drift=1.0, seed=3)
    fv = np.array([f"v{i:06d}" for i in range(len(table))], dtype=object)
    ts = table["ts"].to_numpy().astype("datetime64[ns]")
    slot = (ts - ANCHOR) // WIDTH
    src_rows = np.flatnonzero(slot == 4)[:60]
    dst_rows = np.flatnonzero(slot == 7)[:60]
    fv[dst_rows] = fv[src_rows]
    table = table.assign(fv=fv)
    return TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, fv_col="fv", name="synthetic")


def config(delay: int) -> RunConfig:
    return RunConfig.from_dict(
        {
            "name": "seen",
            "dataset": "bodmas",
            "slots": {"preset": "adr-0004", "min_malware": 5},
            "window": {"nT": 3, "nE": 6, "stride": 2},
            "ratio": {"target": 0.10, "sensitivity": 0.05},
            "seeds": [0],
            "model": [{"name": "lr"}],
            "policy": {"name": "periodic", "period": 3},
            "selector": "random",
            "delay": delay,
            "budget_pct": 100.0,  # query every row, so every repeat has an earlier copy
            "e0": {"variants": ["rolling"], "random_split": False},
            "output": "unused",
        }
    )


def seen_by_slot(tmp_path: Path, delay: int) -> pd.DataFrame:
    summary = run(config(delay), source_with_repeats(), tmp_path, repo_root=ROOT)
    s = pd.read_parquet(summary.dir / "slots.parquet")
    s = s[s["window_id"] == s["window_id"].iloc[0]].sort_values("slot_index")
    return s.reset_index(drop=True)


def test_a_repeat_is_counted_once_its_label_has_arrived(tmp_path: Path) -> None:
    s = seen_by_slot(tmp_path / "d0", delay=0)
    # evaluation index 1 is queried at d = 0 and released before index 2, so the repeat at
    # index 4 finds its twin in the pool; the initial-window-only count cannot see it
    assert s.loc[4, "n_seen_in_pool"] > s.loc[4, "n_seen_in_initial_train"]
    assert s.loc[4, "n_seen_in_pool"] >= 1
    assert (s.loc[:3, "n_seen_in_pool"] == s.loc[:3, "n_seen_in_initial_train"]).all()


def test_delay_keeps_the_twin_out_of_the_pool(tmp_path: Path) -> None:
    s = seen_by_slot(tmp_path / "d3", delay=3)
    # queried at index 1 with d = 3 arrives at index 5: index 4 is scored without it
    assert s.loc[4, "n_seen_in_pool"] == s.loc[4, "n_seen_in_initial_train"]


def test_count_is_none_without_hashes(tmp_path: Path) -> None:
    table, X = drifting_timeline(n_slots=12, rows_per_slot=ROWS, drift=1.0, seed=3)
    src = TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, name="synthetic")
    summary = run(config(0), src, tmp_path, repo_root=ROOT)
    s = pd.read_parquet(summary.dir / "slots.parquet")
    assert s["n_seen_in_pool"].isna().all()
