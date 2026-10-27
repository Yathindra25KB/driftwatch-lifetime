"""E2 tables and figures from a small synthetic grid (code-behaviour checks, never evidence)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.metrics import grid_tables as gt
from driftwatch.sim import grid
from driftwatch.sim.grid import GridSpec
from driftwatch.sim.runner import run

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = np.datetime64("2019-01-07", "ns")
WIDTH = np.timedelta64(14, "D")


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source():
    from driftwatch.data.synthetic import drifting_timeline

    table, X = drifting_timeline(n_slots=12, rows_per_slot=400, drift=1.0, seed=5)
    return TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, name="synthetic")


def spec() -> GridSpec:
    return GridSpec.from_dict(
        {
            "name": "e2_t",
            "dataset": "bodmas",
            "slots": {"preset": "adr-0004", "min_malware": 5},
            "window": {"nT": 3, "nE": 6, "stride": 2},
            "ratio": {"target": 0.10, "sensitivity": 0.05},
            "model": [{"name": "lr"}],
            "e0": {"variants": ["rolling"], "random_split": False},
            "output": "unused",
            "grid": {
                "delay": [0, 1, 2, 3],
                "budget_pct": [0.5, 1.0, 2.0, 5.0],
                "policy": {"name": "periodic", "period": 3},
                "selector": {"name": "random", "calibration_fraction": 0.2},
                "seeds": [0, 1, 2, 3, 4],
                "headline": {
                    "seeds": [5, 6, 7, 8, 9],
                    "cells": [[0, 1.0], [0, 5.0], [3, 1.0], [3, 5.0], [0, 0.5], [0, 2.0]],
                },
                "chow": {
                    "seeds": [0, 1, 2, 3, 4],
                    "cells": [[0, 1.0], [0, 5.0], [3, 1.0], [3, 5.0]],
                },
                "never": {"seeds": list(range(10)), "variants": ["rolling", "rolling_chow"]},
            },
        }
    )


def plain(cfg, src, out, *, resume=False, **kw):
    return run(cfg, src, out, **kw)


@pytest.fixture(scope="module")
def grid_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("e2") / "bodmas"
    results = grid.run_grid(
        spec(), source(), root, repo_root=ROOT, require_clean=False, runner=plain
    )
    assert all(r.status == "complete" for r in results), [r.reason for r in results]
    return root


@pytest.fixture(scope="module")
def tables(grid_root: Path, tmp_path_factory):
    mod = load_script("make_tables")
    out = tmp_path_factory.mktemp("tables")
    built = mod.build(grid_root.parent, None, ("bodmas",), n_boot=300)
    return mod, built, out


def test_aaut_has_every_arm_and_seed_set(tables) -> None:
    _, built, _ = tables
    a = built["aaut"]
    roll = a[(a["variant"] == "rolling") & (a["model"] == "lr")]
    per = roll[roll["policy"] == "periodic"]
    assert set(per[per["seed_set"] == "0-4"]["delay"].astype(int)) == {0, 1, 2, 3}
    assert len(per[per["seed_set"] == "0-4"]) == 16
    assert len(per[per["seed_set"] == "0-9"]) == 6  # the headline cells only
    never = roll[roll["policy"] == "never"]
    assert set(never["seed_set"]) == {"0-4", "0-9"} and (never["labels_per_slot"] == 0).all()
    assert a["a_aut_mean"].between(0, 1).all()


def test_aaut_equals_the_mean_of_per_window_seed_means(tables, grid_root: Path) -> None:
    _, built, _ = tables
    a = built["aaut"]
    row = a[
        (a["model"] == "lr") & (a["policy"] == "periodic") & (a["delay"] == 0)
        & (a["budget_pct"] == 5.0) & (a["seed_set"] == "0-4") & (a["variant"] == "rolling")
    ].iloc[0]  # fmt: skip
    col = gt.collect(grid_root, "bodmas")
    frame = col.arms[("rolling", "lr", "periodic", 0, 5.0)][list(range(5))]
    assert row["a_aut_mean"] == pytest.approx(frame.mean(axis=1).mean())
    assert row["n_windows"] == len(frame)


def test_contrasts_have_four_primary_rows_per_seed_set_with_plain_units(tables) -> None:
    _, built, _ = tables
    c = built["contrasts"]
    assert sorted(c["contrast"].unique()) == ["C-B", "C-D1", "C-D2", "C-P"]
    assert set(c["seed_set"]) == {"0-4", "0-9"} and len(c) == 8
    d = c[c["contrast"] == "C-D1"].iloc[0]
    assert d["unit_value"] == pytest.approx(d["estimate"] / 3)
    assert d["ci_low"] <= d["estimate"] <= d["ci_high"]
    b = c[(c["contrast"] == "C-B") & (c["seed_set"] == "0-9")].iloc[0]
    assert b["labels_per_slot_plus"] > b["labels_per_slot_minus"] > 0
    expect = b["estimate"] / (b["labels_per_slot_plus"] - b["labels_per_slot_minus"]) * 100
    assert b["unit_value"] == pytest.approx(expect)
    p = c[(c["contrast"] == "C-P") & (c["seed_set"] == "0-9")].iloc[0]
    assert p["labels_per_slot_minus"] == 0 and p["min_wilcoxon_p"] == pytest.approx(2 / 1024)
    prim = c[c["role"] == "primary"]
    assert (
        prim["seed_level_wilcoxon_p_holm"].between(0, 1).all() and (prim["family_size"] == 4).all()
    )
    rob = c[c["role"] == "seed_robustness"]
    assert rob["seed_level_wilcoxon_p_holm"].isna().all()  # 5 seeds cannot go below 0.0625
    assert set(c["verdict"]) <= {
        "detected", "detected_within_margin", "reversed", "equivalent", "not_detected"
    }  # fmt: skip
    assert (c["status"] == "computed").all()
    assert (c["block_len_effective"] <= c["block_len"]).all()


def test_secondary_chow_labels_recovery_and_ledger(tables) -> None:
    _, built, _ = tables
    s = built["secondary"]
    assert set(s["kind"]) == {"delay_slope", "budget_step", "budget_concavity"}
    assert len(s[s["kind"] == "delay_slope"]) == 4
    assert len(s[s["kind"] == "budget_step"]) == 3
    assert set(built["chow"]["contrast"]) == {"C-D1", "C-D2", "C-P"}
    assert (built["chow"]["variant"] == "rolling_chow").all()
    lab = built["labels"]
    assert (lab[lab["policy"] == "never"]["n_cells"] > 0).all()
    led = built["ledger"]
    assert len(led) == 27 and (led["status"] == "complete").all()
    assert not built["recovery"].empty and not built["per_slot"].empty


def test_never_equals_periodic_at_d3_on_this_geometry_is_visible(tables) -> None:
    # nE = 6, period 3: at d = 3 no label has arrived at the single refit, so the arms agree
    _, built, _ = tables
    a = built["aaut"]
    m = a[(a["model"] == "lr") & (a["variant"] == "rolling") & (a["seed_set"] == "0-4")]
    never = m[m["policy"] == "never"]["a_aut_mean"].iloc[0]
    d3 = m[(m["policy"] == "periodic") & (m["delay"] == 3) & (m["budget_pct"] == 5.0)]
    assert d3["a_aut_mean"].iloc[0] == pytest.approx(never)


def test_outputs_are_identical_across_runs_and_figures_hash_equal(
    grid_root: Path, tmp_path: Path
) -> None:
    tab = load_script("make_tables")
    fig = load_script("make_figures")
    digests = []
    for i in range(2):
        out = tmp_path / f"t{i}"
        figs = tmp_path / f"f{i}"
        assert tab.main(
            ["--results", str(grid_root.parent), "--out", str(out), "--datasets", "bodmas",
             "--e1-root", str(tmp_path / "none"), "--n-boot", "200"]
        ) == 0  # fmt: skip
        assert fig.main(["--tables", str(out), "--out", str(figs)]) == 0
        files = sorted(out.glob("*.csv")) + sorted(figs.glob("*.png"))
        assert len(list(figs.glob("*.png"))) >= 3
        digests.append({f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
    assert digests[0] == digests[1]


def test_the_scripts_import_no_model_code(grid_root: Path, tmp_path: Path) -> None:
    scripts = (ROOT / "scripts").as_posix()
    code = f"""
