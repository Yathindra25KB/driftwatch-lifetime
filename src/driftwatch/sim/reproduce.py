"""`driftwatch reproduce table1`: rebuild Table 1 (E0 on BODMAS), compare with the stored one.

Steps (full mode): check the lock file against the recorded one, make sure the BODMAS cache
exists and verifies (download through the manifest and build when it does not; a failed
download prints the documented manual path and exits with code 3), run ``configs/e0_bodmas.yaml``
on a clean tree, build the table with the same code as ``scripts/make_e0_table.py`` and compare
it row by row with ``reports/tables/e0_baselines.csv`` within a stated tolerance.

Smoke mode does the same on the committed synthetic fixture (a tiny E0 run) and compares with
``tests/golden/table1_smoke.csv``. Fixture numbers test the code path only; they are never
evidence.

The comparison is a finding, not something to tune: a mismatch is reported with its cells and
the run is never repeated until it looks right.
"""

from __future__ import annotations

import json
import platform
import tempfile
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from driftwatch.metrics.e0_tables import KEYS, build_tables, check_run
from driftwatch.sim.config import RunConfig, lock_sha256, package_versions

DEFAULT_TOLERANCE = 0.002  # absolute, per cell; counts must match exactly (estimate, PHASES.md)
# The random-split comparator draws its split from a seed keyed by the window id, and the window
# id embeds a digest of the data manifest, whose content hash changes with every rebuild (build
# times, paths). On another machine the comparator is therefore a different random draw: it is
# compared at a looser, stated tolerance. The time-aware columns do not depend on it.
COMPARATOR_COLUMNS = {
    "f1_random_split", "gap", "gap_ci_low", "gap_ci_high", "gap_window_min", "gap_window_max",
    "f1_random_pooled", "gap_pooled", "random_test_ratio",
}  # fmt: skip
COMPARATOR_TOLERANCE = 0.02  # [estimate]; the observed differences are reported next to it
IGNORED = {"fit_seconds_median", "sanity_band"}  # timing and a placeholder column
SMOKE_GOLDEN = Path("tests/golden/table1_smoke.csv")
STORED_TABLE = Path("reports/tables/e0_baselines.csv")
SMOKE_CONFIG: dict[str, Any] = {
    "name": "table1_smoke",
    "dataset": "bodmas",
    "slots": {"preset": "adr-0004", "min_malware": 1},
    "window": {"nT": 1, "nE": 2, "stride": 1},
    "ratio": {"target": 0.4, "sensitivity": 0.2},
    "seeds": [0],
    "model": [
        {"name": "lr", "C": 1.0, "max_iter": 1000, "tol": 0.0001},
        {"name": "lgbm", "profile": "fast", "n_jobs": 1},
    ],
    "policy": "never",
    "e0": {"variants": ["rolling"], "random_split": False},
    "output": "results/table1_smoke",
}


class ReproductionError(RuntimeError):
    """The reproduction could not be run (not a mismatch)."""


@dataclass
class Comparison:
    ok: bool
    n_rows: int
    max_abs_diff: float
    problems: list[str] = field(default_factory=list)
    worst: list[dict[str, Any]] = field(default_factory=list)
    max_comparator_diff: float = 0.0


def _is_count(column: str) -> bool:
    return column.startswith("n_") or column in {"window_slot_cells"}


def compare_tables(
    new: pd.DataFrame,
    stored: pd.DataFrame,
    tolerance: float = DEFAULT_TOLERANCE,
    comparator_tolerance: float = COMPARATOR_TOLERANCE,
) -> Comparison:
    """Row-by-row comparison on (dataset, model, variant, ratio).

    Same row set required; count columns (``n_*``) must be equal; other numeric columns must
    agree within ``tolerance`` (absolute), the random-split comparator columns within
    ``comparator_tolerance`` (see COMPARATOR_COLUMNS); strings must be equal; timing columns
    are ignored.
    """
    problems: list[str] = []
    new = new.copy()
    stored = stored.copy()
    for df in (new, stored):
        df["ratio"] = df["ratio"].round(6)
    a = new.set_index(KEYS).sort_index()
    b = stored.set_index(KEYS).sort_index()
    if set(a.index) != set(b.index):
        only_new = sorted(set(a.index) - set(b.index))
        only_old = sorted(set(b.index) - set(a.index))
        problems.append(f"row sets differ: only new {only_new}, only stored {only_old}")
        return Comparison(False, len(a), float("nan"), problems)
    cols = [c for c in b.columns if c in a.columns and c not in IGNORED]
    missing = sorted(set(b.columns) - set(a.columns) - IGNORED)
    if missing:
        problems.append(f"columns missing from the rebuilt table: {missing}")
    max_diff = 0.0
    max_comparator = 0.0
    worst: list[dict[str, Any]] = []
    for key in b.index:
        for c in cols:
            x, y = a.at[key, c], b.at[key, c]
            if pd.isna(x) and pd.isna(y):
                continue
            if isinstance(y, str) or isinstance(x, str):
                if str(x) != str(y):
                    problems.append(f"{key} {c}: {x!r} != {y!r}")
                continue
            if pd.isna(x) != pd.isna(y):
                problems.append(f"{key} {c}: {x!r} != {y!r}")
                continue
            d = abs(float(x) - float(y))
            if _is_count(c):
                if d != 0:
                    problems.append(f"{key} {c}: count {x} != {y}")
                continue
            limit = comparator_tolerance if c in COMPARATOR_COLUMNS else tolerance
            if c not in COMPARATOR_COLUMNS:
                max_diff = max(max_diff, d)
            else:
                max_comparator = max(max_comparator, d)
            if d > limit:
                problems.append(f"{key} {c}: |{x} - {y}| = {d:.6f} > {limit}")
            worst.append({"key": [str(k) for k in key], "column": c, "diff": d})
    worst = sorted(worst, key=lambda r: -r["diff"])[:5]
    return Comparison(not problems, len(b), max_diff, problems, worst, max_comparator)


