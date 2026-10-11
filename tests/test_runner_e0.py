"""E0 end to end on seeded synthetic timelines (code-behaviour checks, never evidence).

The runner fits on the training window, scores each evaluation slot on the slicer's public
view only, and maps predictions back to labels with the slot-bound handles. These tests pin
that mapping, determinism, the per-slot rows, the fit cache and the failure rule.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import driftwatch.models as models_pkg
from driftwatch.data.slicer import WindowSpec, slice_windows
from driftwatch.data.synthetic import drifting_timeline
from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.models.linear import LogisticDetector
from driftwatch.sim.config import RunConfig
from driftwatch.sim.runner import run

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = np.datetime64("2019-01-07", "ns")
WIDTH = np.timedelta64(14, "D")


def make_source(drift: float = 1.0, seed: int = 0) -> tuple[TableSource, pd.DataFrame]:
    table, X = drifting_timeline(n_slots=16, rows_per_slot=400, drift=drift, seed=seed)
    source = TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, name="synthetic")
    return source, table


def make_config(**over) -> RunConfig:
    d = {
        "name": "t",
        "dataset": "bodmas",
        "slots": {"preset": "adr-0004", "min_malware": 5},
        "window": {"nT": 3, "nE": 6, "stride": 2},
        "ratio": {"target": 0.10, "sensitivity": 0.05},
        "seeds": [0, 1],
        "model": [{"name": "lr"}, {"name": "lgbm", "profile": "fast", "n_jobs": 2}],
        "policy": "never",
        "e0": {
            "variants": ["rolling", "rolling_chow", "sensitivity", "single_run"],
            "random_split": True,
        },
        "output": "unused",
    }
    d.update(over)
    return RunConfig.from_dict(d)


@pytest.fixture(scope="module")
def finished(tmp_path_factory: pytest.TempPathFactory):
    source, table = make_source()
    out = tmp_path_factory.mktemp("e0")
    summary = run(make_config(), source, out, repo_root=ROOT)
    return source, table, summary


def tables(summary):
    d = summary.dir
    return (
        pd.read_parquet(d / "windows.parquet"),
        pd.read_parquet(d / "slots.parquet"),
        pd.read_parquet(d / "predictions.parquet"),
        json.loads((d / "run.json").read_text(encoding="utf-8")),
    )


# --- shape ----------------------------------------------------------------------------------


def test_row_counts_follow_the_window_formula(finished) -> None:
    _, _, summary = finished
    windows, slots, _, _ = tables(summary)
    # 16 slots: rolling stride 2 -> 4 windows; Chow stride 3 -> 3; 5% -> 4; single run -> 1
    first = windows[windows["seed"] == 0]  # window ids carry the seed through the spec digest
    per_variant = first.groupby("variant")["window_id"].nunique().to_dict()
    assert per_variant == {"rolling": 4, "rolling_chow": 3, "sensitivity": 4, "single_run": 1}
    assert len(windows) == (4 + 3 + 4 + 1) * 2 * 2  # x seeds x models
    assert len(slots) == (4 * 6 + 3 * 6 + 4 * 6 + 13) * 2 * 2
    keys = ["variant", "model", "ratio", "seed", "window_id", "slot_id"]
    assert not slots.duplicated(keys).any()  # one row per (config, model, seed, window, slot)
    assert set(slots["config_hash"]) == {summary.config_hash}


def test_every_slot_row_respects_c3_and_reports_the_ratio(finished) -> None:
    _, _, summary = finished
    _, slots, _, _ = tables(summary)
    assert (slots["achieved_ratio"] <= slots["target_ratio"] + 1e-12).all()
    assert set(slots["c3_status"]) <= {"at_target", "below_target"}
    assert set(np.round(slots["target_ratio"].unique(), 2)) == {0.10, 0.05}
    assert (slots["n_malware"] + slots["n_benign"] == slots["n"]).all()
    for col in ("tp", "fp", "fn", "tn"):
        assert (slots[col] >= 0).all()
    assert ((slots["f1"] >= 0) & (slots["f1"] <= 1)).all()


def test_run_record_carries_provenance(finished) -> None:
    _, _, summary = finished
    *_, record = tables(summary)
    assert record["status"] == "complete"
    assert record["config_hash"] == summary.config_hash
    assert record["seeds"] == [0, 1]
    for key in ("code_version", "lock_sha256", "packages", "machine", "source", "models"):
        assert key in record
    assert record["packages"]["lightgbm"] not in ("", "unknown")
    assert record["machine"]["cpu_count"] >= 1
    assert record["predictions_sha256"] == summary.predictions_sha256
    assert {m["name"] for m in record["models"]} == {"lr", "lgbm"}


# --- the handle mapping and the public view ----------------------------------------------------


def test_stored_labels_and_rows_are_the_c3_kept_rows_of_each_slot(finished) -> None:
    source, table, summary = finished
    _, slots, preds, _ = tables(summary)
    label_by_row = dict(zip(table["row_id"], table["label"], strict=True))
    spec = WindowSpec(nT=3, nE=6, stride=2, target_ratio=0.10, min_malware=5, seed=1)
    expected: dict[str, set[int]] = {}
    for window in slice_windows(source, spec):
        for slot in window.eval_slots():
            expected[(window.plan.window_id, slot.ref.slot_id)] = set(slot.row_id.tolist())
    sel = preds[(preds["variant"] == "rolling") & (preds["model"] == "lr") & (preds["seed"] == 1)]
    assert len(sel) > 0
    for (window_id, slot_id), grp in sel.groupby(["window_id", "slot_id"]):
        assert set(grp["row_id"]) == expected[(window_id, slot_id)]
        assert grp["row_id"].is_unique
        truth = np.array([label_by_row[r] for r in grp["row_id"]])
        assert np.array_equal(grp["y_true"].to_numpy(), truth)
        assert np.array_equal(grp["pred"].to_numpy(), (grp["proba"].to_numpy() > 0.5).astype(int))


def test_each_stored_probability_is_the_score_of_that_rows_own_features(finished) -> None:
    """Refit outside the runner and score the slot in its own row order: the probability
    stored under a row id must be that row's, not a neighbour's (handle mapping)."""
    source, _, summary = finished
    _, _, preds, _ = tables(summary)
    spec = WindowSpec(nT=3, nE=6, stride=2, target_ratio=0.10, min_malware=5, seed=0)
    sel = preds[(preds["variant"] == "rolling") & (preds["model"] == "lr") & (preds["seed"] == 0)]
    checked = 0
    for window in slice_windows(source, spec):
        model = LogisticDetector(seed=0).fit(window.train.X, window.train.y, "ref")
        for slot in window.eval_slots():
            stored = sel[
                (sel["window_id"] == window.plan.window_id) & (sel["slot_id"] == slot.ref.slot_id)
            ].set_index("row_id")["proba"]
            direct = model.predict_proba(slot.X, "ref")  # slot order, no public permutation
            got = stored.loc[slot.row_id].to_numpy()
            assert np.allclose(got, direct.astype(np.float32), atol=1e-6)
            checked += len(direct)
    assert checked > 5000


def test_slot_rows_are_the_confusion_of_the_stored_predictions(finished) -> None:
    _, _, summary = finished
    _, slots, preds, _ = tables(summary)
    key = ["variant", "model", "ratio", "seed", "window_id", "slot_id"]
    g = (
        preds.assign(
            tp=(preds.y_true == 1) & (preds.pred == 1),
            fp=(preds.y_true == 0) & (preds.pred == 1),
            fn=(preds.y_true == 1) & (preds.pred == 0),
        )
        .groupby(key)[["tp", "fp", "fn"]]
        .sum()
    )
    merged = slots.set_index(key).join(g, rsuffix="_p")
    assert (merged["tp"] == merged["tp_p"]).all()
    assert (merged["fp"] == merged["fp_p"]).all()
    assert (merged["fn"] == merged["fn_p"]).all()


class SpyDetector(LogisticDetector):
    """Records every feature matrix it is asked to score."""

    name = "spy"
    seen: list[np.ndarray] = []

    def _score(self, X):
        SpyDetector.seen.append(np.array(X, copy=True))
        return super()._score(X)


def test_models_are_scored_on_the_public_view_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setitem(models_pkg._REGISTRY, "spy", SpyDetector)
    SpyDetector.seen = []
    source, _ = make_source()
    cfg = make_config(
        seeds=[0],
        model=[{"name": "spy"}],
        e0={"variants": ["rolling"], "random_split": False},
    )
    run(cfg, source, tmp_path, repo_root=ROOT)
    spec = WindowSpec(nT=3, nE=6, stride=2, target_ratio=0.10, min_malware=5, seed=0)
    reference = [
        np.array(slot.public().X)
        for window in slice_windows(source, spec)
        for slot in window.eval_slots()
    ]
    assert len(SpyDetector.seen) == len(reference) == 24
    for got, want in zip(SpyDetector.seen, reference, strict=True):
        assert np.array_equal(got, want)  # same rows in the same seeded, label-free order


# --- determinism, cache, failure -----------------------------------------------------------------


def test_rerun_gives_identical_predictions_and_tables(finished, tmp_path: Path) -> None:
    source, _, first = finished
    again = run(make_config(), make_source()[0], tmp_path, repo_root=ROOT)
    assert again.predictions_sha256 == first.predictions_sha256
    w1, s1, p1, _ = tables(first)
    w2, s2, p2, _ = tables(again)
    pd.testing.assert_frame_equal(s1, s2)
    pd.testing.assert_frame_equal(p1, p2)
    timing = [c for c in w1.columns if c.endswith("_seconds")]
    pd.testing.assert_frame_equal(w1.drop(columns=timing), w2.drop(columns=timing))


def test_a_different_seed_changes_the_predictions_hash(tmp_path: Path) -> None:
    source, _ = make_source()
    one = run(
        make_config(seeds=[0], e0={"variants": ["rolling"], "random_split": False}),
        source,
        tmp_path / "a",
        repo_root=ROOT,
    )
    two = run(
        make_config(seeds=[1], e0={"variants": ["rolling"], "random_split": False}),
        source,
        tmp_path / "b",
        repo_root=ROOT,
    )
    assert one.predictions_sha256 != two.predictions_sha256


def test_deterministic_linear_fits_are_reused_across_seeds_and_variants(finished) -> None:
    _, _, summary = finished
    windows, _, _, _ = tables(summary)
    lr = windows[windows["model"] == "lr"]
    assert lr[lr["seed"] == 1]["fit_reused"].all()  # the seed cannot change a convex fit
    assert (~lr[lr["seed"] == 0]["fit_reused"]).any()
    assert (lr[lr["fit_reused"]]["fit_seconds"] >= 0).all()
    lgbm = windows[(windows["model"] == "lgbm") & (windows["seed"] == 1)]
    assert (~lgbm["fit_reused"]).any()  # bagging uses the seed: a new fit per seed


def test_a_finished_run_is_not_overwritten(tmp_path: Path) -> None:
    source, _ = make_source()
    cfg = make_config(seeds=[0], e0={"variants": ["rolling"], "random_split": False})
    run(cfg, source, tmp_path, repo_root=ROOT)
    with pytest.raises(FileExistsError):
        run(cfg, source, tmp_path, repo_root=ROOT)
    run(cfg, source, tmp_path, repo_root=ROOT, overwrite=True)


def test_cli_run_writes_results_and_reports_the_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import yaml

    from driftwatch import cli

    monkeypatch.setattr(
        "driftwatch.data.presets.cached_source", lambda dataset, root="data", **kw: make_source()[0]
    )
    d = make_config(seeds=[0], e0={"variants": ["rolling"], "random_split": False}).to_dict()
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump(d), encoding="utf-8")
    assert cli.main(["run", str(path), "--out", str(tmp_path / "out")]) == 0
    out = capsys.readouterr().out
    assert "config hash" in out and "predictions sha256" in out
    (run_dir,) = list((tmp_path / "out").iterdir())
    assert (run_dir / "run.json").exists() and (run_dir / "predictions.parquet").exists()
    assert cli.main(["run", str(path), "--out", str(tmp_path / "out")]) == 2  # no overwrite
    assert cli.main(["run", str(path), "--out", str(tmp_path / "out"), "--overwrite"]) == 0


def test_cli_run_rejects_an_invalid_config(tmp_path: Path) -> None:
    from driftwatch import cli

    path = tmp_path / "bad.yaml"
    path.write_text("dataset: bodmas\npolicy: periodic\n", encoding="utf-8")
    assert cli.main(["run", str(path)]) == 2


def test_a_variant_without_a_window_is_an_error_not_an_empty_result(tmp_path: Path) -> None:
    source, _ = make_source()
    cfg = make_config(
        seeds=[0],
        window={"nT": 10, "nE": 10, "stride": 1},  # needs 20 slots; the source has 16
        e0={"variants": ["rolling"], "random_split": False},
    )
    with pytest.raises(RuntimeError, match="no window"):
        run(cfg, source, tmp_path, repo_root=ROOT)


class FailingDetector(LogisticDetector):
    name = "failing"

    def _fit(self, X, y):
        raise RuntimeError("boom")


def test_a_failure_is_recorded_and_raised(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(models_pkg._REGISTRY, "failing", FailingDetector)
    source, _ = make_source()
    cfg = make_config(
        seeds=[0],
        model=[{"name": "failing"}],
        e0={"variants": ["rolling"], "random_split": False},
    )
    with pytest.raises(RuntimeError, match="boom"):
        run(cfg, source, tmp_path, repo_root=ROOT)
    (failed,) = list(tmp_path.glob("*/run_failed.json"))
    record = json.loads(failed.read_text(encoding="utf-8"))
    assert record["status"] == "failed" and "boom" in record["error"]
    assert not list(tmp_path.glob("*/run.json"))


# --- the pipeline measures decay (planted drift) -------------------------------------------------


def test_planted_drift_puts_aut_below_the_random_split_f1(finished) -> None:
    _, _, summary = finished
    windows, _, _, _ = tables(summary)
    lr = windows[(windows["variant"] == "rolling") & (windows["model"] == "lr")]
    assert lr["f1_random_split"].notna().all()
    assert lr["f1_random_split"].mean() - lr["aut"].mean() > 0.05


def test_no_drift_leaves_no_gap(tmp_path: Path) -> None:
    source, _ = make_source(drift=0.0)
    cfg = make_config(
        seeds=[0],
        model=[{"name": "lr"}],
        e0={"variants": ["rolling"], "random_split": True},
    )
    windows = pd.read_parquet(run(cfg, source, tmp_path, repo_root=ROOT).dir / "windows.parquet")
    assert abs(windows["f1_random_split"].mean() - windows["aut"].mean()) < 0.08
