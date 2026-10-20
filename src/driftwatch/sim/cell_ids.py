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


def e3_cell_id(
    ds: str,
    selector: str,
    delay: int,
    budget: float,
    fraction: float,
    score: str,
    seeds: Sequence[int],
) -> str:
    return f"{ds}/e3-{selector}-d{delay}-b{budget:g}-r{fraction:g}-{score}-{seed_tag(seeds)}"


def e4_cell_id(ds: str, arm: str, delay: int | None, budget: float, seeds: Sequence[int]) -> str:
    """``arm`` is never, periodic, monitor-<name> or matched-<name>; never has no delay."""
    d = "" if delay is None else f"-d{delay}"
    return f"{ds}/e4-{arm}{d}-b{budget:g}-{seed_tag(seeds)}"


E4_MONITORS = ("ks", "mmd", "domain_clf", "p_uniformity")


def e4_arms(g: dict[str, Any]) -> list[tuple[str, int | None]]:
    """(arm, delay) of an E4 grid block, in expansion order: never, periodic, monitors, matched.

    Every monitor cell comes before every matched cell, so a matched cell's source exists
    when the grid reaches it.
    """
    p = g["policies"]
    delays = [int(d) for d in g["delay"]]
    arms: list[tuple[str, int | None]] = []
    if "never" in p:
        arms.append(("never", None))
    if "periodic" in p:
        arms += [("periodic", d) for d in delays]
    triggers = list((p.get("monitor") or {}).get("triggers") or [])
    arms += [(f"monitor-{t}", d) for t in triggers for d in delays]
    if p.get("matched"):
        arms += [(f"matched-{t}", d) for t in triggers for d in delays]
    return arms


def planned_ids_e4(spec: dict[str, Any]) -> list[str]:
    """Cell ids of an E4 spec, in the order ``E4Spec.cells`` expands them."""
    g = spec["grid"]
    ds, b = spec["dataset"], float(g["budget_pct"])
    ids = [e4_cell_id(ds, arm, d, b, g["seeds"]) for arm, d in e4_arms(g)]
    if g.get("extra_seeds"):
        ids += [e4_cell_id(ds, arm, d, b, g["extra_seeds"]) for arm, d in e4_arms(g)]
    return ids


def planned_ids_e3(spec: dict[str, Any]) -> list[str]:
    """Cell ids of an E3 spec, in the order ``E3Spec.cells`` expands them."""
    g = spec["grid"]
    ds = spec["dataset"]
    frac = float(g.get("calibration_fraction", 0.20))
    score = str(g.get("score", "probability"))
    ids = []
    for sel in g["selectors"]:
        for d in g["delay"]:
            for b in g["budget_pct"]:
                ids.append(e3_cell_id(ds, sel, int(d), float(b), frac, score, g["seeds"]))
    if g.get("extra_seeds"):
        for sel in g["selectors"]:
            for d in g["delay"]:
                for b in g["budget_pct"]:
                    ids.append(e3_cell_id(ds, sel, int(d), float(b), frac, score, g["extra_seeds"]))
    a = g.get("anchor") or {}
    if a:
        sel = a.get("selector", "credibility")
        d, b = int(a.get("delay", 0)), float(a.get("budget_pct", g["budget_pct"][0]))
        for r in a.get("reserved", []):
            ids.append(e3_cell_id(ds, sel, d, b, float(r), score, g["seeds"]))
        if a.get("score_comparison"):
            ids.append(e3_cell_id(ds, sel, d, b, frac, str(a["score_comparison"]), g["seeds"]))
    return ids


def planned_ids(spec: dict[str, Any]) -> list[str]:
    """Every cell id a grid spec (the parsed YAML mapping) plans, in expansion order."""
    g = spec["grid"]
    ds = spec["dataset"]
    if "policies" in g:
        return planned_ids_e4(spec)
    if "selectors" in g:
        return planned_ids_e3(spec)
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
