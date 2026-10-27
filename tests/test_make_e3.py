"""E3 grid spec, tables and figure on a small synthetic grid (code-behaviour checks only)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.sim import grid
from driftwatch.sim.cell_ids import planned_ids
from driftwatch.sim.grid_e3 import E3Spec, load_spec
from driftwatch.sim.runner import run

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = np.datetime64("2019-01-07", "ns")
WIDTH = np.timedelta64(14, "D")


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def source():
    from driftwatch.data.synthetic import drifting_timeline

    table, X = drifting_timeline(n_slots=12, rows_per_slot=400, drift=1.0, seed=5)
    return TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, name="synthetic")


def spec_dict() -> dict:
    return {
        "name": "e3_t",
        "dataset": "bodmas",
        "slots": {"preset": "adr-0004", "min_malware": 5},
        "window": {"nT": 3, "nE": 6, "stride": 2},
        "ratio": {"target": 0.10, "sensitivity": 0.05},
        "model": [{"name": "lr"}],
        "e0": {"variants": ["rolling"], "random_split": False},
        "output": "unused",
        "nonconf": {
            "score": "probability",
            "holdout_fraction": 0.2,
            "min_per_class": 10,
            "buffer_size": 400,
            "calibration_in_pool": False,
        },  # fmt: skip
        "grid": {
            "policy": {"name": "periodic", "period": 3},
            "delay": [0, 3],
            "budget_pct": [5.0, 10.0],
            "selectors": ["random", "uncertainty", "credibility"],
            "calibration_fraction": 0.2,
            "score": "probability",
            "seeds": [0, 1, 2, 3, 4],
            "extra_seeds": [5, 6, 7, 8, 9],
            "anchor": {
                "selector": "credibility",
                "delay": 0,
                "budget_pct": 10.0,
                "reserved": [0.0, 0.1, 0.4],
                "score_comparison": "centroid",
            },  # fmt: skip
        },
    }


def plain(cfg, src, out, *, resume=False, **kw):
    return run(cfg, src, out, **kw)


@pytest.fixture(scope="module")
def e3_root(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("e3") / "bodmas"
    spec = E3Spec.from_dict(spec_dict())
    res = grid.run_grid(spec, source(), root, repo_root=ROOT, require_clean=False, runner=plain)
    assert all(r.status == "complete" for r in res), [r.reason for r in res if r.reason]
    return root


def spec_dir_for(root: Path) -> Path:
    """A directory holding this test grid's spec as e3_bodmas.yaml (for the planned cell ids)."""
    d = root.parent / "specs"
    d.mkdir(exist_ok=True)
    (d / "e3_bodmas.yaml").write_text(yaml.safe_dump(spec_dict()), encoding="utf-8")
    return d


def test_spec_expands_to_the_registered_cells() -> None:
    cells = E3Spec.from_dict(spec_dict()).cells()
    roles = [c.role for c in cells]
    assert (roles.count("main"), roles.count("extra_seeds")) == (12, 12)
    assert (roles.count("ablation"), roles.count("score")) == (3, 1)
    assert planned_ids(spec_dict()) == [c.cell_id for c in cells]
    trap = [c for c in cells if c.calibration_fraction == 0.0]
    assert len(trap) == 1 and trap[0].role == "ablation"


def test_trap_cell_config_names_the_trap_and_others_do_not() -> None:
    spec = E3Spec.from_dict(spec_dict())
    for c in spec.cells():
        cfg = spec.config(c)
        assert cfg.nonconf is not None
        assert cfg.nonconf["trap_selected_calibration"] is (c.calibration_fraction == 0.0)
        assert cfg.nonconf["score"] == c.score and cfg.selector == c.selector


def test_bad_e3_specs_fail_at_parse_time() -> None:
    d = spec_dict()
    d["grid"]["selectors"] = ["uncertainty", "credibility"]
    with pytest.raises(grid.GridError, match="random"):
        E3Spec.from_dict(d)
    d = spec_dict()
    d["grid"]["extra_seeds"] = [0, 9]
    with pytest.raises(grid.GridError, match="extra_seeds"):
        E3Spec.from_dict(d)


def test_load_spec_dispatches_on_the_grid_block(tmp_path: Path) -> None:
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(spec_dict()), encoding="utf-8")
    assert isinstance(load_spec(p), E3Spec)
    assert load_spec(ROOT / "configs" / "e2_lamda.yaml").__class__.__name__ == "GridSpec"
    assert len(load_spec(ROOT / "configs" / "e3_bodmas.yaml").cells()) == 28
    assert len(load_spec(ROOT / "configs" / "e3_lamda.yaml").cells()) == 28


