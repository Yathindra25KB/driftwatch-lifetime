"""The claims audit finds uncovered numbers, unresolved ids and "first" claims."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAIMS = """# ledger
| Claim ID | Statement | Value | Source file | Commit | Tag | Access date |
|---|---|---|---|---|---|---|
| E-01 | a result | 0.91 | reports/tables/x.csv | abc1234 | [measured] | 2026-10-15 |
| E-02 | no commit | 0.5 | reports/tables/y.csv | | [measured] | 2026-10-15 |
"""


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(
        "claims_audit", ROOT / "scripts" / "claims_audit.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["claims_audit"] = module
    spec.loader.exec_module(module)
    return module


def run(tool, tmp_path: Path, text: str):
    md = tmp_path / "doc.md"
    md.write_text(text, encoding="utf-8")
    claims = tmp_path / "CLAIMS.md"
    claims.write_text(CLAIMS, encoding="utf-8")
    return tool.audit([md], claims, root=tmp_path)


def test_a_number_with_a_resolving_claim_passes(tool, tmp_path: Path) -> None:
    rep = run(tool, tmp_path, "A-AUT was 0.91 on BODMAS [E-01].\n")
    assert rep.ok and rep.covered == 1 and not rep.uncovered


def test_a_number_without_a_claim_fails(tool, tmp_path: Path) -> None:
    rep = run(tool, tmp_path, "A-AUT was 0.91 on BODMAS.\n")
    assert not rep.ok and len(rep.uncovered) == 1


def test_an_unknown_claim_id_fails(tool, tmp_path: Path) -> None:
    rep = run(tool, tmp_path, "A-AUT was 0.91 [E-99].\n")
    assert not rep.ok and rep.unresolved[0][1] == "E-99"


def test_a_cited_row_without_a_commit_fails(tool, tmp_path: Path) -> None:
    rep = run(tool, tmp_path, "A gap of 0.5 [E-02].\n")
    assert not rep.ok and rep.incomplete_rows == ["E-02"]


def test_verify_marked_paragraphs_are_pending_not_failures(tool, tmp_path: Path) -> None:
    rep = run(tool, tmp_path, "About 40% of samples were packed [verify].\n")
    assert rep.ok and len(rep.pending) == 1


@pytest.mark.parametrize(
    "text",
    [
        "Years like 2026, dates like 15 Oct 2026, RQ1, C3 and ch07 need no claim.\n",
        "# 3.1 Heading with 12 in it\n",
        "```\nuv run pytest 123\n```\n",
        "Use `--chunk 2/11` to run one chunk.\n",
        "1. First step\n2. Second step\n",
        "See section 3.4 and chapter 6 and Table 2.\n",
    ],
)
def test_things_that_are_not_claims_are_ignored(tool, tmp_path: Path, text: str) -> None:
    assert run(tool, tmp_path, text).ok


@pytest.mark.parametrize(
    "text",
    [
        "This is the first to study label delay.\n",
        "We are the first to combine them.\n",
        "A first-ever result.\n",
    ],
)
def test_first_as_a_contribution_claim_fails(tool, tmp_path: Path, text: str) -> None:
    rep = run(tool, tmp_path, text)
    assert not rep.ok and len(rep.first_claims) == 1


def test_first_slot_or_first_window_is_fine(tool, tmp_path: Path) -> None:
    assert run(tool, tmp_path, "The first evaluation slot and the first window.\n").ok


def test_table_rows_are_one_block(tool, tmp_path: Path) -> None:
    text = "| a | b |\n|---|---|\n| LR | 0.91 [E-01] |\n| LGBM | 0.97 |\n"
    rep = run(tool, tmp_path, text)
    assert rep.ok and rep.covered == 1  # the table is cited as one block


def test_the_real_ledger_parses_and_every_row_has_a_source(tool) -> None:
    rows = tool.parse_claims((ROOT / "docs" / "CLAIMS.md").read_text(encoding="utf-8"))
    assert len(rows) > 60 and "E-01" in rows and "P-08" in rows
    assert all(r["source"] for r in rows.values())
