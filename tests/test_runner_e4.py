"""E4 in the simulator: monitor-triggered and matched-count arms, rule R, cache, no labels.

Synthetic stream only (never evidence).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from simstream import spied
from test_runner_sim import ROOT, make_config, make_source

import driftwatch.sim.queue as queue_mod
from driftwatch.monitors import MONITORS
from driftwatch.sim.config import RunConfig
from driftwatch.sim.policies import even_schedule
from driftwatch.sim.runner import run

NONCONF = {"score": "probability", "holdout_fraction": 0.2, "min_per_class": 10, "buffer_size": 400}
ALL = list(MONITORS)
# the domain classifier fits a 99-draw null per window: fast tests leave it out, the slow
# variants run all four monitors
CHEAP = ["ks", "mmd", "p_uniformity"]


def cfg(policy, *, delay: int = 0, names=ALL, cache=None, nE: int = 6, **over) -> RunConfig:
    return make_config(
        policy=policy,
        selector={"name": "random", "calibration_fraction": 0.2},
        delay=delay,
        budget_pct=10.0,
        nonconf=NONCONF,
        monitors={"names": names, "cache": cache},
        model=[{"name": "lr"}],
        window={"nT": 3, "nE": nE, "stride": 2},
        **over,
    )


def go(config: RunConfig, out: Path, rows: int = 400, version: str | None = None):
    src = make_source(n_slots=14, rows=rows)
    return run(config, src, out, repo_root=ROOT, pinned_version=version)


def slots(summary) -> pd.DataFrame:
    return pd.read_parquet(summary.dir / "slots.parquet")


def preds(summary) -> pd.DataFrame:
    p = pd.read_parquet(summary.dir / "predictions.parquet")
    return p.drop(columns=["config_hash", "policy"]).reset_index(drop=True)


def per_window(df: pd.DataFrame):
    for _, g in df.groupby(["window_id", "seed", "model"], sort=False):
        yield g.reset_index(drop=True)


def test_monitor_arm_refits_only_after_an_alarm_and_never_closer_than_min_gap(
    tmp_path: Path,
) -> None:
    s = slots(go(cfg({"name": "monitor", "trigger": "ks", "min_gap": 2}, names=["ks"]), tmp_path))
    assert {"alarm_ks", "p_ks", "stat_ks", "decided_ks", "monitor_ref_slot"} <= set(s.columns)
    n_events = 0
    for g in per_window(s):
        last = 0
        for i in range(len(g)):
            if g.loc[i, "retrain_event"]:
                n_events += 1
                assert i >= 1 and bool(g.loc[i - 1, "alarm_ks"]), "event without an alarm"
                assert i - last >= 2
            if g.loc[i, "retrained"]:
                last = i
            if i >= 1 and g.loc[i - 1, "alarm_ks"] and i - last >= 2 and not g.loc[i, "retrained"]:
                assert g.loc[i, "retrain_event"]  # a due alarm always makes an event
    assert n_events > 0, "the drifting stream never triggered; the test exercises nothing"
    noop = s[s["retrain_event"] & ~s["retrained"]]
    assert (noop["retrain_noop_reason"] == "no_new_labels").all()


def test_rule_r_moves_the_reference_to_the_newest_slot_in_the_pool(tmp_path: Path) -> None:
    for delay in (0, 2):
        s = slots(go(cfg({"name": "monitor", "trigger": "ks"}, delay=delay, names=["ks"]),
                     tmp_path / f"d{delay}"))  # fmt: skip
        for g in per_window(s):
            ref = -1
            for i in range(len(g)):
                if g.loc[i, "retrained"]:
                    ref = max(ref, i - 1 - delay)  # newest slot whose labels have arrived
                assert g.loc[i, "monitor_ref_slot"] == ref


def test_observing_monitors_do_not_change_the_arm(tmp_path: Path) -> None:
    plain = make_config(
        policy="periodic",
        selector={"name": "random", "calibration_fraction": 0.2},
        delay=0,
        budget_pct=10.0,
        nonconf=NONCONF,
        model=[{"name": "lr"}],
    )
    a = go(plain, tmp_path / "a")
    b = go(cfg({"name": "periodic", "period": 3}, names=CHEAP), tmp_path / "b")
    pd.testing.assert_frame_equal(preds(a), preds(b))
    assert a.predictions_sha256 == b.predictions_sha256


@pytest.mark.slow
def test_never_arm_keeps_the_initial_reference_and_logs_every_monitor(tmp_path: Path) -> None:
    s = slots(go(cfg("never"), tmp_path))
    assert (s["monitor_ref_slot"] == -1).all() and not s["retrained"].any()
    for name in ALL:
        assert s[f"decided_{name}"].all(), name
        assert s[f"p_{name}"].between(0, 1).all(), name
    w = pd.read_parquet(next(tmp_path.glob("*/windows.parquet")))
    assert {f"n_alarms_{n}" for n in ALL} <= set(w.columns)


def test_matched_arm_has_the_source_refit_count_spread_evenly_and_equal_labels(
    tmp_path: Path,
) -> None:
    src_out = tmp_path / "src"
    src = slots(go(cfg({"name": "monitor", "trigger": "ks"}, names=["ks"]), src_out))
    m = go(cfg({"name": "matched", "trigger": "ks", "source": str(src_out)}, names=["ks"]),
           tmp_path / "m")  # fmt: skip
    ms = slots(m)
    keys = ["window_id", "seed", "model"]
    k_src = src.groupby(keys)["retrained"].sum()
    k_m = ms.groupby(keys)["retrained"].sum()
    events = ms[ms["retrain_event"]].groupby(keys)["retrain_event"].sum()
    for key, k in k_src.items():
        n_eval = int((ms[keys] == pd.Series(key, index=keys)).all(axis=1).sum())
        expected = even_schedule(int(k), 1, n_eval - 1)
        assert int(events.get(key, 0)) == len(expected)
        assert int(k_m[key]) <= int(k)  # an event with no new label is a no-op
    pd.testing.assert_series_equal(
        src.groupby(keys)["n_queried"].sum(), ms.groupby(keys)["n_queried"].sum()
    )
    w = pd.read_parquet(m.dir / "windows.parquet")
    assert w["matched_source_hash"].notna().all() and "matched_k" in w.columns
    got = w.merge(k_src.rename("k").reset_index(), on=keys)
    assert len(got) and (got["matched_k_source"] == got["k"]).all()
    assert (got["matched_refit_shortfall"] == got["k"] - got["n_retrains"]).all()


def test_matched_arm_refuses_a_source_with_other_settings(tmp_path: Path) -> None:
    src_out = tmp_path / "src"
    go(cfg({"name": "monitor", "trigger": "ks"}, names=["ks"]), src_out)
    with pytest.raises(RuntimeError, match="delay"):
        go(cfg({"name": "matched", "trigger": "ks", "source": str(src_out)}, delay=2,
               names=["ks"]), tmp_path / "m")  # fmt: skip
    with pytest.raises(RuntimeError, match="another monitor"):
        go(cfg({"name": "matched", "trigger": "mmd", "source": str(src_out)},
               names=["ks"]), tmp_path / "m2")  # fmt: skip


def test_a_dirty_tree_writes_no_disk_cache(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    go(cfg("never", names=["ks"], cache=str(cache)), tmp_path / "a", version="abc-dirty")
    assert not list(cache.rglob("*.json"))


@pytest.mark.parametrize(
    "names", [CHEAP, pytest.param(ALL, marks=pytest.mark.slow)], ids=["cheap", "all"]
)
def test_monitor_outputs_do_not_depend_on_the_labels_the_runner_holds(
    tmp_path: Path, monkeypatch, names: list[str]
) -> None:
    """Label invariance: permute every label the scoring and release doors hand out.

    The never arm does not refit, so its monitors depend on features and a fixed model only.
    If any label (scored y_true, released y) reached a monitor, its columns would change.
    """
    plain = slots(go(cfg("never", names=names), tmp_path / "plain"))
    rng = np.random.default_rng(0)
    score, take = queue_mod.SealedSlot.score, queue_mod.SealedSlot._take

    def permuted_score(self, pred):
        s = score(self, pred)
        y = rng.permutation(s.y_true)
        return queue_mod.Scored(y, s.row_id, queue_mod.score_slot(y, pred))

    def permuted_take(self, selection):
        r = take(self, selection)
        return dataclasses.replace(r, y=rng.permutation(r.y))

    monkeypatch.setattr(queue_mod.SealedSlot, "score", permuted_score)
    monkeypatch.setattr(queue_mod.SealedSlot, "_take", permuted_take)
    shuffled = slots(go(cfg("never", names=names), tmp_path / "shuffled"))
    assert not np.allclose(plain["f1"], shuffled["f1"])  # the labels really moved
    cols = [f"{k}_{n}" for n in names for k in ("alarm", "decided", "stat", "p")]
    pd.testing.assert_frame_equal(plain[cols], shuffled[cols])


def test_matched_arm_refuses_a_missing_source(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="exactly one complete run"):
        go(cfg({"name": "matched", "trigger": "ks", "source": str(tmp_path / "none")},
               names=["ks"]), tmp_path / "m")  # fmt: skip


@pytest.mark.slow
def test_disk_cache_is_reused_and_changes_no_statistic(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    clean = "0123abc"  # a committed version: a dirty tree gets no disk cache
    a = slots(go(cfg("never", names=["ks", "domain_clf"], cache=str(cache)), tmp_path / "a",
                 version=clean))  # fmt: skip
    files = list(cache.rglob("*.json"))
    assert files
    before = {f: f.stat().st_mtime_ns for f in files}
    b = slots(go(cfg({"name": "periodic", "period": 3}, names=["ks", "domain_clf"],
                     cache=str(cache)), tmp_path / "b", version=clean))  # fmt: skip
    nocache = slots(go(cfg("never", names=["ks", "domain_clf"]), tmp_path / "c"))
    cols = ["p_ks", "stat_ks", "p_domain_clf", "stat_domain_clf"]
    pd.testing.assert_frame_equal(a[cols], nocache[cols])
    # before the first refit the periodic arm meets the same pairs: same statistics
    first = b["slot_index"] <= b.groupby("window_id")["slot_index"].transform("min") + 2
    pd.testing.assert_frame_equal(
        a.loc[first, cols].reset_index(drop=True), b.loc[first, cols].reset_index(drop=True)
    )
    assert all(f.stat().st_mtime_ns >= before[f] for f in files)


@pytest.mark.parametrize(
    "names", [CHEAP, pytest.param(ALL, marks=pytest.mark.slow)], ids=["cheap", "all"]
)
def test_monitors_read_no_label_at_run_time(tmp_path: Path, monkeypatch, names) -> None:
    """Runtime spy: every label read in an E4 run comes from the queue (release and scoring)."""
    log: list[tuple[str, str, str]] = []
    original = queue_mod.SealedSlot.__init__

    def spying_init(self, slot):
        original(self, spied(slot, log))

    monkeypatch.setattr(queue_mod.SealedSlot, "__init__", spying_init)
    go(cfg({"name": "monitor", "trigger": "p_uniformity"}, names=names), tmp_path)
    callers = {c for c, _, _ in log}
    assert log and callers == {"driftwatch.sim.queue"}, callers


@pytest.mark.slow
def test_label_free_calibration_features_only_reach_the_monitors(tmp_path: Path) -> None:
    s = slots(go(cfg({"name": "monitor", "trigger": "p_uniformity"}, delay=2), tmp_path))
    assert s["decided_p_uniformity"].all()
    assert np.isfinite(s["p_p_uniformity"]).all()