def test_tables_have_the_registered_contrasts(e3_root: Path) -> None:
    mod = load_script("make_e3")
    built = mod.build(e3_root.parent, ("bodmas",), n_boot=300, spec_dir=spec_dir_for(e3_root))
    c = built["contrasts"]
    inter = c[c["contrast"].str.startswith("I_")]
    prim = inter[inter["role"] == "primary"]
    assert len(prim) == 4 and set(prim["seed_set"]) == {"0-9"}  # 2 selectors x 2 budgets
    assert (inter[inter["role"] == "seed_robustness"]["seed_set"] == "0-4").all()
    assert (prim["family_size"] == 4).all() and prim["seed_level_wilcoxon_p_holm"].between(
        0, 1
    ).all()
    # the interaction is the difference of the two advantages
    for _, r in prim.iterrows():
        a = c[(c["selector"] == r["selector"]) & (c["budget_pct"] == r["budget_pct"])
              & (c["seed_set"] == "0-9") & (c["model"] == r["model"])]  # fmt: skip
        d0 = a[a["contrast"] == f"adv_d0_{r['selector']}"]["estimate"].iloc[0]
        d3 = a[a["contrast"] == f"adv_d3_{r['selector']}"]["estimate"].iloc[0]
        assert r["estimate"] == pytest.approx(d0 - d3)
    assert inter["delay_axis_note"].str.contains("single refit").all()  # nE = 6, period 3


def test_selection_ablation_and_score_tables(e3_root: Path) -> None:
    mod = load_script("make_e3")
    built = mod.build(e3_root.parent, ("bodmas",), n_boot=200, spec_dir=spec_dir_for(e3_root))
    sel = built["selection"]
    # equal labels spent across the three arms at each delay and budget
    main = sel[(sel["reserved_share"] == 0.2) & (sel["score"] == "probability")
               & (sel["seed_set"] == "0-4")]  # fmt: skip
    for (_, _), g in main.groupby(["delay", "budget_pct"]):
        assert g["labels_per_slot"].nunique() == 1 and len(g) == 3
    ab = built["ablation"]
    assert set(ab["reserved_share"]) == {0.0, 0.1, 0.2, 0.4}
    assert ab[ab["reserved_share"] == 0.0]["role"].iloc[0] == "trap_demonstration"
    sc = built["score"]
    assert set(sc["score"]) == {"probability", "centroid"}
    led = built["ledger"]
    assert len(led) == 28 and (led["status"] == "complete").all()


def test_outputs_are_identical_across_runs_and_the_figure_exists(
    e3_root: Path, tmp_path: Path
) -> None:
    mod = load_script("make_e3")
    digests = []
    for i in range(2):
        out = tmp_path / f"t{i}"
        fig = tmp_path / f"f{i}" / "e3_selection.png"
        args = ["--results", str(e3_root.parent), "--out", str(out), "--figure", str(fig),
                "--datasets", "bodmas", "--n-boot", "200",
                "--spec-dir", str(spec_dir_for(e3_root))]  # fmt: skip
        assert mod.main(args) == 0
        files = sorted(out.glob("*.csv")) + [fig]
        digests.append({f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
    assert digests[0] == digests[1] and "e3_selection.png" in digests[0]


def test_the_script_imports_no_model_code(e3_root: Path) -> None:
    scripts = (ROOT / "scripts").as_posix()
    code = f"""
import sys, importlib.util, pathlib
spec = importlib.util.spec_from_file_location("make_e3", "{scripts}/make_e3.py")
m = importlib.util.module_from_spec(spec)
sys.modules["make_e3"] = m
spec.loader.exec_module(m)
m.build(pathlib.Path(r"{e3_root.parent}"), ("bodmas",), 50)
bad = [k for k in sys.modules if k.split(".")[0] in ("sklearn", "lightgbm")
       or k.startswith("driftwatch.models") or k == "driftwatch.sim.runner"]
assert not bad, bad
"""
    proc = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr[-2000:]


def test_cli_status_for_an_e3_spec(tmp_path: Path, capsys) -> None:
    from driftwatch import cli

    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(spec_dict()), encoding="utf-8")
    assert cli.main(["grid", str(p), "--status", "--out", str(tmp_path / "r")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["planned"] == 28 and report["counts"] == {"planned": 28}
