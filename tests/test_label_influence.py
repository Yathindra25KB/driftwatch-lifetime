"""The label-influence diagnostic: how many predictions change once labels have arrived.

It counts changed predictions (never vs periodic at a low and a high budget, and low vs
high). It must not compute or print AUT: the pool design is fixed by ADR-0007 before any
grid run and is never chosen by looking at AUT.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftwatch.sim.runner import run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_runner_sim import baseline_config, make_config, make_source  # noqa: E402


def load_script():
    spec = importlib.util.spec_from_file_location(
        "label_influence", ROOT / "scripts" / "label_influence.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["label_influence"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    out = tmp_path_factory.mktemp("li")
    src = make_source()
    never = run(baseline_config(seeds=[0, 1]), src, out, repo_root=ROOT)
    low = run(make_config(delay=0, budget_pct=0.5, seeds=[0, 1]), src, out, repo_root=ROOT)
    high = run(make_config(delay=0, budget_pct=5.0, seeds=[0, 1]), src, out, repo_root=ROOT)
    return never, low, high


def _first_refit(run_dir: Path) -> pd.Series:
    slots = pd.read_parquet(run_dir / "slots.parquet")
    return slots[slots["retrained"]].groupby("window_id")["slot_index"].min()


def test_counts_use_each_arms_own_first_refit_and_denominator(runs) -> None:
    mod = load_script()
    never, low, high = runs
    table = mod.influence_table("toy", never.dir, low.dir, high.dir)
    assert set(table["model"]) == {"lr"}
    row = table.iloc[0]

    key = ["seed", "window_id", "slot_id", "row_id", "model"]
    cols = [*key, "pred"]
    p = {
        k: pd.read_parquet(r.dir / "predictions.parquet", columns=cols)
        for k, r in zip(("n", "l", "h"), runs, strict=True)
    }
    m = p["n"].merge(p["l"], on=key, suffixes=("_n", "_l")).merge(p["h"], on=key)
    m = m.rename(columns={"pred": "pred_h"})
    slots = pd.read_parquet(high.dir / "slots.parquet")[["window_id", "slot_id", "slot_index"]]
    m = m.merge(slots.drop_duplicates(), on=["window_id", "slot_id"])
    fl, fh = _first_refit(low.dir), _first_refit(high.dir)
    after_l = m["slot_index"].to_numpy() >= m["window_id"].map(fl).to_numpy()
    after_h = m["slot_index"].to_numpy() >= m["window_id"].map(fh).to_numpy()
    either = after_l | after_h
    assert row["n_scored_low"] == int(after_l.sum())
    assert row["n_scored_high"] == int(after_h.sum())
    assert row["n_scored_either"] == int(either.sum())
    assert row["n_changed_never_vs_low"] == int((m["pred_n"] != m["pred_l"])[after_l].sum())
    assert row["n_changed_never_vs_high"] == int((m["pred_n"] != m["pred_h"])[after_h].sum())
    assert row["n_changed_low_vs_high"] == int((m["pred_l"] != m["pred_h"])[either].sum())
    assert 0 <= row["share_changed_never_vs_high"] <= 1


def test_the_table_has_no_aut_or_f1_and_reports_the_labels_that_arrived(runs) -> None:
    mod = load_script()
    never, low, high = runs
    table = mod.influence_table("toy", never.dir, low.dir, high.dir)
    for col in table.columns:
        assert "aut" not in col.lower() and "f1" not in col.lower(), col
    assert (table["mean_labels_arrived_high"] > table["mean_labels_arrived_low"]).all()
    assert (table["n_changed_never_vs_low"] <= table["n_scored_low"]).all()
    assert np.isfinite(table["share_changed_low_vs_high"]).all()


def test_the_script_refuses_runs_that_are_not_the_expected_arms(runs, tmp_path: Path) -> None:
    mod = load_script()
    never, low, high = runs
    with pytest.raises(ValueError, match="never"):
        mod.influence_table("toy", low.dir, low.dir, high.dir)
    with pytest.raises(ValueError, match="budget"):
        mod.influence_table("toy", never.dir, high.dir, low.dir)
