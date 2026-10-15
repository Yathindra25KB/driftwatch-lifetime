"""The delay x budget grid (E2): spec, cells, ledger, chunks, and a resumable driver.

A grid file is a normal run config plus a ``grid:`` block. :class:`RunConfig` rejects that
block on purpose, so ``driftwatch run configs/e2_*.yaml`` fails instead of running one cell.
Every cell expands into an ordinary :class:`RunConfig` with scalar delay and budget (hard
rule 6: one config per run, hashed with the code version and the lock file).

Cells (per dataset):

- ``grid``: periodic retraining at every (delay, budget), the grid seeds;
- ``headline``: the pre-registered headline cells again with further seeds;
- ``chow``: the Chow-stride secondary check on the delay-contrast cells;
- ``never``: one run for every (dataset, model, window, seed). It does not depend on delay or
  budget (it never refits), so it is not repeated per cell (``tests/test_grid.py`` pins that).

The driver runs one cell at a time (the memory cap forbids parallel BODMAS runs), writes an
append-only JSONL ledger, and never reruns a cell because of what its result looks like. A
failure is logged with its reason and the next cell runs. Nothing here reads a label or a
score: it decides what is run, and how long it took.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from driftwatch.data.cache import code_version
from driftwatch.data.slicer import SlotSource, count_windows
from driftwatch.sim.config import RunConfig, config_hash, lock_sha256
from driftwatch.sim.runner import DEFAULT_MEMORY_CAP, InitialModelCache, _spec_for, run

log = logging.getLogger(__name__)

FIT_LIMIT_S = 60.0  # PROTOCOL: a fit over 60 s means shrink the grid, not the claim
ROLES = ("grid", "headline", "chow", "never")
GRID_KEYS = {"delay", "budget_pct", "policy", "selector", "seeds", "headline", "chow", "never"}
LEDGER_NAME = "ledger.jsonl"
# relative cost of a unit (window x seed x model): a never run only fits the initial model
NEVER_WEIGHT = 0.26  # measured: about 320 s against about 1,250 s per LAMDA cell (Phase 5)


class GridError(ValueError):
    """The grid spec is not valid."""


# --- spec and cells ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cell:
    cell_id: str
    dataset: str
    role: str
    arm: str  # "periodic" | "never"
    delay: int | None
    budget_pct: float | None
    seeds: tuple[int, ...]
    variants: tuple[str, ...]

    @property
    def shape(self) -> tuple[str, int | None, float | None, tuple[str, ...]]:
        """What costs the same per unit: arm, delay, budget, variants (seeds excluded)."""
        return (self.arm, self.delay, self.budget_pct, self.variants)


def _seed_list(value: Any, what: str) -> tuple[int, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(isinstance(s, bool) or not isinstance(s, int) or s < 0 for s in value)
        or len(set(value)) != len(value)
    ):
        raise GridError(f"{what} must be an explicit non-empty list of distinct integers")
    return tuple(value)


def _pairs(value: Any, what: str, delays: Sequence[int], budgets: Sequence[float]):
    if not isinstance(value, list) or not value:
        raise GridError(f"{what}.cells must be a non-empty list of [delay, budget_pct]")
    out = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise GridError(f"{what}.cells entry {item!r} is not [delay, budget_pct]")
        d, b = int(item[0]), float(item[1])
        if d not in delays or b not in budgets:
            raise GridError(f"{what}.cells entry {item!r} is outside the grid")
        out.append((d, b))
    if len(set(out)) != len(out):
        raise GridError(f"{what}.cells has duplicates")
    return out


def _tag(variants: Sequence[str]) -> str:
    return "+".join({"rolling": "roll", "rolling_chow": "chow"}.get(v, v) for v in variants)


def _seed_tag(seeds: Sequence[int]) -> str:
    s = sorted(seeds)
    if s == list(range(s[0], s[-1] + 1)):
        return f"s{s[0]}-{s[-1]}"
    return "s" + "_".join(str(x) for x in s)


def _periodic_id(dataset: str, d: int, b: float, seeds: Sequence[int], variants: Sequence[str]):
    return f"{dataset}/periodic-d{d}-b{b:g}-{_seed_tag(seeds)}-{_tag(variants)}"


@dataclass(frozen=True)
class GridSpec:
    base: dict[str, Any]  # a RunConfig dict without seeds, delay, budget or policy
    dataset: str
    name: str
    delays: tuple[int, ...]
    budgets: tuple[float, ...]
    policy: Any
    selector: Any
    seeds: tuple[int, ...]
    headline_cells: tuple[tuple[int, float], ...]
    headline_seeds: tuple[int, ...]
    chow_cells: tuple[tuple[int, float], ...]
    chow_seeds: tuple[int, ...]
    never_seeds: tuple[int, ...]
    never_variants: tuple[str, ...]
    output: str

    @classmethod
    def from_file(cls, path: Path | str) -> GridSpec:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise GridError(f"{path}: a grid spec must be a mapping")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> GridSpec:
        d = dict(data)
        g = d.pop("grid", None)
        if not isinstance(g, dict):
            raise GridError("a grid spec needs a grid: block")
        unknown = sorted(set(g) - GRID_KEYS)
        if unknown:
            raise GridError(f"unknown grid key(s) {unknown}; allowed {sorted(GRID_KEYS)}")
        for key in ("seeds", "delay", "budget_pct", "policy", "selector"):
            if key in d:
                raise GridError(f"{key!r} belongs inside grid:, not at the top level")
        delays = tuple(int(x) for x in g.get("delay") or ())
        budgets = tuple(float(x) for x in g.get("budget_pct") or ())
        if not delays or not budgets:
            raise GridError("grid.delay and grid.budget_pct must be non-empty lists")
        if len(set(delays)) != len(delays) or len(set(budgets)) != len(budgets):
            raise GridError("grid.delay and grid.budget_pct must not repeat values")
        seeds = _seed_list(g.get("seeds"), "grid.seeds")
        head = g.get("headline") or {}
        chow = g.get("chow") or {}
        never = g.get("never") or {}
        h_seeds = _seed_list(head["seeds"], "grid.headline.seeds") if head else ()
        if set(h_seeds) & set(seeds):
            raise GridError("grid.headline.seeds must be seeds the grid does not already run")
        if g.get("policy") is None or g.get("selector") is None:
            raise GridError("grid.policy and grid.selector are required")
        spec = cls(
            base=d,
            dataset=str(d.get("dataset")),
            name=str(d.get("name") or "grid"),
            delays=delays,
            budgets=budgets,
            policy=g["policy"],
            selector=g["selector"],
            seeds=seeds,
            headline_cells=tuple(_pairs(head.get("cells"), "grid.headline", delays, budgets))
            if head
            else (),
            headline_seeds=h_seeds,
            chow_cells=tuple(_pairs(chow.get("cells"), "grid.chow", delays, budgets))
            if chow
            else (),
            chow_seeds=_seed_list(chow["seeds"], "grid.chow.seeds") if chow else (),
            never_seeds=_seed_list(never.get("seeds"), "grid.never.seeds"),
            never_variants=tuple(never.get("variants") or ("rolling",)),
            output=str(d.get("output") or "results/e2"),
        )
        need_seeds = set(seeds) | set(h_seeds) | set(spec.chow_seeds)
        if not need_seeds <= set(spec.never_seeds):
            raise GridError(
                "grid.never.seeds must cover every seed of the periodic cells, so every "
                "contrast has a never arm to pair with; missing "
                f"{sorted(need_seeds - set(spec.never_seeds))}"
            )
        need_variants = set(spec.base.get("e0", {}).get("variants") or ("rolling",))
        if spec.chow_cells:
            need_variants.add("rolling_chow")
        if not need_variants <= set(spec.never_variants):
            raise GridError(
                "grid.never.variants must include "
                f"{sorted(need_variants - set(spec.never_variants))}"
            )
        # validate by expanding every cell once (fails here, not after hours of compute)
        for cell in spec.cells():
            spec.config(cell)
        return spec

    # -- expansion ---------------------------------------------------------------------------

    def cells(self) -> list[Cell]:
        ds = self.dataset
        variants = tuple(self.base.get("e0", {}).get("variants") or ("rolling",))
        out: list[Cell] = []
        out.append(
            Cell(
                f"{ds}/never-{_seed_tag(self.never_seeds)}-{_tag(self.never_variants)}",
                ds, "never", "never", None, None, self.never_seeds, self.never_variants,
            )
        )  # fmt: skip
        for delay in self.delays:
            for budget in self.budgets:
                out.append(
                    Cell(
                        _periodic_id(ds, delay, budget, self.seeds, variants),
                        ds, "grid", "periodic", delay, budget, self.seeds, variants,
                    )
                )  # fmt: skip
        for delay, budget in self.headline_cells:
            out.append(
                Cell(
                    _periodic_id(ds, delay, budget, self.headline_seeds, variants),
                    ds, "headline", "periodic", delay, budget, self.headline_seeds, variants,
                )
            )  # fmt: skip
        for delay, budget in self.chow_cells:
            out.append(
                Cell(
                    _periodic_id(ds, delay, budget, self.chow_seeds, ("rolling_chow",)),
                    ds, "chow", "periodic", delay, budget, self.chow_seeds, ("rolling_chow",),
                )
            )  # fmt: skip
        ids = [c.cell_id for c in out]
        if len(set(ids)) != len(ids):
            raise GridError("two cells have the same id")
        return out

    def config(self, cell: Cell, *, smoke: bool = False, output: str | None = None) -> RunConfig:
        """The ordinary run config of one cell (seed list cut to the first seed in smoke mode)."""
        d = json.loads(json.dumps(self.base))  # deep copy, JSON-safe
        d["name"] = f"{self.name}:{cell.cell_id.split('/', 1)[1]}"
        d["seeds"] = list(cell.seeds[:1] if smoke else cell.seeds)
        e0 = dict(d.get("e0") or {})
        e0["variants"] = list(cell.variants)
        e0.setdefault("random_split", False)
        d["e0"] = e0
        rel = cell.cell_id.split("/", 1)[1]
        # relative and machine independent, so the hash does not depend on --out or the host
        d["output"] = output or f"{self.output}{'-smoke' if smoke else ''}/{rel}"
        if cell.arm == "never":
            d.update({"policy": "never", "selector": None, "delay": None, "budget_pct": None})
        else:
            d.update(
                {
                    "policy": self.policy,
                    "selector": self.selector,
                    "delay": cell.delay,
                    "budget_pct": cell.budget_pct,
                }
            )
        return RunConfig.from_dict(d)


# --- cost model and chunks --------------------------------------------------------------------


def window_counts(source: SlotSource, cfg: RunConfig, seed: int | None = None) -> dict[str, int]:
    """Planned windows per variant (the slicer's plan, no features loaded)."""
    s = cfg.seeds[0] if seed is None else seed
    return {v: count_windows(source, _spec_for(cfg, v, s)) for v in cfg.variants}


def cell_units(cell: Cell, n_models: int, windows: Mapping[str, int]) -> int:
    """Window x seed x model units of a cell."""
    return sum(windows.get(v, 1) for v in cell.variants) * len(cell.seeds) * n_models


def cell_cost(cell: Cell, units: int) -> float:
    return units * (NEVER_WEIGHT if cell.arm == "never" else 1.0)


def assign_chunks(costs: Mapping[str, float], n: int) -> list[list[str]]:
    """Greedy balanced partition: deterministic, every cell in exactly one chunk."""
    if n < 1:
        raise ValueError("the number of chunks must be at least 1")
    loads = [0.0] * n
    chunks: list[list[str]] = [[] for _ in range(n)]
    for cid in sorted(costs, key=lambda c: (-costs[c], c)):
        k = min(range(n), key=lambda i: (loads[i], i))
        chunks[k].append(cid)
        loads[k] += costs[cid]
    return [sorted(c) for c in chunks]


def parse_chunk(text: str) -> tuple[int, int]:
    """``"i/n"`` with 1 <= i <= n."""
    try:
        i, n = (int(x) for x in text.split("/"))
    except ValueError as exc:
        raise ValueError(f"--chunk must look like 2/11, got {text!r}") from exc
    if not 1 <= i <= n:
        raise ValueError(f"--chunk i/n needs 1 <= i <= n, got {text!r}")
    return i, n


# --- ledger -----------------------------------------------------------------------------------

EVENTS = ("started", "complete", "failed", "invalidated", "retry", "flag")


@dataclass
class CellState:
    cell_id: str
    status: str = "planned"  # planned | running | complete | failed | invalidated
    code_version: str | None = None
    config_hash: str | None = None
    dir: str | None = None
    wall_s: float | None = None
    max_fit_s: float | None = None
    peak_gb: float | None = None
    reason: str | None = None
    flags: list[str] = field(default_factory=list)
    attempts: int = 0


class Ledger:
    """Append-only JSONL: one line per event, the last event of a cell is its state."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, event: str, cell_id: str, **fields: Any) -> dict[str, Any]:
        if event not in EVENTS:
            raise ValueError(f"unknown ledger event {event!r}")
        row = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "event": event,
            "cell_id": cell_id,
            **fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        return row

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def state(self, cell_ids: Iterable[str] = (), *, smoke: bool = False) -> dict[str, CellState]:
        return fold_events(self.events(), cell_ids, smoke=smoke)


def fold_events(
    rows: Iterable[dict[str, Any]], cell_ids: Iterable[str] = (), *, smoke: bool = False
) -> dict[str, CellState]:
    """The state of every cell from its events, in the order given.

    Smoke events and real events never mix: a smoke run (one seed, one window) is not a
    finished cell, and the real driver must not see it as one.
    """
    out = {c: CellState(c) for c in cell_ids}
    for row in rows:
        if bool(row.get("smoke")) != smoke:
            continue
        st = out.setdefault(row["cell_id"], CellState(row["cell_id"]))
        ev = row["event"]
        if ev == "started":
            st.status, st.attempts = "running", st.attempts + 1
            st.code_version = row.get("code_version")
            st.config_hash = row.get("config_hash")
        elif ev == "complete":
            st.status = "complete"
            for k in ("code_version", "config_hash", "dir", "wall_s", "max_fit_s", "peak_gb"):
                setattr(st, k, row.get(k, getattr(st, k)))
            st.reason = None
        elif ev == "failed":
            st.status, st.reason = "failed", row.get("reason")
        elif ev == "invalidated":
            st.status, st.reason = "invalidated", row.get("reason")
        elif ev == "flag":
            st.flags.append(str(row.get("flag")))
        # "retry" only documents why a failed cell was run again; "started" follows it
    return out


def merged_ledger_events(root: Path | str) -> list[dict[str, Any]]:
    """Events of every ``ledger*.jsonl`` under ``root`` (chunks may have run on other machines)."""
    rows: list[dict[str, Any]] = []
    for p in sorted(Path(root).glob("ledger*.jsonl")):
        rows += Ledger(p).events()
    return sorted(rows, key=lambda r: r["ts"])  # stable: file order breaks ties


# --- driver -----------------------------------------------------------------------------------


class CodeVersionMismatch(RuntimeError):
    """A ledger holds cells run on another code version."""


def tree_is_clean(repo: Path | str) -> bool:
    """Tracked files unchanged and no untracked file under src/, configs/, scripts/ or tests/.

    ``code_version`` ignores untracked files (carried review item), so an untracked module
    could change results without changing the hash; the grid refuses that.
    """
    repo = Path(repo)
    if code_version(repo).endswith("-dirty"):
        return False
    out = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "src", "configs", "scripts",
         "tests"],  # fmt: skip
        cwd=repo, capture_output=True, text=True, check=False,
    ).stdout  # fmt: skip
    return not out.strip()


def _max_fit_seconds(run_dir: Path) -> float | None:
    import pandas as pd

    w = pd.read_parquet(run_dir / "windows.parquet", columns=["fit_seconds"])
    return float(w["fit_seconds"].max()) if len(w) else None


def _slot_fit_max(run_dir: Path) -> float | None:
    """Longest refit in a simulation run (baseline slot tables carry no fit_seconds)."""
    import pandas as pd

    s = pd.read_parquet(run_dir / "slots.parquet")
    if "fit_seconds" not in s.columns or s.empty:
        return None
    return float(s["fit_seconds"].max())


@dataclass(frozen=True)
class CellResult:
    cell_id: str
    status: str
    wall_s: float | None
    units: int
    dir: Path | None
    reason: str | None = None
    stop: bool = False


def run_cell(
    spec: GridSpec,
    cell: Cell,
    source: SlotSource,
    out_root: Path,
    ledger: Ledger,
    *,
    repo_root: Path,
    cache: InitialModelCache,
    memory_cap_bytes: int = DEFAULT_MEMORY_CAP,
    smoke: bool = False,
    max_windows: int | None = None,
    require_clean: bool = True,
    allow_code_change: str | None = None,
    retry_reason: str | None = None,
    state: CellState | None = None,
    runner: Callable[..., Any] = run,
    pinned_version: str | None = None,
) -> CellResult:
    """Run one cell (or skip it when the ledger says it is complete).

    ``pinned_version`` is the code version read once when the grid started: if HEAD or the
    tree moved since, the cell is refused (the modules in memory are the old ones).
    """
    cfg = spec.config(cell, smoke=smoke)
    version = code_version(repo_root)
    if pinned_version is not None and version != pinned_version:
        raise CodeVersionMismatch(
            f"the code version moved from {pinned_version} to {version} during the grid; "
            "modules are loaded once, so later cells would be labelled with code that did not run"
        )
    st = state or ledger.state([cell.cell_id], smoke=smoke)[cell.cell_id]
    chash = config_hash(cfg.to_dict(), version, lock_sha256(repo_root))
    if st.status == "complete":
        if st.code_version != version and not allow_code_change:
            raise CodeVersionMismatch(
                f"{cell.cell_id} was completed at {st.code_version}, this tree is {version}; "
                "a grid is run on one commit (use --allow-code-change with a reason, then "
                "mark the affected cells invalidated)"
            )
        if st.code_version == version and st.config_hash != chash:
            raise GridError(
                f"{cell.cell_id} was completed under another configuration at this commit "
                f"({st.config_hash} against {chash}); the spec changed after results existed"
            )
        if allow_code_change and st.code_version != version:
            ledger.append(
                "flag", cell.cell_id, flag=f"accepted_other_code_version:{allow_code_change}",
                previous_version=st.code_version, code_version=version,
            )  # fmt: skip
        return CellResult(cell.cell_id, "skipped", st.wall_s, 0, Path(st.dir) if st.dir else None)
    if st.status == "failed" and not retry_reason:
        return CellResult(cell.cell_id, "failed-kept", None, 0, None, st.reason)
    if require_clean and not tree_is_clean(repo_root):
        raise RuntimeError(f"the working tree is dirty ({version}); commit before a grid run")
    if st.status == "failed" and retry_reason:
        ledger.append("retry", cell.cell_id, reason=retry_reason, previous=st.reason)
    ledger.append(
        "started", cell.cell_id, code_version=version, config_hash=chash, smoke=smoke,
        seeds=list(cfg.seeds), variants=list(cfg.variants), delay=cell.delay,
        budget_pct=cell.budget_pct, arm=cell.arm,
    )  # fmt: skip
    t0 = time.perf_counter()
    try:
        summary = runner(
            cfg, source, out_root / cell.cell_id.split("/", 1)[1],
            repo_root=repo_root, memory_cap_bytes=memory_cap_bytes,
            cache=cache, max_windows=max_windows, pinned_version=version,
            # an invalidated cell is recomputed from scratch; otherwise continue a partial run
            **({"overwrite": True} if st.status == "invalidated" else {"resume": not smoke}),
        )  # fmt: skip
    except FileExistsError:
        # the run finished earlier but the ledger line was lost: adopt it, do not recompute
        d = out_root / cell.cell_id.split("/", 1)[1] / chash[:16]
        record = json.loads((d / "run.json").read_text(encoding="utf-8"))
        if (
            record.get("status") != "complete"
            or record.get("config_hash") != chash
            or record.get("max_windows") != max_windows
        ):
            reason = f"existing run directory {d} is not a finished run of this cell"
            ledger.append(
                "failed", cell.cell_id, reason=reason, code_version=version, config_hash=chash
            )
            return CellResult(cell.cell_id, "failed", None, 0, None, reason)
        ledger.append(
            "complete", cell.cell_id, code_version=version, config_hash=chash, dir=str(d),
            wall_s=record.get("wall_s"), adopted=True,
        )  # fmt: skip
        return CellResult(cell.cell_id, "adopted", record.get("wall_s"), 0, d)
    except BaseException as exc:  # noqa: BLE001 - logged with its reason, then re-raised if fatal
        reason = f"{type(exc).__name__}: {exc}"
        ledger.append(
            "failed", cell.cell_id, reason=reason, traceback=traceback.format_exc(),
            code_version=version, config_hash=chash,
            infrastructure="memory" in reason.lower() or isinstance(exc, KeyboardInterrupt),
        )  # fmt: skip
        if isinstance(exc, KeyboardInterrupt | SystemExit):
            raise
        return CellResult(cell.cell_id, "failed", None, 0, None, reason)
    wall = time.perf_counter() - t0
    max_fit = max(
        filter(None, (_max_fit_seconds(summary.dir), _slot_fit_max(summary.dir))), default=None
    )
    record = json.loads((summary.dir / "run.json").read_text(encoding="utf-8"))
    peak = (record.get("memory") or {}).get("peak_bytes")
    ledger.append(
        "complete", cell.cell_id, code_version=version, config_hash=chash, dir=str(summary.dir),
        wall_s=round(wall, 2), max_fit_s=max_fit, peak_gb=None if peak is None else peak / 1024**3,
        predictions_sha256=summary.predictions_sha256, n_windows=summary.n_windows,
        n_prediction_rows=summary.n_prediction_rows, smoke=smoke,
    )  # fmt: skip
    stop = False
    if max_fit is not None and max_fit > FIT_LIMIT_S:
        ledger.append("flag", cell.cell_id, flag=f"fit_over_{int(FIT_LIMIT_S)}s:{max_fit:.1f}")
        stop = True  # the shrink order is applied by the researcher's rule, not by this driver
    # one window row per (variant, seed, window, model): that count is the cell's unit count
    return CellResult(cell.cell_id, "complete", wall, summary.n_windows, summary.dir, None, stop)


def plan(
    spec: GridSpec,
    source: SlotSource | None = None,
    *,
    chunk: tuple[int, int] | None = None,
    smoke: bool = False,
) -> tuple[list[Cell], dict[str, int], dict[str, float]]:
    """(cells to run, planned units per cell, cost per cell) for this chunk."""
    cells = spec.cells()
    cfg0 = spec.config(cells[0])
    windows: dict[str, int] = {}
    if source is not None:
        for cell in cells:
            for v, n in window_counts(source, spec.config(cell)).items():
                windows.setdefault(v, n)
    n_models = len(cfg0.models)
    units = {c.cell_id: cell_units(c, n_models, windows) for c in cells}
    costs = {c.cell_id: cell_cost(c, units[c.cell_id]) for c in cells}
    if smoke:
        seen: set = set()
        keep = []
        for c in cells:  # one smoke cell per cost shape: extra seeds cost the same per unit
            if c.shape in seen:
                continue
            seen.add(c.shape)
            keep.append(c)
        cells = keep
    if chunk is not None:
        i, n = chunk
        mine = set(assign_chunks({c.cell_id: costs[c.cell_id] for c in cells}, n)[i - 1])
        cells = [c for c in cells if c.cell_id in mine]
    return cells, units, costs


def extrapolate(
    spec: GridSpec,
    smoke_seconds: Mapping[str, float],
    units: Mapping[str, int],
    smoke_units: Mapping[str, int],
) -> dict[str, Any]:
    """Seconds per unit from the smoke cells, applied to every planned cell of the same shape."""
    by_shape: dict[Any, float] = {}
    for c in spec.cells():
        if c.cell_id in smoke_seconds and smoke_units.get(c.cell_id):
            by_shape[c.shape] = smoke_seconds[c.cell_id] / smoke_units[c.cell_id]
    per_cell: dict[str, float] = {}
    for c in spec.cells():
        rate = by_shape.get(c.shape)
        if rate is not None:
            per_cell[c.cell_id] = rate * units[c.cell_id]
    missing = [c.cell_id for c in spec.cells() if c.cell_id not in per_cell]
    return {
        "per_cell_s": per_cell,
        "total_s": sum(per_cell.values()),
        "unmeasured": missing,
        "s_per_unit": {str(k): v for k, v in by_shape.items()},
    }


def ledger_for(out_root: Path | str, chunk: tuple[int, int] | None) -> Ledger:
    """One ledger file per chunk, so chunks run on other machines never write the same file."""
    name = LEDGER_NAME if chunk is None else f"ledger-chunk-{chunk[0]}-of-{chunk[1]}.jsonl"
    return Ledger(Path(out_root) / name)


def run_grid(
    spec: GridSpec,
    source: SlotSource,
    out_root: Path | str,
    *,
    repo_root: Path | str,
    chunk: tuple[int, int] | None = None,
    smoke: bool = False,
    max_windows: int | None = None,
    memory_cap_bytes: int = DEFAULT_MEMORY_CAP,
    require_clean: bool = True,
    allow_code_change: str | None = None,
    retry_reason: str | None = None,
    runner: Callable[..., Any] = run,
    on_cell: Callable[[CellResult], None] | None = None,
) -> list[CellResult]:
    """Run this chunk's cells one at a time; failures are logged and the next cell runs."""
    out = Path(out_root)
    repo = Path(repo_root)
    cells, _, _ = plan(spec, source, chunk=chunk, smoke=smoke)
    ledger = ledger_for(out, chunk)
    # the ledger is the progress record: planned cells are written once, before any run
    known = fold_events(merged_ledger_events(out), [c.cell_id for c in cells], smoke=smoke)
    pinned = code_version(repo)  # read once: modules are loaded once, labels must not drift
    cache = InitialModelCache()  # initial models are shared by cells: same rows, same seed
    results: list[CellResult] = []
    for cell in cells:
        res = run_cell(
            spec, cell, source, out, ledger, repo_root=repo, cache=cache,
            memory_cap_bytes=memory_cap_bytes, smoke=smoke,
            max_windows=(max_windows or 1) if smoke else max_windows,
            require_clean=require_clean, allow_code_change=allow_code_change,
            retry_reason=retry_reason, state=known[cell.cell_id], runner=runner,
            pinned_version=pinned,
        )  # fmt: skip
        results.append(res)
        if on_cell is not None:
            on_cell(res)
        if res.stop:
            log.error("%s: a fit exceeded %.0f s; stopping this chunk", cell.cell_id, FIT_LIMIT_S)
            break
    return results


def status(spec: GridSpec, out_root: Path | str) -> dict[str, Any]:
    """Planned against complete, failed and open cells, from every ledger under ``out_root``."""
    cells = spec.cells()
    state = fold_events(merged_ledger_events(out_root), [c.cell_id for c in cells])
    counts: dict[str, int] = {}
    for c in cells:
        counts[state[c.cell_id].status] = counts.get(state[c.cell_id].status, 0) + 1
    versions = sorted({s.code_version for s in state.values() if s.status == "complete"} - {None})
    return {
        "planned": len(cells),
        "counts": counts,
        "code_versions": versions,
        "failed": {
            c.cell_id: state[c.cell_id].reason for c in cells if state[c.cell_id].status == "failed"
        },  # fmt: skip
        "flags": {c.cell_id: state[c.cell_id].flags for c in cells if state[c.cell_id].flags},
        "cells": {c.cell_id: state[c.cell_id].status for c in cells},
    }
