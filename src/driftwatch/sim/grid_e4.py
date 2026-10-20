"""The E4 grid (drift monitors and retraining policies): spec and cells (addendum v3).

A spec is a run config plus a ``grid:`` block with ``policies``. It has the interface of
:class:`driftwatch.sim.grid.GridSpec` (``cells``, ``config``, ``dataset``, ``output``,
``name``), so the ledger, smoke mode and resume of ``driftwatch grid`` apply unchanged.

Every arm runs on the conformal path of E3 with the random selector (reserved share and
hold-out as in E3), so all arms query the same rows: labels spent are matched by
construction. Cells per dataset, for each seed set:

- ``never``: never retrains; every monitor in ``policies.never.observe`` runs passively with
  the initial reference (the primary monitor-quality cells);
- ``periodic`` at each delay: periodic(3), no monitors (the E3 random arm's configuration);
- ``monitor-<m>`` at each delay: retrain on monitor ``m``'s alarm, minimum gap ``min_gap``;
- ``matched-<m>`` at each delay: the same number of refits as ``monitor-<m>`` in each window,
  spread evenly (the matched-retrains control). Its source is the sibling monitor cell, which
  the expansion order puts first. Run the grid without chunks (``--workers 1``) so that a
  matched cell and its source share an output root.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from driftwatch.sim.cell_ids import E4_MONITORS, e4_arms, e4_cell_id
from driftwatch.sim.config import RunConfig
from driftwatch.sim.grid import Cell, GridError

E4_KEYS = {
    "policies", "delay", "budget_pct", "calibration_fraction", "seeds", "extra_seeds",
    "monitor_cache",
}  # fmt: skip
POLICY_KEYS = {"never", "periodic", "monitor", "matched"}


@dataclass(frozen=True)
class E4Spec:
    base: dict[str, Any]
    grid: Mapping[str, Any]
    dataset: str
    name: str
    output: str
    delays: tuple[int, ...]
    budget: float
    fraction: float
    seeds: tuple[int, ...]
    extra_seeds: tuple[int, ...]
    observe: tuple[str, ...]
    triggers: tuple[str, ...]
    period: int
    min_gap: int
    monitor_cache: str | None

    @classmethod
    def from_file(cls, path: Path | str) -> E4Spec:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise GridError(f"{path}: a grid spec must be a mapping")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> E4Spec:
        d = dict(data)
        g = d.pop("grid", None)
        if not isinstance(g, dict) or "policies" not in g:
            raise GridError("an E4 spec needs a grid: block with policies")
        unknown = sorted(set(g) - E4_KEYS)
        if unknown:
            raise GridError(f"unknown E4 grid key(s) {unknown}; allowed {sorted(E4_KEYS)}")
        for key in ("seeds", "delay", "budget_pct", "policy", "selector", "monitors"):
            if key in d:
                raise GridError(f"{key!r} belongs inside grid:, not at the top level")
        p = g["policies"]
        if not isinstance(p, dict) or set(p) - POLICY_KEYS:
            raise GridError(f"grid.policies takes only {sorted(POLICY_KEYS)}")
        observe = tuple((p.get("never") or {}).get("observe") or ())
        mon = p.get("monitor") or {}
        triggers = tuple(mon.get("triggers") or ())
        for name in (*observe, *triggers):
            if name not in E4_MONITORS:
                raise GridError(f"unknown monitor {name!r}; choose from {E4_MONITORS}")
        if p.get("matched") and not triggers:
            raise GridError("matched cells need monitor triggers to be matched to")
        spec = cls(
            base=d,
            grid=g,
            dataset=str(d.get("dataset")),
            name=str(d.get("name") or "e4"),
            output=str(d.get("output") or "results/e4"),
            delays=tuple(int(x) for x in g["delay"]),
            budget=float(g["budget_pct"]),
            fraction=float(g.get("calibration_fraction", 0.20)),
            seeds=tuple(g["seeds"]),
            extra_seeds=tuple(g.get("extra_seeds") or ()),
            observe=observe,
            triggers=triggers,
            period=int((p.get("periodic") or {}).get("period", 3)),
            min_gap=int(mon.get("min_gap", 2)),
            monitor_cache=g.get("monitor_cache"),
        )
        if set(spec.extra_seeds) & set(spec.seeds):
            raise GridError("extra_seeds must be seeds the main cells do not already run")
        for cell in spec.cells():
            spec.config(cell)  # fails here, not after hours of compute
        return spec

    def _arms(self) -> list[tuple[str, int | None]]:
        return e4_arms(dict(self.grid))

    def cells(self) -> list[Cell]:
        out: list[Cell] = []
        for role, seeds in (("main", self.seeds), ("extra_seeds", self.extra_seeds)):
            if not seeds:
                continue
            for arm, d in self._arms():
                out.append(
                    Cell(
                        e4_cell_id(self.dataset, arm, d, self.budget, seeds),
                        self.dataset, role, arm, 0 if d is None else d, self.budget,
                        tuple(seeds), ("rolling",), "random", self.fraction, "probability",
                    )
                )  # fmt: skip
        ids = [c.cell_id for c in out]
        if len(set(ids)) != len(ids):
            raise GridError("two E4 cells have the same id")
        return out

    def _policy(self, cell: Cell) -> tuple[dict[str, Any] | str, list[str] | None]:
        arm = cell.arm
        if arm == "never":
            return "never", list(self.observe) or None
        if arm == "periodic":
            return {"name": "periodic", "period": self.period}, None
        kind, trigger = arm.split("-", 1)
        if kind == "monitor":
            return {"name": "monitor", "trigger": trigger, "min_gap": self.min_gap}, [trigger]
        source = e4_cell_id(self.dataset, f"monitor-{trigger}", cell.delay, cell.budget_pct
                            or self.budget, cell.seeds)  # fmt: skip
        return {"name": "matched", "trigger": trigger,
                "source": "sibling:" + source.split("/", 1)[1]}, None  # fmt: skip

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
        policy, names = self._policy(cell)
        d.update(
            {
                "policy": policy,
                "selector": {"name": "random", "calibration_fraction": cell.calibration_fraction},
                "delay": cell.delay,
                "budget_pct": cell.budget_pct,
                "nonconf": {**dict(d.get("nonconf") or {}), "score": "probability"},
            }
        )
        if names:
            d["monitors"] = {"names": names, "cache": self.monitor_cache}
        return RunConfig.from_dict(d)


__all__ = ["E4Spec"]
