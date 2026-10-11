"""Project-memory tests: CLAUDE.md stays short and the scoped rules and agents are well formed."""

from __future__ import annotations

import re

import pytest
from conftest import ROOT

CLAUDE_MD = ROOT / "CLAUDE.md"
RULES = sorted((ROOT / ".claude" / "rules").glob("*.md"))
AGENTS = sorted((ROOT / ".claude" / "agents").glob("*.md"))


def frontmatter(text: str) -> str:
    assert text.startswith("---\n"), "missing YAML frontmatter"
    return text.split("---\n", 2)[1]


def test_claude_md_under_200_lines():
    lines = CLAUDE_MD.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 200, f"CLAUDE.md has {len(lines)} lines; the limit is 200"


def test_claude_md_has_the_twelve_hard_rules():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    numbers = [int(n) for n in re.findall(r"^(\d+)\. ", text, flags=re.M)]
    assert numbers == list(range(1, 13))


def test_claude_md_points_to_protocol_and_ledgers():
    text = CLAUDE_MD.read_text(encoding="utf-8")
    for target in ("docs/PROTOCOL.md", "docs/PREREG.md", "docs/CLAIMS.md", "docs/PHASES.md"):
        assert target in text
        assert (ROOT / target).is_file()


@pytest.mark.parametrize("rule", RULES, ids=lambda p: p.name)
def test_rules_are_path_scoped(rule):
    fm = frontmatter(rule.read_text(encoding="utf-8"))
    assert re.search(r"^paths:\n(  - \"[^\"]+\"\n)+", fm, flags=re.M), rule.name


@pytest.mark.parametrize("agent", AGENTS, ids=lambda p: p.name)
def test_agents_are_read_only(agent):
    fm = frontmatter(agent.read_text(encoding="utf-8"))
    tools = re.search(r"^tools: (.+)$", fm, flags=re.M).group(1)
    assert {t.strip() for t in tools.split(",")} == {"Read", "Grep", "Glob", "Bash"}
    denied = re.search(r"^disallowedTools: (.+)$", fm, flags=re.M).group(1)
    assert {"Write", "Edit", "NotebookEdit", "PowerShell"} <= {t.strip() for t in denied.split(",")}
    assert "--reviewer-bash" in fm


def test_both_reviewers_exist():
    assert {a.stem for a in AGENTS} == {"leakage-reviewer", "stats-reviewer"}
