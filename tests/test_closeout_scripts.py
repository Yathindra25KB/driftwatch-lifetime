"""Tests for the phase-closeout skill's helper scripts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from conftest import ROOT

SCRIPTS = ROOT / ".claude" / "skills" / "phase-closeout" / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"closeout_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def handoff():
    return load("check_handoff")


@pytest.fixture(scope="module")
def hashes():
    return load("config_hashes")


def test_handoff_items_of_phase_1(handoff):
    items = handoff.handoff_items((ROOT / "docs/prompts/phase-01.md").read_text(encoding="utf-8"))
    assert "pyproject.toml" in items and "uv.lock" in items and ".gitignore" in items
    assert "docs/DECISIONS/" in items  # parenthetical note stripped
    assert [i for i in items if i.startswith("docs/prompts/phase-")] == [
        f"docs/prompts/phase-{n:02d}.md" for n in range(1, 13)
    ]  # "phase-01.md to phase-12.md" expanded


def test_handoff_items_of_phase_2(handoff):
    items = handoff.handoff_items((ROOT / "docs/prompts/phase-02.md").read_text(encoding="utf-8"))
    assert items[0] == "src/driftwatch/data/loaders.py"
    assert "docs/DECISIONS/ADR-0004-slot-definition.md" in items


def test_missing_items_reported(handoff, tmp_path):
    (tmp_path / "present.txt").write_text("x", encoding="utf-8")
    (tmp_path / "dir").mkdir()
    missing = handoff.missing(["present.txt", "dir/", "absent.md", "present.txt/"], tmp_path)
    assert missing == ["absent.md", "present.txt/"]


def test_config_hashes_are_stable_and_sorted(hashes, tmp_path):
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "b.yaml").write_text("seed: 1\n", encoding="utf-8")
    (configs / "a.yaml").write_text("seed: 2\n", encoding="utf-8")
    rows = hashes.config_hashes(tmp_path)
    assert [name for name, _ in rows] == ["configs/a.yaml", "configs/b.yaml"]
    assert rows == hashes.config_hashes(tmp_path)
    assert all(len(digest) == 64 for _, digest in rows)


def test_config_hashes_with_no_configs(hashes, tmp_path):
    assert hashes.config_hashes(tmp_path) == []


def test_skill_frontmatter(handoff):
    text = (SCRIPTS.parent / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: phase-closeout\n")
    assert "description:" in text.split("---")[1]
    assert len(text.splitlines()) < 500
    assert Path(SCRIPTS / "check_handoff.py").is_file()
