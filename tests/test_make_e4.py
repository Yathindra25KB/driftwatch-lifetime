"""E4 tables and figure on a small synthetic grid (code-behaviour checks only, never evidence)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml
from test_grid import ROOT, plain_runner, source
from test_grid_e4 import spec_dict
from test_make_e3 import load_script

from driftwatch.sim import grid
from driftwatch.sim.grid_e4 import E4Spec


@pytest.fixture(scope="module")
def e4_results(tmp_path_factory) -> tuple[Path, Path]:
    base = tmp_path_factory.mktemp("e4")
    d = spec_dict(
        policies={
            "never": {"observe": ["ks", "mmd", "domain_clf", "p_uniformity"]},
            "periodic": {"period": 3},
            "monitor": {"triggers": ["ks", "mmd", "domain_clf", "p_uniformity"], "min_gap": 2},
            "matched": True,
        },
        seeds=[0, 1],
    )
    spec_dir = base / "configs"
    spec_dir.mkdir()
    (spec_dir / "e4_bodmas.yaml").write_text(yaml.safe_dump(d), encoding="utf-8")
    results = base / "results"
    grid.run_grid(E4Spec.from_dict(d), source(), results / "bodmas", repo_root=ROOT,
                  require_clean=False, runner=plain_runner)  # fmt: skip
    return results, spec_dir


@pytest.mark.slow
def test_make_e4_writes_every_table_and_the_figure(e4_results, tmp_path: Path) -> None:
    results, spec_dir = e4_results
    mod = load_script("make_e4")
    fig = tmp_path / "e4.png"
    args = ["--results", str(results), "--out", str(tmp_path), "--figure", str(fig)]
    rc = mod.main([*args, "--spec-dir", str(spec_dir), "--datasets", "bodmas", "--n-boot", "200"])
    assert rc == 0 and fig.exists()
    pol = pd.read_csv(tmp_path / "e4_policies.csv")
    assert {"labels_per_window", "refits_per_window", "a_aut_mean"} <= set(pol.columns)
    assert pol["labels_per_window"].nunique() == 1  # matched labels spent in every arm
    assert (pol.loc[pol["arm"] == "never", "refits_per_window"] == 0).all()
    con = pd.read_csv(tmp_path / "e4_contrasts.csv")
    assert set(con["family"]) == {"M-P", "M-C"}
    assert (con["status"] == "computed").all()
    assert (con.groupby("family")["family_size"].first() == 1 * 1 * 4 * 2).all()
    assert (con["seed_level_wilcoxon_p_holm"] >= con["seed_level_wilcoxon_p"] - 1e-12).all()
    mc = con[con["family"] == "M-C"]
    assert (mc["refits_per_window_minus"] <= mc["refits_per_window_plus"] + 1e-12).all()
    mon = pd.read_csv(tmp_path / "e4_monitors.csv")
    obs = mon[mon["context"] == "observe_never"]
    assert len(obs) == 4 and (obs["status"] == "computed").all()
    trig = mon[mon["context"] == "trigger_arm"]
    assert len(trig) == 4 * 2
    led = pd.read_csv(tmp_path / "e4_ledger.csv")
    assert (led["status"] == "complete").all() and len(led) == 19


@pytest.mark.slow
def test_tables_regenerate_identically(e4_results, tmp_path: Path) -> None:
    results, spec_dir = e4_results
    mod = load_script("make_e4")
    for sub in ("a", "b"):
        mod.main(["--results", str(results), "--out", str(tmp_path / sub), "--figure",
                  str(tmp_path / sub / "f.png"), "--spec-dir", str(spec_dir), "--datasets",
                  "bodmas", "--n-boot", "100"])  # fmt: skip
    for name in ("e4_policies.csv", "e4_contrasts.csv", "e4_monitors.csv"):
        a = (tmp_path / "a" / name).read_bytes()
        assert a == (tmp_path / "b" / name).read_bytes(), name