def smoke_config(output: str | None = None) -> RunConfig:
    d = json.loads(json.dumps(SMOKE_CONFIG))
    if output:
        d["output"] = output
    return RunConfig.from_dict(d)


def _ensure_bodmas(data_root: Path, memory_cap_bytes: int, log: list[str]) -> None:
    from driftwatch.data import download
    from driftwatch.data.build import build_dataset
    from driftwatch.data.cache import Layout
    from driftwatch.data.verify import verify

    layout = Layout(data_root)
    if not verify(layout, ("bodmas",)):
        log.append("BODMAS cache present and verified; nothing to fetch")
        return
    log.append("BODMAS cache missing or not verified: fetching through the manifest")
    download.download_bodmas(layout, manual=False)  # may raise ManualDownloadRequired
    build_dataset("bodmas", layout, memory_cap_bytes=memory_cap_bytes)
    problems = verify(layout, ("bodmas",))
    if problems:
        raise ReproductionError("data verify failed after the build: " + "; ".join(problems))


def reproduce_table1(
    *,
    repo_root: Path | str,
    data_root: Path | str = "data",
    out_dir: Path | str = "reports/reproduction",
    work_dir: Path | str | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    smoke: bool = False,
    memory_cap_gb: float = 1.5,
    require_clean: bool = True,
    stored_table: Path | str | None = None,
    write_reference: bool = False,
) -> dict[str, Any]:
    """Run the reproduction and return (and write) its report."""
    from driftwatch.sim.runner import run

    repo = Path(repo_root)
    t0 = time.perf_counter()
    notes: list[str] = []
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cap = int(memory_cap_gb * 1024**3)
    work = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="driftwatch-table1-"))
    if smoke:
        from driftwatch.data.build import build_dataset
        from driftwatch.data.cache import Layout
        from driftwatch.data.presets import cached_source

        root = work / "data"
        fixture = repo / "tests" / "fixtures" / "synthetic"
        if not fixture.exists():
            raise ReproductionError(f"smoke mode needs the committed fixture at {fixture}")
        build_dataset("bodmas", Layout(root), raw_layout=Layout(fixture), batch_size=16)
        cfg = smoke_config(str(work / "results"))
        source = cached_source("bodmas", root)
        reference = Path(stored_table) if stored_table else repo / SMOKE_GOLDEN
    else:
        root = Path(data_root)
        _ensure_bodmas(root, cap, notes)
        cfg = RunConfig.from_file(repo / "configs" / "e0_bodmas.yaml")
        from driftwatch.data.presets import cached_source

        source = cached_source("bodmas", root)
        reference = Path(stored_table) if stored_table else repo / STORED_TABLE
    results_root = work / "results" if (smoke or work_dir) else repo / cfg.output
    strict = require_clean and not smoke
    summary = run(
        cfg,
        source,
        results_root,
        repo_root=repo,
        memory_cap_bytes=cap,
        require_clean=strict,
        overwrite=True,
    )
    if strict:
        check_run(summary.dir)  # a partial or dirty run is never Table 1
    table, _ = build_tables({"bodmas": summary.dir})
    table = table.round(4)
    new_path = out / ("table1_smoke_rebuilt.csv" if smoke else "table1_rebuilt.csv")
    table.to_csv(new_path, index=False, lineterminator="\n")
    if write_reference:
        reference.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(reference, index=False, lineterminator="\n")
        notes.append(f"reference written to {reference}")
    stored = pd.read_csv(reference)
    stored = stored[stored["dataset"] == "bodmas"]
    cmp = compare_tables(table, stored, tolerance)
    record = json.loads((summary.dir / "run.json").read_text(encoding="utf-8"))
    report = {
        "command": "reproduce table1" + (" --smoke" if smoke else ""),
        "verdict": "MATCH" if cmp.ok else "MISMATCH",
        "tolerance_abs": tolerance,
        "rows_compared": cmp.n_rows,
        "max_abs_diff": cmp.max_abs_diff,
        "comparator_tolerance_abs": COMPARATOR_TOLERANCE,
        "max_abs_diff_comparator_columns": cmp.max_comparator_diff,
        "problems": cmp.problems[:50],
        "largest_differences": cmp.worst,
        "reference": str(reference),
        "rebuilt_table": str(new_path),
        "run_dir": str(summary.dir),
        "config_hash": summary.config_hash,
        "predictions_sha256": summary.predictions_sha256,
        "code_version": record.get("code_version"),
        "lock_sha256": lock_sha256(repo),
        "packages": package_versions(),
        "platform": platform.platform(),
        "run_wall_s": round(summary.wall_s, 1),
        "total_wall_s": round(time.perf_counter() - t0, 1),
        "peak_bytes": (record.get("memory") or {}).get("peak_bytes"),
        "notes": notes,
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "evidence": not smoke,
    }
    name = f"table1{'_smoke' if smoke else ''}_{report['date']}.json"
    (out / name).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