import sys, importlib.util, pathlib
for name in ("make_tables", "make_figures"):
    spec = importlib.util.spec_from_file_location(name, "{scripts}/" + name + ".py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
root = pathlib.Path(r"{grid_root.parent}")
sys.modules["make_tables"].build(root, None, ("bodmas",), 50)
heavy = ("sklearn", "lightgbm")
bad = [
    k for k in sys.modules
    if k.split(".")[0] in heavy or k.startswith("driftwatch.models")
    or k == "driftwatch.sim.runner"
]
assert not bad, bad
"""
    proc = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]


def test_a_slot_table_that_disagrees_with_the_predictions_is_refused(
    grid_root: Path, tmp_path: Path
) -> None:
    ledger = [json.loads(x) for x in (grid_root / "ledger.jsonl").read_text().splitlines()]
    done = next(
        e for e in ledger if e["event"] == "complete" and "periodic-d0-b5-s0-4" in e["cell_id"]
    )
    src = Path(done["dir"])
    copy = tmp_path / "copy"
    shutil.copytree(src, copy)
    s = pd.read_parquet(copy / "slots.parquet")
    s.loc[s.index[0], "f1"] = min(1.0, float(s["f1"].iloc[0]) + 0.123)
    s.to_parquet(copy / "slots.parquet", index=False)
    with pytest.raises(gt.GridDataError, match="differs"):
        gt.load_cell(copy)


def test_a_partial_grid_still_produces_tables(grid_root: Path, tmp_path: Path) -> None:
    part = tmp_path / "bodmas"
    part.mkdir()
    keep = []
    for line in (grid_root / "ledger.jsonl").read_text().splitlines():
        e = json.loads(line)
        if "never" in e["cell_id"] or "periodic-d0-b5-s0-4-roll" in e["cell_id"]:
            keep.append(line)
    (part / "ledger.jsonl").write_text("\n".join(keep) + "\n", encoding="utf-8")
    mod = load_script("make_tables")
    built = mod.build(tmp_path, None, ("bodmas",), n_boot=100)
    assert not built["aaut"].empty
    c = built["contrasts"]
    done = c[c["status"] == "computed"]
    assert set(done["contrast"]) <= {"C-P"}  # only the contrast with both arms is computed
    gone = c[c["status"] == "not_computed"]
    assert {"C-D1", "C-D2", "C-B"} <= set(gone["contrast"])  # reported, never silently dropped
    assert (gone["reason"].str.len() > 0).all()
    assert (gone["verdict"] == "not_computed").all()
    # the Holm family keeps its registered size, with the missing contrasts at p = 1
    assert (c[c["role"] == "primary"]["family_size"] == 4).all()
    led = built["ledger"]
    assert len(led) == 27 and "planned" in set(led["status"])  # unstarted cells are listed


def test_units_signs_and_counts_follow_the_registered_definitions(tables, grid_root) -> None:
    _, built, _ = tables
    s = built["secondary"]
    slope = s[(s["kind"] == "delay_slope") & (s["budget_pct"] == 5.0)].iloc[0]
    assert slope["unit"].startswith("AUT lost per slot of delay (positive")
    assert slope["unit_value"] == pytest.approx(-slope["estimate"])  # lost = minus the slope
    step = s[s["kind"] == "budget_step"].iloc[0]
    assert step["labels_hi"] > step["labels_lo"] > 0
    assert step["labels_per_slot"] == pytest.approx(step["labels_hi"] - step["labels_lo"])
    # counts are those of the seeds in the row, not of the last block read
    col = gt.collect(grid_root, "bodmas")
    key = ("rolling", "lr", "periodic", 0, 5.0)
    both = col.counts_for(key, range(10))["labels_queried_per_slot"]
    first = col.counts_for(key, range(5))["labels_queried_per_slot"]
    blocks = {tuple(sorted(s)): c["labels_queried_per_slot"] for s, c in col.counts_blocks[key]}
    assert first == pytest.approx(blocks[(0, 1, 2, 3, 4)])
    assert both == pytest.approx(np.mean(list(blocks.values())), rel=0.2)
    c = built["contrasts"]
    a = c[(c["contrast"] == "C-B") & (c["seed_set"] == "0-4")].iloc[0]
    assert a["labels_per_slot_plus"] == pytest.approx(first)


def test_verdict_is_three_way_and_reads_direction() -> None:
    from driftwatch.metrics.stats import Estimate

    assert gt.verdict(Estimate(0.05, 0.03, 0.07)) == "detected"
    assert gt.verdict(Estimate(0.004, 0.001, 0.008)) == "detected_within_margin"
    assert gt.verdict(Estimate(-0.05, -0.07, -0.03)) == "reversed"
    assert gt.verdict(Estimate(0.001, -0.004, 0.006)) == "equivalent"
    assert gt.verdict(Estimate(0.01, -0.03, 0.05)) == "not_detected"


def test_holm_family_has_fixed_size_and_missing_contrasts_count_as_one() -> None:
    rows = [
        {"dataset": "bodmas", "model": "lr", "contrast": "C-D1", "role": "primary",
         "status": "computed", "seed_level_wilcoxon_p": 0.002},
        {"dataset": "bodmas", "model": "lr", "contrast": "C-P", "role": "primary",
         "status": "not_computed", "seed_level_wilcoxon_p": float("nan")},
    ]  # fmt: skip
    out = gt.add_holm(pd.DataFrame(rows), ["bodmas", "lamda"], ["lr", "lgbm"])
    assert (out["family_size"] == 16).all()
    # 16 hypotheses: the smallest p is multiplied by 16, not by the 2 rows that are present
    assert out.loc[0, "seed_level_wilcoxon_p_holm"] == pytest.approx(0.002 * 16)


def test_window_stage_coarseness_and_effective_block() -> None:
    from driftwatch.metrics import stats

    assert stats.effective_block(3, 2) == 2
    assert stats.window_stage_is_coarse(3, 2) and stats.window_stage_is_coarse(3, 5)
    assert not stats.window_stage_is_coarse(3, 6) and not stats.window_stage_is_coarse(4, 16)


def test_planned_ids_match_the_grid_spec_cells() -> None:
    import yaml

    from driftwatch.sim.cell_ids import planned_ids

    raw = yaml.safe_load((ROOT / "configs" / "e2_lamda.yaml").read_text(encoding="utf-8"))
    cells = GridSpec.from_file(ROOT / "configs" / "e2_lamda.yaml").cells()
    assert planned_ids(raw) == [c.cell_id for c in cells]
    assert len(set(planned_ids(raw))) == 27


def test_mixed_code_versions_are_refused(grid_root: Path, tmp_path: Path) -> None:
    part = tmp_path / "bodmas"
    part.mkdir()
    lines = []
    n_complete = 0
    for line in (grid_root / "ledger.jsonl").read_text().splitlines():
        e = json.loads(line)
        if e["event"] == "complete":
            n_complete += 1
            if n_complete % 2 == 0:
                e["code_version"] = "deadbee"
        lines.append(json.dumps(e))
    (part / "ledger.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(gt.GridDataError, match="code versions"):
        gt.collect(part, "bodmas")


def test_the_e0_window_level_gap_is_the_prior_matched_comparator(tmp_path: Path) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "tests"))
    from test_runner_sim import baseline_config, make_source  # noqa: PLC0415

    cfg = baseline_config(
        seeds=[0, 1],
        model=[{"name": "lr"}],
        e0={"variants": ["rolling"], "random_split": True, "per_slot_random_split": True},
    )
    summary = run(cfg, make_source(), tmp_path / "e1", repo_root=ROOT)
    t = gt.rq1_table(summary.dir, "bodmas", n_boot=200)
    sec = t[t["comparator"].str.startswith("E0")].iloc[0]
    w = pd.read_parquet(summary.dir / "windows.parquet")
    w = w[(w["variant"] == "rolling") & (w["series"] == "time_aware")]
    expect = float(
        (w["f1_random_split"] - w["aut"])
        .groupby(w["window_id"].str.split("|", n=1).str[1])
        .mean()
        .mean()
    )
    assert sec["gap"] == pytest.approx(expect, abs=1e-9)
    prim = t[t["comparator"].str.startswith("per-slot")].iloc[0]
    assert prim["role"] == "primary" and sec["role"] == "secondary"
