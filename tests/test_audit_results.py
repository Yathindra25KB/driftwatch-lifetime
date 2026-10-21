"""The results audit lists folders and flags dirty, smoke and mixed-version runs."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_run(folder: Path, version: str, **extra) -> None:
    folder.mkdir(parents=True)
    body = {"status": "complete", "code_version": version, **extra}
    (folder / "run.json").write_text(json.dumps(body), encoding="utf-8")


def test_the_audit_flags_dirty_smoke_mixed_and_tooling_folders(tmp_path: Path) -> None:
    audit = load_script("audit_results")
    res = tmp_path / "results"
    write_run(res / "e3" / "a" / "x", "abc1234")
    write_run(res / "e3" / "a" / "y", "abc1234")
    write_run(res / "e0" / "r1", "abc1234")
    write_run(res / "e0" / "r2", "def5678-dirty")
    write_run(res / "e4_smoke" / "z", "abc1234", max_windows=1)
    (res / "bench").mkdir()
    (res / "bench" / "fit_times.json").write_text("{}", encoding="utf-8")
    failed = res / "e2" / "c"
    failed.mkdir(parents=True)
    (failed / "run_failed.json").write_text("{}", encoding="utf-8")

    rows = {r.folder: r for r in audit.collect(res)}
    assert rows["e3"].n_complete == 2 and rows["e3"].flags == []
    assert set(rows["e0"].flags) == {"dirty", "several versions"}
    assert "smoke" in rows["e4_smoke"].flags
    assert rows["bench"].flags == ["tooling output (no run.json)"]
    assert "has failed runs" in rows["e2"].flags


def test_main_writes_the_table_and_deletes_nothing(tmp_path: Path) -> None:
    audit = load_script("audit_results")
    res = tmp_path / "results"
    write_run(res / "e3" / "a", "abc1234")
    out = tmp_path / "audit.md"
    assert audit.main(["--results", str(res), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "| e3 | 1 | 0 | abc1234 (?) | none |" in text
    assert (res / "e3" / "a" / "run.json").exists()
    assert audit.main(["--results", str(tmp_path / "missing"), "--out", str(out)]) == 1


def test_src_changes_since_counts_files_between_a_commit_and_head() -> None:
    audit = load_script("audit_results")
    assert audit.src_changes_since("0000000") is None  # not a commit
    head = audit.src_changes_since("HEAD")
    assert head == 0
