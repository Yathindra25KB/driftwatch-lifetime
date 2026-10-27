"""scripts/compare_runs.py: a rerun with fewer seeds matches, and a perturbed one does not."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(
        "compare_runs", ROOT / "scripts" / "compare_runs.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["compare_runs"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runs(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    from test_runner_e0 import make_config, make_source

    from driftwatch.sim.runner import run

    e0 = {"variants": ["rolling"], "random_split": True}
    full = run(
        make_config(seeds=[0, 1], e0=e0),
        make_source()[0],
        tmp_path_factory.mktemp("full"),
        repo_root=ROOT,
    )
    again = run(
        make_config(seeds=[0], e0=e0),
        make_source()[0],
        tmp_path_factory.mktemp("again"),
        repo_root=ROOT,
    )
    return full.dir, again.dir


def test_a_subset_rerun_is_identical(tool, runs) -> None:
    result = tool.compare(*runs)
    assert result["identical"], result
    assert result["cells_compared"] > 0 and result["window_rows_compared"] > 0


def test_a_changed_comparator_or_prediction_is_caught(tool, runs, tmp_path: Path) -> None:
    original, rerun = runs
    broken = tmp_path / "broken"
    shutil.copytree(rerun, broken)
    w = pd.read_parquet(broken / "windows.parquet")
    w.loc[0, "f1_random_split"] += 0.01
    w.to_parquet(broken / "windows.parquet", index=False)
    result = tool.compare(original, broken)
    assert not result["identical"] and "f1_random_split" in result["columns_that_differ"]

    other = tmp_path / "other"
    shutil.copytree(rerun, other)
    record = json.loads((other / "run.json").read_text(encoding="utf-8"))
    first = sorted(record["cell_predictions_sha256"])[0]
    record["cell_predictions_sha256"][first] = "0" * 64
    (other / "run.json").write_text(json.dumps(record), encoding="utf-8")
    assert first in tool.compare(original, other)["cells_with_different_hash"]
