"""The E2 grid driver: expansion, never-dedupe, chunks, ledger, failures, smoke.

Synthetic timelines only (code-behaviour checks, never evidence). The expensive part, a real
simulation run, is exercised with a tiny stream; the driver logic is what is under test.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from conftest import GIT

from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.sim import grid
from driftwatch.sim.config import ConfigError, RunConfig
from driftwatch.sim.grid import GridError, GridSpec, Ledger
from driftwatch.sim.runner import run

ROOT = Path(__file__).resolve().parents[1]
ANCHOR = np.datetime64("2019-01-07", "ns")
WIDTH = np.timedelta64(14, "D")


def source(n_slots: int = 12, rows: int = 200):
    from driftwatch.data.synthetic import drifting_timeline

    table, X = drifting_timeline(n_slots=n_slots, rows_per_slot=rows, drift=1.0, seed=0)
    return TableSource(table, FixedWidthScheme(ANCHOR, WIDTH), x=X, name="synthetic")


def spec_dict(**grid_over) -> dict:
    g = {
        "delay": [0, 1, 2, 3],
        "budget_pct": [0.5, 1.0, 2.0, 5.0],
        "policy": {"name": "periodic", "period": 3},
        "selector": {"name": "random", "calibration_fraction": 0.2},
        "seeds": [0, 1],
        "headline": {
            "seeds": [2, 3],
            "cells": [[0, 1.0], [0, 5.0], [3, 1.0], [3, 5.0], [0, 0.5], [0, 2.0]],
        },
        "chow": {"seeds": [0, 1], "cells": [[0, 1.0], [0, 5.0], [3, 1.0], [3, 5.0]]},
        "never": {"seeds": [0, 1, 2, 3], "variants": ["rolling", "rolling_chow"]},
    }
    g.update(grid_over)
    return {
        "name": "e2_test",
        "dataset": "bodmas",
        "slots": {"preset": "adr-0004", "min_malware": 5},
        "window": {"nT": 3, "nE": 6, "stride": 2},
        "ratio": {"target": 0.10, "sensitivity": 0.05},
        "model": [{"name": "lr"}],
        "e0": {"variants": ["rolling"], "random_split": False},
        "output": "unused",
        "grid": g,
    }


def small_spec() -> GridSpec:
    return GridSpec.from_dict(
        spec_dict(
            delay=[0, 3],
            budget_pct=[1.0, 5.0],
            seeds=[0],
            headline={"seeds": [1], "cells": [[0, 1.0]]},
            chow={"seeds": [0], "cells": [[0, 5.0]]},
            never={"seeds": [0, 1], "variants": ["rolling", "rolling_chow"]},
        )
    )


def plain_runner(cfg, src, out, *, resume=False, **kw):
    """``run`` without resume (the working tree is dirty during development)."""
    return run(cfg, src, out, **kw)


# --- expansion --------------------------------------------------------------------------------


def test_expansion_counts_and_roles() -> None:
    cells = GridSpec.from_dict(spec_dict()).cells()
    roles = [c.role for c in cells]
    assert len(cells) == 27
    assert (roles.count("grid"), roles.count("headline")) == (16, 6)
    assert (roles.count("chow"), roles.count("never")) == (4, 1)
    assert len({c.cell_id for c in cells}) == 27


def test_every_cell_is_an_ordinary_run_config_with_scalar_delay_and_budget() -> None:
    spec = GridSpec.from_dict(spec_dict())
    for c in spec.cells():
        cfg = spec.config(c)
        assert isinstance(cfg, RunConfig)
        if c.arm == "periodic":
            assert (cfg.policy, cfg.delay, cfg.budget_pct) == ("periodic", c.delay, c.budget_pct)
            assert cfg.policy_period == 3 and cfg.selector == "random"
        else:
            assert (cfg.policy, cfg.selector, cfg.delay, cfg.budget_pct) == (
                "never",
                None,
                None,
                None,
            )
    chow = [c for c in spec.cells() if c.role == "chow"]
    assert all(spec.config(c).variants == ("rolling_chow",) for c in chow)


def test_run_config_refuses_a_grid_file() -> None:
    with pytest.raises(ConfigError, match="grid"):
        RunConfig.from_dict(spec_dict())


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(seeds=[0]), "inside grid"),
        (lambda d: d["grid"].update(unknown=1), "unknown grid key"),
        (lambda d: d["grid"]["headline"].update(seeds=[0, 1]), "already run"),
        (lambda d: d["grid"]["headline"].update(cells=[[9, 1.0]]), "outside the grid"),
        (lambda d: d["grid"].update(delay=[0, 0, 1]), "repeat"),
        (lambda d: d["grid"].update(seeds=[]), "explicit"),
    ],
)
def test_bad_specs_fail_at_parse_time(mutate, message) -> None:
    d = spec_dict()
    mutate(d)
    with pytest.raises(GridError, match=message):
        GridSpec.from_dict(d)


# --- never does not depend on delay or budget -------------------------------------------------


def test_never_arm_is_the_same_for_every_delay_and_budget() -> None:
    src = source()
    base = spec_dict()
    spec = GridSpec.from_dict(base)
    never = next(c for c in spec.cells() if c.arm == "never")
    cfg_never = spec.config(never)
    cfg_never = RunConfig.from_dict({**cfg_never.to_dict(), "seeds": [0]})
    out = []
    for delay, budget in [(0, 0.5), (3, 5.0)]:
        d = cfg_never.to_dict()
        d.update({"selector": "random", "delay": delay, "budget_pct": budget, "policy": "never"})
        d["e0"] = {"variants": ["rolling"], "random_split": False}
        out.append(RunConfig.from_dict(d))
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        runs = [run(c, src, Path(tmp) / str(i), repo_root=ROOT) for i, c in enumerate(out)]
        runs.append(
            run(
                RunConfig.from_dict({**cfg_never.to_dict(), "e0": {"variants": ["rolling"]}}),
                src,
                Path(tmp) / "base",
                repo_root=ROOT,
            )
        )
        cols = ["window_id", "slot_id", "row_id", "pred"]
        frames = [
            pd.read_parquet(r.dir / "predictions.parquet")
            .query("series == 'time_aware'")
            .sort_values(cols[:3])[cols]
            .reset_index(drop=True)
            for r in runs
        ]
    assert len(frames[0]) > 0
    for f in frames[1:]:
        pd.testing.assert_frame_equal(frames[0], f)


# --- chunks and cost --------------------------------------------------------------------------


def test_chunks_partition_every_cell_exactly_once_and_are_balanced() -> None:
    spec = GridSpec.from_dict(spec_dict())
    cells, units, costs = grid.plan(spec, source())
    assert len(cells) == 27
    for n in (1, 3, 11):
        parts = [grid.plan(spec, source(), chunk=(i, n))[0] for i in range(1, n + 1)]
        ids = [c.cell_id for p in parts for c in p]
        assert sorted(ids) == sorted(c.cell_id for c in cells)
        loads = [sum(costs[c.cell_id] for c in p) for p in parts]
        assert max(loads) - min(loads) <= max(costs.values()) + 1e-9


def test_chunk_assignment_is_deterministic() -> None:
    costs = {f"c{i}": float(i % 5 + 1) for i in range(20)}
    assert grid.assign_chunks(costs, 4) == grid.assign_chunks(dict(reversed(costs.items())), 4)


@pytest.mark.parametrize("bad", ["0/3", "4/3", "x", "1-3"])
def test_chunk_syntax(bad) -> None:
    with pytest.raises(ValueError):
        grid.parse_chunk(bad)
    assert grid.parse_chunk("2/11") == (2, 11)


def test_units_count_windows_seeds_and_models() -> None:
    spec = small_spec()
    cells = {c.role: c for c in spec.cells() if c.role in {"never", "chow"}}
    assert grid.cell_units(cells["never"], 2, {"rolling": 6, "rolling_chow": 4}) == (6 + 4) * 2 * 2
    assert grid.cell_units(cells["chow"], 2, {"rolling_chow": 4}) == 4 * 1 * 2


# --- driver: ledger, failures, resume ---------------------------------------------------------


def run_small(tmp_path: Path, runner=plain_runner, **kw):
    return grid.run_grid(
        small_spec(), source(), tmp_path, repo_root=ROOT, require_clean=False, runner=runner, **kw
    )


def test_driver_runs_all_cells_and_records_them(tmp_path: Path) -> None:
    results = run_small(tmp_path)
    spec = small_spec()
    assert [r.status for r in results] == ["complete"] * len(spec.cells())
    st = grid.status(spec, tmp_path)
    assert st["planned"] == len(spec.cells()) == st["counts"]["complete"]
    assert not st["failed"]
    for r in results:
        assert (r.dir / "predictions.parquet").exists() and (r.dir / "run.json").exists()
    rows = Ledger(tmp_path / "ledger.jsonl").events()
    assert {r["event"] for r in rows} == {"started", "complete"}


def test_interrupted_grid_resumes_without_rerunning_finished_cells(tmp_path: Path) -> None:
    calls: list[str] = []

    def counting(cfg, src, out, **kw):
        calls.append(cfg.name)
        return plain_runner(cfg, src, out, **kw)

    first = run_small(tmp_path, counting)
    assert len(calls) == len(first)
    calls.clear()
    again = run_small(tmp_path, counting)
    assert calls == [] and {r.status for r in again} == {"skipped"}


def test_failure_is_logged_with_its_reason_and_the_next_cell_runs(tmp_path: Path) -> None:
    spec = small_spec()
    bad = spec.cells()[2].cell_id.split("/", 1)[1]

    def flaky(cfg, src, out, **kw):
        if cfg.name.endswith(bad):
            raise RuntimeError("synthetic failure for the test")
        return plain_runner(cfg, src, out, **kw)

    results = run_small(tmp_path, flaky)
    by = {r.cell_id: r for r in results}
    failed = [r for r in results if r.status == "failed"]
    assert len(failed) == 1 and "synthetic failure" in (failed[0].reason or "")
    assert sum(r.status == "complete" for r in results) == len(results) - 1
    st = grid.status(spec, tmp_path)
    assert list(st["failed"]) == [failed[0].cell_id] and by[failed[0].cell_id].dir is None
    # a rerun does not retry a failure on its own (no result-driven reruns)
    again = run_small(tmp_path, flaky)
    assert [r.status for r in again].count("failed-kept") == 1
    # an explicit, reasoned retry is recorded as such
    fixed = run_small(tmp_path, plain_runner, retry_reason="cap hit by another process")
    assert [r.status for r in fixed].count("complete") == 1
    events = Ledger(tmp_path / "ledger.jsonl").events()
    assert any(e["event"] == "retry" and "cap hit" in e["reason"] for e in events)
    assert grid.status(spec, tmp_path)["counts"] == {"complete": len(spec.cells())}


def test_memory_failures_are_marked_infrastructure(tmp_path: Path) -> None:
    def oom(cfg, src, out, **kw):
        raise MemoryError("memory cap exceeded (synthetic)")

    run_small(tmp_path, oom)
    failed = [e for e in Ledger(tmp_path / "ledger.jsonl").events() if e["event"] == "failed"]
    assert failed and all(e["infrastructure"] for e in failed)


def test_a_grid_is_refused_across_code_versions(tmp_path: Path) -> None:
    spec = small_spec()
    ledger = Ledger(tmp_path / "ledger.jsonl")
    cell = spec.cells()[0]
    ledger.append("complete", cell.cell_id, code_version="0000000", config_hash="x", dir="d")
    with pytest.raises(grid.CodeVersionMismatch):
        run_small(tmp_path)


def test_invalidated_cells_are_rerun_and_the_reason_is_kept(tmp_path: Path) -> None:
    spec = small_spec()
    run_small(tmp_path)
    cell = spec.cells()[1]
    Ledger(tmp_path / "ledger.jsonl").append(
        "invalidated", cell.cell_id, reason="bug fixed in commit abc"
    )
    st = grid.status(spec, tmp_path)
    assert st["counts"]["invalidated"] == 1
    again = run_small(tmp_path, allow_code_change="bug fix")
    assert [r.status for r in again].count("complete") == 1
    assert grid.status(spec, tmp_path)["counts"] == {"complete": len(spec.cells())}


def test_chunk_ledgers_are_separate_files_and_merge_in_status(tmp_path: Path) -> None:
    spec = small_spec()
    n = 2
    for i in (1, n):
        grid.run_grid(
            spec, source(), tmp_path, repo_root=ROOT, chunk=(i, n), require_clean=False,
            runner=plain_runner,
        )  # fmt: skip
    names = sorted(p.name for p in tmp_path.glob("ledger*.jsonl"))
    assert names == ["ledger-chunk-1-of-2.jsonl", "ledger-chunk-2-of-2.jsonl"]
    assert grid.status(spec, tmp_path)["counts"] == {"complete": len(spec.cells())}


def test_fit_over_the_limit_stops_the_chunk_and_is_flagged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(grid, "_max_fit_seconds", lambda d: 61.0)
    results = run_small(tmp_path)
    assert len(results) == 1 and results[0].stop
    flags = grid.status(small_spec(), tmp_path)["flags"]
    assert any("fit_over_60s" in f for fl in flags.values() for f in fl)


# --- smoke ------------------------------------------------------------------------------------


def test_smoke_runs_one_seed_one_window_per_cost_shape(tmp_path: Path) -> None:
    spec = small_spec()
    cells, _, _ = grid.plan(spec, source(), smoke=True)
    shapes = {c.shape for c in spec.cells()}
    assert len(cells) == len(shapes) < len(spec.cells())  # the extra-seed cell is not repeated
    results = grid.run_grid(
        spec, source(), tmp_path, repo_root=ROOT, smoke=True, require_clean=False,
        runner=plain_runner,
    )  # fmt: skip
    for r in results:
        rec = json.loads((r.dir / "run.json").read_text(encoding="utf-8"))
        assert rec["max_windows"] == 1 and len(rec["seeds"]) == 1
        w = pd.read_parquet(r.dir / "windows.parquet")
        assert w.groupby(["variant", "seed", "model"]).size().max() == 1


def test_extrapolation_scales_seconds_per_unit_to_every_cell_of_that_shape() -> None:
    spec = small_spec()
    cells, units, _ = grid.plan(spec, source())
    smoke_cells, smoke_units, _ = grid.plan(spec, source(), smoke=True)
    secs = {c.cell_id: 10.0 for c in smoke_cells}
    su = {c.cell_id: 1 for c in smoke_cells}
    est = grid.extrapolate(spec, secs, units, su)
    assert not est["unmeasured"] or all(
        c.cell_id in est["unmeasured"]
        for c in cells
        if c.shape not in {x.shape for x in smoke_cells}
    )
    grid_cell = next(c for c in cells if c.role == "grid")
    assert est["per_cell_s"][grid_cell.cell_id] == pytest.approx(10.0 * units[grid_cell.cell_id])
    del smoke_units


# --- clean tree -------------------------------------------------------------------------------


def test_tree_is_clean_sees_untracked_code(tmp_path: Path) -> None:
    def git(*a):
        subprocess.run([*GIT, *a], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "init")
    assert grid.tree_is_clean(tmp_path)
    (tmp_path / "src" / "b.py").write_text("y = 2\n", encoding="utf-8")  # untracked code
    assert not grid.tree_is_clean(tmp_path)
    (tmp_path / "src" / "b.py").unlink()
    (tmp_path / "notes.txt").write_text("not code\n", encoding="utf-8")  # untracked, not code
    assert grid.tree_is_clean(tmp_path)
    (tmp_path / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")  # tracked edit
    assert not grid.tree_is_clean(tmp_path)


# --- command line -----------------------------------------------------------------------------


def test_cli_grid_status_and_bad_chunk(tmp_path: Path, capsys) -> None:
    import yaml

    from driftwatch import cli

    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(spec_dict()), encoding="utf-8")
    assert cli.main(["grid", str(spec_path), "--status", "--out", str(tmp_path / "r")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["planned"] == 27 and report["counts"] == {"planned": 27}
    assert cli.main(["grid", str(spec_path), "--chunk", "4/3", "--out", str(tmp_path / "r")]) == 2


def test_cli_run_refuses_a_grid_spec(tmp_path: Path, capsys) -> None:
    import yaml

    from driftwatch import cli

    spec_path = tmp_path / "spec.yaml"
    spec_path.write_text(yaml.safe_dump(spec_dict()), encoding="utf-8")
    assert cli.main(["run", str(spec_path)]) == 2
    assert "grid" in capsys.readouterr().err


# --- review hardening (leakage review, Phase 6) -----------------------------------------------


def test_smoke_events_never_complete_a_real_cell(tmp_path: Path) -> None:
    spec = small_spec()
    grid.run_grid(
        spec, source(), tmp_path, repo_root=ROOT, smoke=True, require_clean=False,
        runner=plain_runner,
    )  # fmt: skip
    # the same root: the smoke ledger lines must not count as finished cells
    assert grid.status(spec, tmp_path)["counts"] == {"planned": len(spec.cells())}
    results = run_small(tmp_path)
    assert all(r.status == "complete" for r in results)
    full = [r for r in results if r.status == "complete"]
    assert len(full) == len(spec.cells())


def test_adopting_a_directory_checks_what_it_is(tmp_path: Path) -> None:
    spec = small_spec()
    cell = next(c for c in spec.cells() if c.arm == "periodic")
    cfg = spec.config(cell)
    # a one-window smoke result sitting where the full cell will be written: same config hash
    # (single seed), so the runner finds a finished directory
    src = source()
    out = tmp_path / cell.cell_id.split("/", 1)[1]
    run(cfg, src, out, repo_root=ROOT, max_windows=1)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    res = grid.run_cell(
        spec, cell, src, tmp_path, ledger, repo_root=ROOT, cache=grid.InitialModelCache(),
        require_clean=False, runner=plain_runner,
    )  # fmt: skip
    assert res.status == "failed" and "not a finished run of this cell" in (res.reason or "")


def test_cell_config_hash_does_not_depend_on_the_output_root() -> None:
    spec = small_spec()
    cell = spec.cells()[1]
    a = spec.config(cell).to_dict()
    assert a["output"].startswith("unused/") and "periodic" in a["output"]
    assert spec.config(cell, smoke=True).to_dict()["output"].startswith("unused-smoke/")


def test_a_moved_code_version_stops_the_grid(tmp_path: Path) -> None:
    spec = small_spec()
    cell = spec.cells()[0]
    with pytest.raises(grid.CodeVersionMismatch, match="moved"):
        grid.run_cell(
            spec, cell, source(), tmp_path, Ledger(tmp_path / "l.jsonl"), repo_root=ROOT,
            cache=grid.InitialModelCache(), require_clean=False, runner=plain_runner,
            pinned_version="0000000",
        )  # fmt: skip


def test_a_completed_cell_under_another_config_is_refused(tmp_path: Path) -> None:
    spec = small_spec()
    cell = spec.cells()[0]
    version = grid.code_version(ROOT)
    Ledger(tmp_path / "ledger.jsonl").append(
        "complete", cell.cell_id, code_version=version, config_hash="not-this-one", dir="d"
    )
    with pytest.raises(GridError, match="another configuration"):
        run_small(tmp_path)


def test_never_arm_must_cover_the_seeds_and_variants_of_every_contrast() -> None:
    with pytest.raises(GridError, match="never.seeds"):
        GridSpec.from_dict(spec_dict(never={"seeds": [0], "variants": ["rolling", "rolling_chow"]}))
    with pytest.raises(GridError, match="never.variants"):
        GridSpec.from_dict(spec_dict(never={"seeds": [0, 1, 2, 3], "variants": ["rolling"]}))


def test_a_transient_unknown_code_version_is_retried(monkeypatch) -> None:
    answers = iter(["unknown", "unknown", "abc1234"])
    monkeypatch.setattr(grid, "code_version", lambda repo: next(answers))
    monkeypatch.setattr(grid.time, "sleep", lambda s: None)
    assert grid.stable_code_version(ROOT) == "abc1234"
    monkeypatch.setattr(grid, "code_version", lambda repo: "unknown")
    assert grid.stable_code_version(ROOT, tries=3) == "unknown"  # never believed, never invented
