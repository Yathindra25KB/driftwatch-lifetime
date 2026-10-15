"""Cell ids of the E2 grid, without importing the simulator or any model code.

The driver (``sim/grid.py``) and the table code (``metrics/grid_tables.py``) must agree on
what a cell is called, and the table code must be able to list the planned cells without
loading the runner. ``tests/test_grid.py`` pins that :func:`planned_ids` and
``GridSpec.cells`` give the same ids.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml


def variant_tag(variants: Sequence[str]) -> str:
    return "+".join({"rolling": "roll", "rolling_chow": "chow"}.get(v, v) for v in variants)


def seed_tag(seeds: Sequence[int]) -> str:
    s = sorted(seeds)
    if s == list(range(s[0], s[-1] + 1)):
        return f"s{s[0]}-{s[-1]}"
    return "s" + "_".join(str(x) for x in s)


def periodic_id(
    dataset: str, delay: int, budget: float, seeds: Sequence[int], variants: Sequence[str]
) -> str:
    return f"{dataset}/periodic-d{delay}-b{budget:g}-{seed_tag(seeds)}-{variant_tag(variants)}"


def planned_ids(spec: dict[str, Any]) -> list[str]:
    """Every cell id a grid spec (the parsed YAML mapping) plans, in expansion order."""
    g = spec["grid"]
    ds = spec["dataset"]
    variants = tuple(spec.get("e0", {}).get("variants") or ("rolling",))
    never = g["never"]
    never_variants = never.get("variants") or ("rolling",)
    ids = [f"{ds}/never-{seed_tag(never['seeds'])}-{variant_tag(never_variants)}"]
    for d in g["delay"]:
        for b in g["budget_pct"]:
            ids.append(periodic_id(ds, int(d), float(b), g["seeds"], variants))
    head = g.get("headline") or {}
    for d, b in head.get("cells", []):
        ids.append(periodic_id(ds, int(d), float(b), head["seeds"], variants))
    chow = g.get("chow") or {}
    for d, b in chow.get("cells", []):
        ids.append(periodic_id(ds, int(d), float(b), chow["seeds"], ("rolling_chow",)))
    return ids


def planned_ids_from_file(path: Path | str) -> list[str]:
    return planned_ids(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
