"""The E0 table builder: aggregation over windows and seeds, bootstrap gap, canary table."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "make_e0_table", ROOT / "scripts" / "make_e0_table.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_e0_table"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return _load_script()


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from test_runner_e0 import ROOT as REPO
    from test_runner_e0 import make_config, make_source

    from driftwatch.sim.runner import run

    source, _ = make_source()
    out = tmp_path_factory.mktemp("e0")
    return run(make_config(), source, out, repo_root=REPO).dir


def test_baseline_table_has_one_row_per_model_variant_and_ratio(tool, run_dir: Path) -> None:
    base, per_slot = tool.build_tables({"bodmas": run_dir})
    assert set(base["variant"]) == {"rolling", "rolling_chow", "sensitivity", "single_run"}
    assert set(base["model"]) == {"lr", "lgbm"}
    assert len(base) == 4 * 2
    assert not base.duplicated(["dataset", "model", "variant", "ratio"]).any()
    row = base[(base["variant"] == "rolling") & (base["model"] == "lr")].iloc[0]
    assert row["n_seeds"] == 2 and row["n_windows"] == 4 and row["n_eval_slots"] == 6
    assert row["gap"] == pytest.approx(row["f1_random_split"] - row["a_aut_mean"])
    assert row["gap_ci_low"] <= row["gap"] <= row["gap_ci_high"] or np.isnan(row["gap_ci_low"])
    assert 0.0 <= row["share_below_target"] <= 1.0
    assert row["sanity_band"] == "[verify]"
    single = base[base["variant"] == "single_run"]
    assert single["f1_random_split"].isna().all()  # no random split for the single run


def test_a_aut_is_the_mean_of_per_seed_means_and_std_is_over_windows(tool, run_dir: Path) -> None:
    base, _ = tool.build_tables({"bodmas": run_dir})
    windows = pd.read_parquet(run_dir / "windows.parquet")
    sel = windows[(windows["variant"] == "rolling") & (windows["model"] == "lgbm")]
    per_seed_mean = sel.groupby("seed")["aut"].mean()
    per_seed_std = sel.groupby("seed")["aut"].std(ddof=1)
    row = base[(base["variant"] == "rolling") & (base["model"] == "lgbm")].iloc[0]
    assert row["a_aut_mean"] == pytest.approx(per_seed_mean.mean())
    assert row["a_aut_std"] == pytest.approx(per_seed_std.mean())
    assert row["a_aut_seed_sd"] == pytest.approx(per_seed_mean.std(ddof=1))


def test_pooled_comparator_is_reported_beside_the_headline(tool, run_dir: Path) -> None:
    base, _ = tool.build_tables({"bodmas": run_dir})
    row = base[(base["variant"] == "rolling") & (base["model"] == "lr")].iloc[0]
    assert row["gap_pooled"] == pytest.approx(row["f1_random_pooled"] - row["a_aut_mean"])


def test_check_run_rejects_partial_dirty_and_foreign_config_runs(
    tool, run_dir: Path, tmp_path: Path
) -> None:
    import shutil

    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

    def variant(name: str, **changes) -> Path:
        d = tmp_path / name
        shutil.copytree(run_dir, d)
        (d / "run.json").write_text(json.dumps({**record, **changes}), encoding="utf-8")
        return d

    # the development tree is usually dirty, so pin a clean version for the positive case
    clean = variant("clean", code_version="abc1234")
    assert tool.check_run(clean)["status"] == "complete"

    with pytest.raises(tool.RunRejected, match="status"):
        tool.check_run(variant("partial", status="failed"))
    with pytest.raises(tool.RunRejected, match="dirty"):
        tool.check_run(variant("dirty", code_version="abc1234-dirty"))
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "e0_bodmas.yaml").write_text(
        (ROOT / "configs" / "e0_bodmas.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(tool.RunRejected, match="differs"):  # the toy run is not the E0 config
        tool.check_run(clean, configs)


def test_per_slot_table_covers_every_evaluated_slot(tool, run_dir: Path) -> None:
    _, per_slot = tool.build_tables({"bodmas": run_dir})
    slots = pd.read_parquet(run_dir / "slots.parquet")
    keys = ["variant", "model", "ratio", "slot_id"]
    assert len(per_slot) == len(slots.drop_duplicates(keys))
    assert per_slot["f1"].between(0, 1).all()


def test_canary_table_reads_verdicts_and_exit_codes(tool, tmp_path: Path) -> None:
    base = {
        "dataset": "bodmas", "aut_true": 0.5, "aut_shuffled": 0.8, "f1_random": 0.9, "gap": 0.4,
        "closure": 0.75, "leakage_warning": False, "n_windows": 3, "spec_digest": "abc",
    }  # fmt: skip
    for name, verdict, extra in (
        ("a.json", "PASS", {}),
        ("b.json", "FAIL", {"dataset": "lamda"}),
        ("c.json", "NO_GAP", {"dataset": "lamda", "closure": None}),
        ("d.json", "PASS", {"dataset": "x", "leakage_warning": True}),
    ):
        (tmp_path / name).write_text(
            json.dumps({**base, **extra, "verdict": verdict}), encoding="utf-8"
        )
    table = tool.canary_table(sorted(tmp_path.glob("*.json")))
    assert list(table["verdict"]) == ["PASS", "FAIL", "NO_GAP", "PASS"]
    assert list(table["exit_code"]) == [0, 1, 3, 3]  # PASS with a leakage warning is not a pass
