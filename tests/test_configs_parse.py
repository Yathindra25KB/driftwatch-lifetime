"""Every config in configs/ is runnable: it parses, and a grid file plans the cells it expands to.

A config that no longer parses is either fixed or deleted (Phase 10 rule); a registered config
is never edited after it produced stored results, so a failure here means the code changed
under a config and the code is wrong (or the config was copied to a new name).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from driftwatch.sim.cell_ids import planned_ids_from_file
from driftwatch.sim.config import RunConfig
from driftwatch.sim.grid_e3 import load_spec

CONFIGS = sorted((Path(__file__).resolve().parents[1] / "configs").glob("*.yaml"))


def is_grid(path: Path) -> bool:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return isinstance(data, dict) and isinstance(data.get("grid"), dict)


def test_there_are_configs_to_check() -> None:
    assert len(CONFIGS) >= 16


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_every_config_parses(path: Path) -> None:
    if is_grid(path):
        spec = load_spec(path)  # raises on a bad grid, parses every cell's run config
        assert spec.cells(), path.name
    else:
        cfg = RunConfig.from_file(path)
        assert cfg.dataset in ("lamda", "bodmas")


@pytest.mark.parametrize("path", [p for p in CONFIGS if is_grid(p)], ids=lambda p: p.name)
def test_a_grid_plans_exactly_the_cells_it_expands_to(path: Path) -> None:
    spec = load_spec(path)
    assert [c.cell_id for c in spec.cells()] == planned_ids_from_file(path)
    for cell in spec.cells():
        assert cell.cell_id.startswith(f"{spec.dataset}/")


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.name)
def test_a_config_names_its_dataset_in_its_file_name(path: Path) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["dataset"] in path.stem, path.name
