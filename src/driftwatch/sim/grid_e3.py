"""The E3 grid (selection under delay): spec and cells (docs/prereg/addendum-v2.md).

A spec is a run config plus a ``grid:`` block with ``selectors``. It has the same interface as
:class:`driftwatch.sim.grid.GridSpec` (``cells``, ``config``, ``dataset``, ``output``), so the
ledger, chunks, smoke mode and resume of ``driftwatch grid`` apply unchanged.

Cells per dataset (reduced grid):

- ``main``: every selector x delay x budget at the default reserved share and score, seeds A;
- ``extra_seeds``: the main cells again with seeds B (the headline contrasts use ten seeds);
- ``ablation``: the anchor cell for the reserved-slice shares other than the default (0 is the
  deliberate trap demonstration);
- ``score``: the anchor cell with the centroid score.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from driftwatch.sim.cell_ids import e3_cell_id
from driftwatch.sim.config import RunConfig
from driftwatch.sim.grid import Cell, GridError

E3_KEYS = {
    "policy", "delay", "budget_pct", "selectors", "calibration_fraction", "score", "seeds",
    "extra_seeds", "anchor",
}  # fmt: skip
ANCHOR_KEYS = {"delay", "budget_pct", "selector", "reserved", "score_comparison"}


@dataclass(frozen=True)
class E3Spec:
    base: dict[str, Any]
    dataset: str
    name: str
    output: str
    policy: Any
    delays: tuple[int, ...]
    budgets: tuple[float, ...]
    selectors: tuple[str, ...]
    fraction: float
    score: str
    seeds: tuple[int, ...]
    extra_seeds: tuple[int, ...]
    anchor: Mapping[str, Any]
    nonconf: Mapping[str, Any]

    @classmethod
    def from_file(cls, path: Path | str) -> E3Spec:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise GridError(f"{path}: a grid spec must be a mapping")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> E3Spec:
        d = dict(data)
        g = d.pop("grid", None)
        if not isinstance(g, dict) or "selectors" not in g:
            raise GridError("an E3 spec needs a grid: block with selectors")
        unknown = sorted(set(g) - E3_KEYS)
        if unknown:
            raise GridError(f"unknown E3 grid key(s) {unknown}; allowed {sorted(E3_KEYS)}")
        for key in ("seeds", "delay", "budget_pct", "policy", "selector"):
            if key in d:
                raise GridError(f"{key!r} belongs inside grid:, not at the top level")
        selectors = tuple(g["selectors"])
        if "random" not in selectors or len(set(selectors)) != len(selectors):
            raise GridError("selectors must be distinct and include random (the reference arm)")
        anchor = dict(g.get("anchor") or {})
        if set(anchor) - ANCHOR_KEYS:
            raise GridError(f"unknown anchor key(s) {sorted(set(anchor) - ANCHOR_KEYS)}")
        spec = cls(
            base=d,
            dataset=str(d.get("dataset")),
            name=str(d.get("name") or "e3"),
            output=str(d.get("output") or "results/e3"),
            policy=g.get("policy") or {"name": "periodic", "period": 3},
            delays=tuple(int(x) for x in g["delay"]),
            budgets=tuple(float(x) for x in g["budget_pct"]),
            selectors=selectors,
            fraction=float(g.get("calibration_fraction", 0.20)),
            score=str(g.get("score", "probability")),
            seeds=tuple(g["seeds"]),
            extra_seeds=tuple(g.get("extra_seeds") or ()),
            anchor=anchor,
            nonconf=dict(d.get("nonconf") or {}),
        )
        if set(spec.extra_seeds) & set(spec.seeds):
            raise GridError("extra_seeds must be seeds the main cells do not already run")
        for cell in spec.cells():
            spec.config(cell)  # fails here, not after hours of compute
        return spec

    def cells(self) -> list[Cell]:
        ds = self.dataset
        out: list[Cell] = []

        def add(role, selector, delay, budget, frac, score, seeds):
            out.append(
                Cell(
                    e3_cell_id(ds, selector, delay, budget, frac, score, seeds),
                    ds, role, "periodic", delay, budget, tuple(seeds), ("rolling",),
                    selector, frac, score,
                )
            )  # fmt: skip

        for sel in self.selectors:
            for d in self.delays:
                for b in self.budgets:
                    add("main", sel, d, b, self.fraction, self.score, self.seeds)
        for sel in self.selectors:
            for d in self.delays:
                for b in self.budgets:
                    if self.extra_seeds:
                        add("extra_seeds", sel, d, b, self.fraction, self.score, self.extra_seeds)
        a = self.anchor
        if a:
            sel = a.get("selector", "credibility")
            d, b = int(a.get("delay", 0)), float(a.get("budget_pct", self.budgets[0]))
            for frac in a.get("reserved", []):
                add("ablation", sel, d, b, float(frac), self.score, self.seeds)
            if a.get("score_comparison"):
                add("score", sel, d, b, self.fraction, str(a["score_comparison"]), self.seeds)
        ids = [c.cell_id for c in out]
        if len(set(ids)) != len(ids):
            raise GridError("two E3 cells have the same id")
        return out

    def config(self, cell: Cell, *, smoke: bool = False, output: str | None = None) -> RunConfig:
        d = json.loads(json.dumps(self.base))
        rel = cell.cell_id.split("/", 1)[1]
        d["name"] = f"{self.name}:{rel}"
        d["seeds"] = list(cell.seeds[:1] if smoke else cell.seeds)
        e0 = dict(d.get("e0") or {})
        e0["variants"] = list(cell.variants)
        e0.setdefault("random_split", False)
        d["e0"] = e0
        d["output"] = output or f"{self.output}{'-smoke' if smoke else ''}/{rel}"
        nonconf = {**self.nonconf, "score": cell.score}
        nonconf["trap_selected_calibration"] = cell.calibration_fraction == 0.0
        d.update(
            {
                "policy": self.policy,
                "selector": {
                    "name": cell.selector,
                    "calibration_fraction": cell.calibration_fraction,
                },
                "delay": cell.delay,
                "budget_pct": cell.budget_pct,
                "nonconf": nonconf,
            }
        )
        return RunConfig.from_dict(d)


def load_spec(path: Path | str):
    """The spec of a grid file: an E3 spec when its grid block has ``selectors``, else E2."""
    from driftwatch.sim.grid import GridSpec

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if (
        isinstance(data, dict)
        and isinstance(data.get("grid"), dict)
        and "selectors" in data["grid"]
    ):
        return E3Spec.from_dict(data)
    return GridSpec.from_dict(data)
