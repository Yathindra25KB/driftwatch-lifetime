"""E1 figure: F1 per evaluation slot, random split vs time-aware, from stored predictions only."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftwatch.sim.runner import run

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_runner_sim import baseline_config, make_source  # noqa: E402

SCRIPT = ROOT / "scripts" / "make_e1_figure.py"


def load_script():
    spec = importlib.util.spec_from_file_location("make_e1_figure", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_e1_figure"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def e1_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("e1")
    cfg = baseline_config(
        seeds=[0],
        model=[{"name": "lr"}, {"name": "lgbm", "profile": "fast", "n_jobs": 1}],
        e0={"variants": ["rolling"], "random_split": True, "per_slot_random_split": True},
    )
    return run(cfg, make_source(), out, repo_root=ROOT)


def f1(y: np.ndarray, p: np.ndarray) -> float:
    tp = int(((y == 1) & (p == 1)).sum())
    fp = int(((y == 0) & (p == 1)).sum())
    fn = int(((y == 1) & (p == 0)).sum())
    return 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)


def test_per_slot_table_matches_f1_computed_directly_from_predictions(e1_run) -> None:
    mod = load_script()
    table = mod.per_slot_table({"toy": e1_run.dir})
    assert set(table["series"]) == {"time_aware", "random_split"}
    assert set(table["model"]) == {"lr", "lgbm"}
    preds = pd.read_parquet(e1_run.dir / "predictions.parquet")
    one = preds[
        (preds["model"] == "lr") & (preds["series"] == "random_split") & (preds["seed"] == 0)
    ]
    # window means over seeds are checked on one cell: seed 0, first window, first slot
    w0 = sorted(one["window_id"].unique())[0]
    s0 = one[one["window_id"] == w0].iloc[0]["slot_id"]
    cell = one[(one["window_id"] == w0) & (one["slot_id"] == s0)]
    direct = f1(cell["y_true"].to_numpy(), cell["pred"].to_numpy())
    assert direct == pytest.approx(
        mod.slot_f1(preds, "lr", "random_split", seed=0, window_id=w0, slot_id=s0)
    )


def test_figure_and_tables_are_written_and_have_both_series(e1_run, tmp_path: Path) -> None:
    mod = load_script()
    out_png = tmp_path / "fig" / "e1_random_vs_time.png"
    out_dir = tmp_path / "tables"
    rc = mod.main(
        ["--run", f"toy={e1_run.dir}", "--out-figure", str(out_png), "--out-tables", str(out_dir)]
    )
    assert rc == 0
    assert out_png.exists() and out_png.stat().st_size > 5_000
    per_slot = pd.read_csv(out_dir / "e1_per_slot.csv")
    summary = pd.read_csv(out_dir / "e1_summary.csv")
    assert {"dataset", "model", "series", "slot_position", "mean_f1", "min_f1", "max_f1"} <= set(
        per_slot.columns
    )
    assert {
        "dataset",
        "model",
        "n_windows",
        "n_slots",
        "aut_time_aware",
        "aut_random_split",
    } <= set(summary.columns)
    assert (summary["n_windows"] > 0).all()
    assert per_slot["mean_f1"].between(0, 1).all()


def test_the_script_fits_nothing_and_imports_no_model_code(e1_run, tmp_path: Path) -> None:
    driver = tmp_path / "drive.py"
    lines = [
        "import sys, importlib.util",
        f"spec = importlib.util.spec_from_file_location('m', {str(SCRIPT)!r})",
        "m = importlib.util.module_from_spec(spec)",
        "spec.loader.exec_module(m)",
        "rc = m.main(sys.argv[1:])",
        "prefixes = ('driftwatch.models', 'sklearn', 'lightgbm')",
        "bad = [k for k in sys.modules if k.startswith(prefixes)]",
        "print('RC', rc, 'BAD', bad)",
    ]
    driver.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args = [
        "--run",
        f"toy={e1_run.dir}",
        "--out-figure",
        str(tmp_path / "f.png"),
        "--out-tables",
        str(tmp_path / "t"),
    ]
    done = subprocess.run(
        [sys.executable, "-I", str(driver), *args], capture_output=True, text=True
    )
    assert "RC 0 BAD []" in done.stdout, done.stdout + done.stderr


def test_a_run_without_the_per_slot_series_is_refused(tmp_path: Path) -> None:
    mod = load_script()
    cfg = baseline_config(seeds=[0], e0={"variants": ["rolling"], "random_split": False})
    plain = run(cfg, make_source(), tmp_path, repo_root=ROOT)
    with pytest.raises(ValueError, match="random_split"):
        mod.per_slot_table({"toy": plain.dir})


def test_a_window_is_counted_once_across_seeds(tmp_path: Path) -> None:
    """window_id carries the seed through the spec digest; the window is the same window."""
    mod = load_script()
    cfg = baseline_config(
        seeds=[0, 1],
        e0={"variants": ["rolling"], "random_split": True, "per_slot_random_split": True},
    )
    s = run(cfg, make_source(), tmp_path, repo_root=ROOT)
    preds = pd.read_parquet(s.dir / "predictions.parquet", columns=["seed", "window_id"])
    per_seed = preds[preds["seed"] == 0]["window_id"].nunique()
    assert preds["window_id"].nunique() == 2 * per_seed  # ids differ by seed
    summary = mod.summary_table({"toy": s.dir})
    assert (summary["n_windows"] == per_seed).all()
    table = mod.per_slot_table({"toy": s.dir})
    assert (table["n_windows"] == per_seed).all()
