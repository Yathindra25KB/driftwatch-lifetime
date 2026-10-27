"""E3 on a seeded synthetic stream: equal labels spent, calibration hygiene, delay.

Code-behaviour checks, never evidence. The contamination tests include a deliberate breakage:
a mutated router that sends selected rows to the calibration buffer must fail loudly.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_runner_sim import ROOT, make_config, make_source

import driftwatch.sim.runner_e3 as runner_e3
from driftwatch.conformal import recalibrate
from driftwatch.conformal.recalibrate import CalibrationContamination
from driftwatch.sim.config import RunConfig
from driftwatch.sim.runner import run

NONCONF = {"score": "probability", "holdout_fraction": 0.2, "min_per_class": 10, "buffer_size": 400}


def cfg(selector: str = "credibility", delay: int = 0, frac: float = 0.2, **over) -> RunConfig:
    nonconf = {**NONCONF, **over.pop("nonconf", {})}
    return make_config(
        selector={"name": selector, "calibration_fraction": frac},
        delay=delay,
        budget_pct=10.0,
        nonconf=nonconf,
        model=[{"name": "lr"}],
        **over,
    )


def go(config: RunConfig, tmp_path: Path):
    return run(config, make_source(rows=400), tmp_path, repo_root=ROOT)


def slots(summary) -> pd.DataFrame:
    return pd.read_parquet(summary.dir / "slots.parquet")


@pytest.mark.slow
def test_every_arm_spends_exactly_the_budget_and_the_same_reserved_slice(tmp_path: Path) -> None:
    tables = {
        name: slots(go(cfg(name), tmp_path / name))
        for name in ("random", "uncertainty", "credibility")
    }
    keys = ["seed", "window_id", "slot_id"]
    base = tables["random"].set_index(keys)
    for name, t in tables.items():
        t = t.set_index(keys)
        assert (t["n_queried"] == t["n_budget"].clip(upper=t["n"])).all()
        assert (t["n_queried"] == base["n_queried"]).all(), name  # equal labels spent
        assert (t["n_calibration"] == base["n_calibration"]).all()  # the reserved slice
        assert (t["n_selected"] + t["n_calibration"] == t["n_queried"]).all()
    # the selectors really differ in what they chose
    pred = {n: t["f1"].round(6).tolist() for n, t in tables.items()}
    assert pred["uncertainty"] != pred["random"] or pred["credibility"] != pred["random"]


@pytest.mark.slow
def test_only_holdout_and_random_slice_rows_reach_the_calibration_buffer(
    tmp_path: Path, monkeypatch
) -> None:
    seen: list[str] = []
    real_add = recalibrate.CalibrationBuffer.add

    def spy(self, X, y, origin):
        seen.extend(set(np.asarray(origin, dtype=object).tolist()) if not isinstance(origin, str)
                    else [origin])  # fmt: skip
        return real_add(self, X, y, origin)

    monkeypatch.setattr(recalibrate.CalibrationBuffer, "add", spy)
    go(cfg("credibility"), tmp_path)
    assert set(seen) == {"holdout", "random_slice"}  # nothing a selector chose, ever


@pytest.mark.slow
def test_a_router_that_sends_selected_rows_to_calibration_fails(
    tmp_path: Path, monkeypatch
) -> None:
    # deliberate breakage: treat "selected" rows as calibration rows
    monkeypatch.setattr(runner_e3, "ORIGIN_RANDOM", "selected")
    with pytest.raises(CalibrationContamination):
        go(cfg("credibility"), tmp_path)


@pytest.mark.slow
def test_the_zero_reserved_share_is_the_named_trap_and_does_feed_selected_rows(
    tmp_path: Path, monkeypatch
) -> None:
    seen: list[str] = []
    real_add = recalibrate.CalibrationBuffer.add

    def spy(self, X, y, origin):
        seen.extend(set(np.asarray(origin, dtype=object).tolist()) if not isinstance(origin, str)
                    else [origin])  # fmt: skip
        return real_add(self, X, y, origin)

    monkeypatch.setattr(recalibrate.CalibrationBuffer, "add", spy)
    s = slots(
        go(
            cfg("credibility", frac=0.0, nonconf={"trap_selected_calibration": True}),
            tmp_path,
        )
    )
    assert "selected" in seen  # the contamination is deliberate and visible
    assert (s["n_calibration"] == 0).all()
    assert (s["n_queried"] == s["n_budget"].clip(upper=s["n"])).all()


@pytest.mark.slow
def test_calibration_labels_arrive_through_the_queue_after_the_delay(tmp_path: Path) -> None:
    fast = slots(go(cfg("random", delay=0), tmp_path / "d0"))
    slow = slots(go(cfg("random", delay=3), tmp_path / "d3"))
    for t, d in ((fast, 0), (slow, 3)):
        w = (
            t[t["window_id"] == t["window_id"].iloc[0]]
            .sort_values("slot_index")
            .reset_index(drop=True)
        )
        arrived = w["n_released_to_calibration"].to_numpy()
        first = int(np.argmax(arrived > 0))
        assert first == 1 + d  # queried at slot 0, usable from slot 0 + 1 + d


@pytest.mark.slow
def test_calibration_rows_are_not_training_rows_and_the_initial_fit_leaves_a_holdout(
    tmp_path: Path,
) -> None:
    s = go(cfg("random"), tmp_path)
    t = slots(s)
    w = pd.read_parquet(s.dir / "windows.parquet")
    first = t[t["window_id"] == t["window_id"].iloc[0]].sort_values("slot_index")
    # the arrived labels in the pool are the selected ones only
    arrived = int(first["n_pool_new_labels"].iloc[-1])
    queried_selected = int(
        first["n_selected"].iloc[:-1].sum()
    )  # the last slot's labels never arrive
    assert arrived <= queried_selected
    # E3 fits on the window minus its time-ordered hold-out: fewer rows than the whole window
    full = go(make_config(model=[{"name": "lr"}]).__class__.from_dict(
        {**make_config(model=[{"name": "lr"}]).to_dict(), "policy": "never", "selector": None,
         "delay": None, "budget_pct": None, "pool": None}), tmp_path / "plain")  # fmt: skip
    wfull = pd.read_parquet(full.dir / "windows.parquet")
    assert int(w["n_train_rows"].iloc[0]) < int(wfull["n_train_rows"].iloc[0])


@pytest.mark.slow
def test_credibility_falls_back_to_random_when_no_calibration_exists_and_says_so(
    tmp_path: Path,
) -> None:
    c = cfg("credibility", nonconf={"min_per_class": 5000, "buffer_size": 20000})
    t = slots(go(c, tmp_path))
    assert t["selection_fell_back_to_random"].all()
    assert (t["n_queried"] == t["n_budget"].clip(upper=t["n"])).all()  # still the full budget
    assert t["set_coverage"].isna().all() and t["cal_skipped_total"].max() >= 1


@pytest.mark.slow
def test_the_conformal_diagnostics_are_logged_and_in_range(tmp_path: Path) -> None:
    t = slots(go(cfg("credibility"), tmp_path))
    ok = t.dropna(subset=["set_coverage"])
    assert len(ok) > 0
    assert ok["set_coverage"].between(0, 1).all() and ok["set_size_mean"].between(0, 2).all()
    assert (ok["cal_class0"] >= NONCONF["min_per_class"]).all()


@pytest.mark.slow
def test_same_config_and_seed_reproduce_the_same_predictions(tmp_path: Path) -> None:
    a = go(cfg("credibility"), tmp_path / "a")
    b = go(cfg("credibility"), tmp_path / "b")
    assert a.predictions_sha256 == b.predictions_sha256
