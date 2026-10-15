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
    assert c["wilcoxon_p_holm"].between(0, 1).all()


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
    assert set(built["contrasts"]["contrast"]) <= {"C-P"}  # only the contrast with both arms
