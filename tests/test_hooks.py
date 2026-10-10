"""Unit tests for the PostToolUse formatter, the Stop gate and the SessionStart re-injection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import ROOT, load_hook


@pytest.fixture(scope="module")
def fmt():
    return load_hook("format")


@pytest.fixture(scope="module")
def stop_gate():
    return load_hook("stop_gate")


@pytest.fixture(scope="module")
def reinject():
    return load_hook("reinject")


def test_formatter_reformats_python_file(fmt, tmp_path, monkeypatch):
    target = tmp_path / "ugly.py"
    target.write_text("import os\nx=[1,2 ,3]\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(target)}, "cwd": str(tmp_path)}
    assert fmt.main(json.dumps(payload)) == 0
    assert target.read_text(encoding="utf-8") == "x = [1, 2, 3]\n"  # formatted, unused import fixed


def test_formatter_ignores_non_python_and_bad_input(fmt, tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    note = tmp_path / "notes.md"
    note.write_text("x=1\n", encoding="utf-8")
    payload = {"tool_name": "Write", "tool_input": {"file_path": str(note)}, "cwd": str(tmp_path)}
    assert fmt.main(json.dumps(payload)) == 0
    assert note.read_text(encoding="utf-8") == "x=1\n"
    assert fmt.main("not json") == 0


def test_formatter_skips_files_outside_project(fmt, tmp_path, monkeypatch):
    outside = tmp_path / "outside.py"
    outside.write_text("x=1\n", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    payload = {"tool_name": "Edit", "tool_input": {"file_path": str(outside)}, "cwd": str(project)}
    assert fmt.main(json.dumps(payload)) == 0
    assert outside.read_text(encoding="utf-8") == "x=1\n"


def test_stop_gate_never_loops(stop_gate, tmp_path, monkeypatch):
    (tmp_path / "test_red.py").write_text("def test_red():\n    assert False\n", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert stop_gate.main(json.dumps({"stop_hook_active": True, "cwd": str(tmp_path)})) == 0


def test_stop_gate_treats_no_tests_as_green(stop_gate, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert stop_gate.main(json.dumps({"stop_hook_active": False, "cwd": str(tmp_path)})) == 0
    assert "no tests" in capsys.readouterr().err.lower()


def test_reinject_prints_rules_phase_and_status(reinject, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(ROOT))
    assert reinject.main(json.dumps({"source": "compact", "cwd": str(ROOT)})) == 0
    out = capsys.readouterr().out
    assert "Never download, run, open, decompile" in out  # hard rule 1
    assert "G1, end of week 4" in out  # stop rules
    assert "Foundations and governance" in out  # PHASES.md status
    assert len(out) < 10_000  # Claude Code caps injected context at 10,000 characters


def test_reinject_survives_missing_files(reinject, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert reinject.main("{}") == 0
    assert "CLAUDE.md" in capsys.readouterr().out


def test_hook_files_are_stdlib_only():
    allowed = {
        "__future__", "base64", "contextlib", "dataclasses", "json", "os", "pathlib", "re",
        "shlex", "subprocess", "sys", "tempfile",
    }  # fmt: skip
    for path in (ROOT / ".claude" / "hooks").glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(("import ", "from ")):
                module = line.split()[1].split(".")[0]
                assert module in allowed, f"{path.name}: non-stdlib import {module}"


def test_hooks_have_no_bash_only_scripts():
    assert not list(Path(ROOT / ".claude" / "hooks").glob("*.sh"))
