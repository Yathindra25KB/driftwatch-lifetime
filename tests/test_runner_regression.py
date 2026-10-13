"""Regression fixture: the qualitative ordering the simulator must reproduce.

Rebuilt from the guide's sandbox stream by shape only (24 slots of 1,500 samples, 40 features,
10% malware, the malware direction rotating away from where the model learned it; labels per
slot 25 or 100; delay 0 or 3). No number from the guide appears here and none of these results
is evidence: the stream is synthetic. What is asserted is order, so a change to the queue,
the pool or the runner that breaks the mechanics shows up as an order violation:

- never retraining is the worst arm;
- more labels per slot help (at the same delay);
- a longer delay hurts (at the same labels).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftwatch.data.synthetic import drifting_timeline
from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.sim.config import RunConfig
from driftwatch.sim.runner import run

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = np.datetime64("2019-01-07", "ns")
WIDTH = np.timedelta64(14, "D")
N_SLOTS, ROWS, FEATURES = 24, 1500, 40
LABELS_LOW, LABELS_HIGH = 25, 100  # per slot, as a percentage of the 150 kept rows below
SEEDS = [0, 1, 2, 3, 4]


def source() -> TableSource:
    table, X = drifting_timeline(
        n_slots=N_SLOTS,
        rows_per_slot=ROWS,
        malware_share=0.10,
        n_features=FEATURES,
        drift=1.0,
        signal=2.0,
        seed=11,
    )
    return TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, name="toy")


def config(policy: str, delay: int | None, pct: float | None) -> RunConfig:
    d = {
        "name": "toy",
        "dataset": "bodmas",
        "slots": {"preset": "adr-0004", "min_malware": 10},
        "window": {"nT": 4, "nE": 20, "stride": 1},
        "ratio": {"target": 0.10, "sensitivity": 0.05},
        "seeds": SEEDS,
        "model": [{"name": "lr"}],
        "policy": policy,
        "e0": {"variants": ["rolling"], "random_split": False},
        "output": "unused",
    }
    if delay is not None:
        d.update(selector="random", delay=delay, budget_pct=pct)
    return RunConfig.from_dict(d)


def pct_for(labels: int, n_slot: float) -> float:
    return 100.0 * labels / n_slot


@pytest.fixture(scope="module")
def aut_by_arm(tmp_path_factory) -> dict[str, float]:
    src = source()
    out = tmp_path_factory.mktemp("toy")
    # slot size after C3 (10% of 1,500 malware stays; benign is untouched)
    first = run(config("never", None, None), src, out / "never", repo_root=ROOT)
    slots = pd.read_parquet(first.dir / "slots.parquet")
    n_slot = float(slots["n"].mean())
    arms = {
        "never": config("never", None, None),
        "d0_low": config("periodic", 0, pct_for(LABELS_LOW, n_slot)),
        "d0_high": config("periodic", 0, pct_for(LABELS_HIGH, n_slot)),
        "d3_high": config("periodic", 3, pct_for(LABELS_HIGH, n_slot)),
    }
    result = {}
    for name, cfg in arms.items():
        s = first if name == "never" else run(cfg, src, out / name, repo_root=ROOT)
        windows = pd.read_parquet(s.dir / "windows.parquet")
        assert windows["aut_defined"].all() and len(windows) == len(SEEDS)
        result[name] = float(windows["aut"].mean())
    return result


def test_never_retraining_is_the_worst_arm(aut_by_arm) -> None:
    worst = min(aut_by_arm, key=aut_by_arm.get)
    assert worst == "never", aut_by_arm


def test_more_labels_per_slot_help(aut_by_arm) -> None:
    assert aut_by_arm["d0_high"] > aut_by_arm["d0_low"], aut_by_arm


def test_a_longer_delay_hurts(aut_by_arm) -> None:
    assert aut_by_arm["d0_high"] > aut_by_arm["d3_high"], aut_by_arm


def test_every_arm_beats_never_only_through_arrived_labels(aut_by_arm) -> None:
    """d = 3 still beats never: labels from the first slots arrive and are used."""
    assert aut_by_arm["d3_high"] > aut_by_arm["never"], aut_by_arm
