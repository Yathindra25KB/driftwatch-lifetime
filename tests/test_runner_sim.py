"""The simulator end to end on seeded synthetic timelines (code-behaviour checks, never evidence).

Stream, queue, pool, policy: slot by slot, labels arrive after the delay, retraining uses only
arrived labels. The checks here are about mechanics (counts, order, determinism, resume,
sealing); the qualitative ordering lives in test_runner_regression.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from simstream import spied

import driftwatch.models as models_pkg
import driftwatch.sim.runner as runner
from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.models.linear import LogisticDetector
from driftwatch.sim.config import RunConfig
from driftwatch.sim.runner import InitialModelCache, run, run_many
from driftwatch.sim.selectors import budget_count

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = np.datetime64("2019-01-07", "ns")
WIDTH = np.timedelta64(14, "D")


def make_source(n_slots: int = 12, rows: int = 300, drift: float = 1.0, seed: int = 0):
    from driftwatch.data.synthetic import drifting_timeline

    table, X = drifting_timeline(n_slots=n_slots, rows_per_slot=rows, drift=drift, seed=seed)
    return TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, name="synthetic")


def make_config(**over) -> RunConfig:
    d = {
        "name": "sim",
        "dataset": "bodmas",
        "slots": {"preset": "adr-0004", "min_malware": 5},
        "window": {"nT": 3, "nE": 6, "stride": 2},
        "ratio": {"target": 0.10, "sensitivity": 0.05},
        "seeds": [0],
        "model": [{"name": "lr"}],
        "policy": "periodic",
        "selector": "random",
        "delay": 0,
        "budget_pct": 5.0,
        "e0": {"variants": ["rolling"], "random_split": False},
        "output": "unused",
    }
    d.update(over)
    return RunConfig.from_dict(d)


def baseline_config(**over) -> RunConfig:
    d = {"policy": "never", "selector": None, "delay": None, "budget_pct": None}
    d.update(over)
    return make_config(**d)


def tables(summary):
    d = summary.dir
    return (
        pd.read_parquet(d / "windows.parquet"),
        pd.read_parquet(d / "slots.parquet"),
        pd.read_parquet(d / "predictions.parquet"),
        json.loads((d / "run.json").read_text(encoding="utf-8")),
    )


def go(cfg: RunConfig, tmp_path: Path, **kw):
    return run(cfg, make_source(), tmp_path, repo_root=ROOT, **kw)


KEY = ["window_id", "slot_id", "row_id"]


def merged(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    a = a[a["series"] == "time_aware"]
    b = b[b["series"] == "time_aware"]
    return a.merge(b, on=KEY + ["model", "seed"], suffixes=("_a", "_b"))


# --- logged counts --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def periodic_d1(tmp_path_factory):
    out = tmp_path_factory.mktemp("sim")
    return go(make_config(delay=1, budget_pct=5.0), out)


def test_slot_rows_log_budget_pool_and_arrivals(periodic_d1) -> None:
    windows, slots, preds, record = tables(periodic_d1)
    assert set(slots["policy"]) == {"periodic"} and set(slots["selector"]) == {"random"}
    assert set(slots["delay"]) == {1} and set(slots["budget_pct"]) == {5.0}
    want = [budget_count(n, 5.0) for n in slots["n"]]
    assert slots["n_budget"].tolist() == want  # absolute count logged beside the percentage
    assert (slots["n_budget"] <= slots["n"]).all() and (slots["n_budget"] > 0).any()
    assert record["config"]["delay"] == 1 and record["config"]["budget_pct"] == 5.0

    for _, w in slots.groupby("window_id"):
        w = w.sort_values("slot_index").reset_index(drop=True)
        n_train = int(windows[windows["window_id"] == w["window_id"][0]]["n_train_rows"].iloc[0])
        d = 1
        for s in range(len(w)):
            src = s - 1 - d
            expected_released = int(w["n_budget"][src]) if src >= 0 else 0
            assert w["n_released"][s] == expected_released  # usable from t + 1 + d
            assert w["n_pool"][s] == n_train + int(w["n_released"][: s + 1].sum())
        # slots whose release slot is past the window end are ignored and counted
        late = w["n_budget"][len(w) - 1 - d :].sum()
        assert w["n_ignored_after_end"].sum() == late


def test_retrain_events_follow_the_period_and_use_only_arrived_labels(periodic_d1) -> None:
    _, slots, _, _ = tables(periodic_d1)
    for _, w in slots.groupby("window_id"):
        w = w.sort_values("slot_index").reset_index(drop=True)
        assert w.index[w["retrain_event"]].tolist() == [3]  # nE = 6: before slot 3 only
        assert w["retrained"].tolist() == [False, False, False, True, False, False]
        assert w["n_pool"].iloc[3] > w["n_pool"].iloc[2] - 1  # pool at slot 3 includes arrivals


def test_a_scheduled_retrain_with_no_new_labels_is_logged_as_a_no_op(tmp_path: Path) -> None:
    # d = 3: nothing queried in slots 0-2 has arrived by slot 3 (earliest release is slot 4)
    summary = go(make_config(delay=3), tmp_path)
    _, slots, _, _ = tables(summary)
    event = slots[slots["retrain_event"]]
    assert len(event) > 0
    assert not event["retrained"].any() and (event["n_released"] == 0).all()
    assert event["fit_seconds"].eq(0).all()


# --- invariances ----------------------------------------------------------------------------


def test_never_is_indifferent_to_delay_and_budget_and_equals_the_baseline(tmp_path: Path) -> None:
    base = go(baseline_config(), tmp_path / "base")
    sim = go(make_config(policy="never", delay=2, budget_pct=5.0), tmp_path / "sim")
    pb, ps = tables(base)[2], tables(sim)[2]
    m = merged(pb, ps)
    assert len(m) == len(pb) == len(ps)
    assert np.array_equal(m["pred_a"], m["pred_b"])
    assert np.allclose(m["proba_a"], m["proba_b"])


def test_labels_change_predictions_only_from_the_first_retrain_slot(tmp_path: Path) -> None:
    never = go(baseline_config(), tmp_path / "never")
    periodic = go(make_config(delay=0, budget_pct=5.0), tmp_path / "periodic")
    m = merged(tables(never)[2], tables(periodic)[2])
    pos = {
        (wid, sid): i
        for wid, w in tables(periodic)[1].groupby("window_id")
        for i, sid in enumerate(w.sort_values("slot_index")["slot_id"])
    }
    m["s"] = [pos[(w, sid)] for w, sid in zip(m["window_id"], m["slot_id"], strict=True)]
    assert (m[m["s"] < 3]["pred_a"] == m[m["s"] < 3]["pred_b"]).all()
    assert (m[m["s"] < 3]["proba_a"] == m[m["s"] < 3]["proba_b"]).all()
    after = m[m["s"] >= 3]
    assert (after["proba_a"] != after["proba_b"]).any()  # arrived labels moved the model


def test_at_delay_3_periodic_is_identical_to_never_on_a_six_slot_window(tmp_path: Path) -> None:
    """The BODMAS limit named in ADR-0007: nE = 6, period 3, d = 3 leaves nothing to learn."""
    never = go(baseline_config(), tmp_path / "never")
    late = go(make_config(delay=3), tmp_path / "late")
    m = merged(tables(never)[2], tables(late)[2])
    assert np.array_equal(m["pred_a"], m["pred_b"])
    assert np.allclose(m["proba_a"], m["proba_b"])


# --- determinism, resume, parallelism --------------------------------------------------------


def test_same_config_and_seed_reproduce_identical_predictions(tmp_path: Path) -> None:
    a = go(make_config(), tmp_path / "a")
    b = go(make_config(), tmp_path / "b")
    assert a.predictions_sha256 == b.predictions_sha256
    pd.testing.assert_frame_equal(tables(a)[2], tables(b)[2])


def test_different_delay_or_budget_changes_the_hash_and_the_directory(tmp_path: Path) -> None:
    a = go(make_config(delay=0), tmp_path)
    b = go(make_config(delay=1), tmp_path)
    c = go(make_config(delay=0, budget_pct=1.0), tmp_path)
    assert len({a.config_hash, b.config_hash, c.config_hash}) == 3
    assert len({a.dir, b.dir, c.dir}) == 3


def test_an_interrupted_run_resumes_cleanly_without_duplicates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # resume demands a clean tree; pin a clean version so the same hash is used throughout
    monkeypatch.setattr(runner, "code_version", lambda repo=None: "abc1234")
    cfg = make_config(delay=1, seeds=[0, 1])
    want = go(cfg, tmp_path / "full")

    calls = {"n": 0}
    real = runner._run_sim_window

    def flaky(*args, **kw):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("killed")
        return real(*args, **kw)

    monkeypatch.setattr(runner, "_run_sim_window", flaky)
    with pytest.raises(RuntimeError, match="killed"):
        go(cfg, tmp_path / "resume")
    monkeypatch.setattr(runner, "_run_sim_window", real)

    count = {"n": 0}

    def counting(*args, **kw):
        count["n"] += 1
        return real(*args, **kw)

    monkeypatch.setattr(runner, "_run_sim_window", counting)
    got = go(cfg, tmp_path / "resume", resume=True)
    assert count["n"] == 2  # 4 units in all (2 windows x 2 seeds), 2 were already done
    assert got.predictions_sha256 == want.predictions_sha256
    gp, wp = tables(got)[2], tables(want)[2]
    pd.testing.assert_frame_equal(gp, wp)
    assert not gp.duplicated(["seed", "window_id", "slot_id", "row_id", "model"]).any()
    timing = [c for c in tables(got)[1].columns if c.endswith("_seconds")]
    pd.testing.assert_frame_equal(
        tables(got)[1].drop(columns=timing), tables(want)[1].drop(columns=timing)
    )
    assert any(Path(got.dir).glob("run_failed.*.json"))  # the interruption stays on record


def test_resume_refuses_a_dirty_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "code_version", lambda repo=None: "abc1234-dirty")
    with pytest.raises(RuntimeError, match="dirty"):
        go(make_config(), tmp_path, resume=True)


def test_run_many_in_threads_equals_running_one_by_one(tmp_path: Path) -> None:
    cfgs = [make_config(delay=d) for d in (0, 1, 2)]
    seq = [go(c, tmp_path / "seq") for c in cfgs]
    par = run_many([(c, make_source()) for c in cfgs], tmp_path / "par", repo_root=ROOT, workers=3)
    assert [s.predictions_sha256 for s in seq] == [p.predictions_sha256 for p in par]


# --- initial-model cache ---------------------------------------------------------------------


class CountingDetector(LogisticDetector):
    name = "counting"
    fits: list[int] = []

    def _fit(self, X, y):
        CountingDetector.fits.append(len(y))
        return super()._fit(X, y)


def test_initial_models_are_shared_through_the_cache_across_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(models_pkg._REGISTRY, "counting", CountingDetector)
    CountingDetector.fits = []
    cache = InitialModelCache()
    model = [{"name": "counting"}]
    go(make_config(delay=0, model=model, policy="never"), tmp_path / "a", cache=cache)
    n_first = len(CountingDetector.fits)
    assert n_first == 2  # one initial fit per window (2 windows), never retrained
    go(make_config(delay=2, model=model, policy="never"), tmp_path / "b", cache=cache)
    assert len(CountingDetector.fits) == n_first  # same dataset, window, model: no refit


def test_cache_key_is_a_subhash_of_dataset_window_model_and_seed() -> None:
    k = InitialModelCache.key("bodmas", "w0+3", {"name": "lr"}, seed=None)
    assert k == InitialModelCache.key("bodmas", "w0+3", {"name": "lr"}, seed=None)
    assert k != InitialModelCache.key("lamda", "w0+3", {"name": "lr"}, seed=None)
    assert k != InitialModelCache.key("bodmas", "w1+3", {"name": "lr"}, seed=None)
    assert k != InitialModelCache.key("bodmas", "w0+3", {"name": "lr", "C": 2.0}, seed=None)
    assert k != InitialModelCache.key("bodmas", "w0+3", {"name": "lr"}, seed=1)
    assert len(k) == 16


# --- sealing at the runner level --------------------------------------------------------------


def test_the_runner_never_reads_a_label_outside_the_queue_module(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    log: list[tuple[str, str, str]] = []
    real = runner.slice_windows

    def spying(source, spec, *a, **kw):
        for window in real(source, spec, *a, **kw):
            original = window.eval_slots

            def eval_slots(original=original):
                for slot in original():
                    yield spied(slot, log)

            window.eval_slots = eval_slots  # type: ignore[method-assign]
            yield window

    monkeypatch.setattr(runner, "slice_windows", spying)
    go(make_config(delay=1), tmp_path)
    assert log, "no label reads were recorded"
    assert {caller for caller, _, _ in log} == {"driftwatch.sim.queue"}


# --- per-slot random-split comparator (E1) ----------------------------------------------------


def test_per_slot_random_split_stores_a_matched_series_for_every_evaluation_slot(
    tmp_path: Path,
) -> None:
    cfg = baseline_config(
        e0={"variants": ["rolling"], "random_split": True, "per_slot_random_split": True}
    )
    s = go(cfg, tmp_path)
    windows, slots, preds, _ = tables(s)
    ta, rs = slots[slots["series"] == "time_aware"], slots[slots["series"] == "random_split"]
    assert len(ta) == len(rs) > 0
    assert set(ta["slot_id"]) == set(rs["slot_id"])  # one random-split point per time-aware point
    assert (rs["achieved_ratio"] <= rs["target_ratio"] + 1e-12).all()  # same C3 ratio, per slot
    assert (rs["c3_status"].isin(["at_target", "below_target"])).all()
    assert (rs["n"] > 0).all() and rs["f1"].between(0, 1).all()
    p = preds[preds["series"] == "random_split"]
    assert set(p["policy"]) == {"never"} and p["row_id"].notna().all()
    # a random-split model has seen the future: its row ids are not the time-aware test rows
    t = preds[preds["series"] == "time_aware"]
    assert not p.duplicated(["model", "seed", "window_id", "slot_id", "row_id"]).any()
    assert set(map(int, p["row_id"])) != set(map(int, t["row_id"]))
    assert "f1_random_split" in windows.columns  # the window-level comparator is still there


def test_cli_runs_several_configs_in_threads_and_rejects_resume_on_a_dirty_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import yaml

    from driftwatch import cli

    monkeypatch.setattr(
        "driftwatch.data.presets.cached_source", lambda dataset, root="data", **kw: make_source()
    )
    paths = []
    for d in (0, 2):
        p = tmp_path / f"c{d}.yaml"
        p.write_text(yaml.safe_dump(make_config(delay=d).to_dict()), encoding="utf-8")
        paths.append(str(p))
    out = tmp_path / "out"
    assert cli.main(["run", *paths, "--out", str(out), "--workers", "2"]) == 0
    text = capsys.readouterr().out
    assert text.count("config hash") == 2
    assert len(list(out.iterdir())) == 2
    monkeypatch.setattr(runner, "code_version", lambda repo=None: "abc-dirty")
    assert cli.main(["run", paths[0], "--out", str(tmp_path / "o2"), "--resume"]) == 2
