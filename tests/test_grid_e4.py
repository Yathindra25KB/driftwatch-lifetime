"""The E4 grid spec: expansion, cell configs, matched sources, and a synthetic end-to-end run."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from test_grid import ROOT, plain_runner, source

from driftwatch.sim import grid
from driftwatch.sim.cell_ids import planned_ids, planned_ids_from_file
from driftwatch.sim.grid import GridError
from driftwatch.sim.grid_e3 import load_spec
from driftwatch.sim.grid_e4 import E4Spec

CONFIGS = ROOT / "configs"


def spec_dict(**grid_over) -> dict:
    g = {
        "policies": {
            "never": {"observe": ["ks", "p_uniformity"]},
            "periodic": {"period": 3},
            "monitor": {"triggers": ["ks", "p_uniformity"], "min_gap": 2},
            "matched": True,
        },
        "delay": [0, 3],
        "budget_pct": 10.0,
        "calibration_fraction": 0.2,
        "seeds": [0],
    }
    g.update(grid_over)
    return {
        "name": "e4_test",
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
        },  # fmt: skip
        "grid": g,
    }


def test_expansion_order_puts_every_monitor_cell_before_its_matched_cell() -> None:
    spec = E4Spec.from_dict(spec_dict())
    ids = [c.cell_id for c in spec.cells()]
    assert ids == planned_ids(spec_dict())
    assert len(ids) == 1 + 2 + 4 + 4
    for c in spec.cells():
        if c.arm.startswith("matched-"):
            src = spec.config(c).policy_source
            assert src is not None and src.startswith("sibling:e4-monitor-")
            assert f"bodmas/{src[8:]}" in ids[: ids.index(c.cell_id)]


def test_cell_configs_share_the_e3_random_arm_settings() -> None:
    spec = E4Spec.from_dict(spec_dict())
    for c in spec.cells():
        cfg = spec.config(c)
        assert cfg.selector == "random" and cfg.calibration_fraction == 0.2
        assert cfg.nonconf is not None and cfg.nonconf["score"] == "probability"
        assert cfg.budget_pct == 10.0
    by_arm = {c.arm: spec.config(c) for c in spec.cells() if c.delay in (0,)}
    assert by_arm["never"].monitors == ("ks", "p_uniformity")
    assert by_arm["periodic"].monitors is None  # the plain E3 random arm
    assert by_arm["monitor-ks"].monitors == ("ks",) and by_arm["monitor-ks"].policy_min_gap == 2
    assert by_arm["matched-ks"].monitors is None


@pytest.mark.parametrize(
    ("over", "message"),
    [
        ({"policies": {"monitor": {"triggers": ["adwin"]}}}, "unknown monitor"),
        ({"policies": {"matched": True}}, "matched cells need"),
        ({"policies": {"sometimes": {}}}, "policies takes only"),
        ({"chunks": 2}, "unknown E4 grid key"),
        ({"extra_seeds": [0]}, "extra_seeds"),
    ],
)
def test_bad_e4_specs_fail_at_parse_time(over: dict, message: str) -> None:
    with pytest.raises(GridError, match=message):
        E4Spec.from_dict(spec_dict(**over))


@pytest.mark.parametrize("ds", ["bodmas", "lamda"])
def test_the_committed_e4_configs_parse_and_plan_19_cells(ds: str) -> None:
    path = CONFIGS / f"e4_{ds}.yaml"
    spec = load_spec(path)
    assert isinstance(spec, E4Spec)
    assert [c.cell_id for c in spec.cells()] == planned_ids_from_file(path)
    assert len(spec.cells()) == 19


@pytest.mark.slow
def test_the_e4_grid_runs_end_to_end_with_matched_cells_reading_their_siblings(
    tmp_path: Path,
) -> None:
    spec = E4Spec.from_dict(spec_dict())
    results = grid.run_grid(
        spec, source(), tmp_path, repo_root=ROOT, require_clean=False, runner=plain_runner
    )
    assert [r.status for r in results] == ["complete"] * len(spec.cells()), [
        (r.cell_id, r.reason) for r in results if r.status != "complete"
    ]
    by_id = {r.cell_id: r for r in results}
    keys = ["window_id", "seed", "model"]
    for c in spec.cells():
        if not c.arm.startswith("matched-"):
            continue
        trig = c.arm.split("-", 1)[1]
        src = by_id[c.cell_id.replace(f"matched-{trig}", f"monitor-{trig}")]
        a = pd.read_parquet(src.dir / "slots.parquet")
        b = pd.read_parquet(by_id[c.cell_id].dir / "slots.parquet")
        pd.testing.assert_series_equal(a.groupby(keys)["n_queried"].sum(),
                                       b.groupby(keys)["n_queried"].sum())  # fmt: skip
