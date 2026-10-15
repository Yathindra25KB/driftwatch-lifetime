"""`driftwatch reproduce table1`: comparison rules, smoke mode on the fixture, exit codes.

Smoke mode runs the real code path on the committed synthetic fixture; its numbers are
code-behaviour checks and are never evidence.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from driftwatch import cli
from driftwatch.sim import reproduce
from driftwatch.sim.reproduce import compare_tables, reproduce_table1

ROOT = Path(__file__).resolve().parents[1]


def table() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "dataset": ["bodmas", "bodmas"],
            "model": ["lr", "lgbm"],
            "variant": ["rolling", "rolling"],
            "ratio": [0.1, 0.1],
            "n_seeds": [5, 5],
            "n_windows": [6, 6],
            "a_aut_mean": [0.9122, 0.9769],
            "gap": [0.0354, 0.0057],
            "fit_seconds_median": [1.3, 3.5],
            "sanity_band": ["[verify]", "[verify]"],
        }
    )


def test_identical_tables_match() -> None:
    cmp = compare_tables(table(), table())
    assert cmp.ok and cmp.n_rows == 2 and cmp.max_abs_diff == 0.0


def test_a_difference_inside_the_tolerance_matches_and_outside_does_not() -> None:
    new = table()
    new.loc[0, "a_aut_mean"] += 0.0015
    assert compare_tables(new, table(), tolerance=0.002).ok
    new.loc[0, "a_aut_mean"] += 0.001
    cmp = compare_tables(new, table(), tolerance=0.002)
    assert not cmp.ok and any("a_aut_mean" in p for p in cmp.problems)
    assert cmp.worst[0]["column"] == "a_aut_mean"


def test_comparator_columns_use_the_looser_tolerance() -> None:
    a, b = table(), table()
    a["f1_random_split"] = [0.9475, 0.9826]
    b["f1_random_split"] = [0.9475 + 0.01, 0.9826 - 0.015]
    assert compare_tables(a, b).ok  # inside 0.02
    b.loc[0, "f1_random_split"] += 0.02
    cmp = compare_tables(a, b)
    assert not cmp.ok and cmp.max_comparator_diff > 0.02 and cmp.max_abs_diff == 0.0


def test_counts_must_be_exactly_equal() -> None:
    new = table()
    new.loc[1, "n_windows"] = 7
    cmp = compare_tables(new, table(), tolerance=1.0)
    assert not cmp.ok and any("count" in p for p in cmp.problems)


def test_timing_and_placeholder_columns_are_ignored() -> None:
    new = table()
    new["fit_seconds_median"] = [90.0, 91.0]
    new["sanity_band"] = ["x", "y"]
    assert compare_tables(new, table()).ok


def test_different_row_sets_are_a_mismatch_not_a_crash() -> None:
    cmp = compare_tables(table().iloc[:1], table())
    assert not cmp.ok and "row sets differ" in cmp.problems[0]


def test_missing_columns_are_reported() -> None:
    cmp = compare_tables(table().drop(columns=["gap"]), table())
    assert not cmp.ok and any("columns missing" in p for p in cmp.problems)


@pytest.mark.slow
def test_smoke_reproduction_matches_the_committed_golden(tmp_path: Path) -> None:
    report = reproduce_table1(
        repo_root=ROOT, smoke=True, out_dir=tmp_path / "out", work_dir=tmp_path / "work",
        require_clean=False,
    )  # fmt: skip
    assert report["verdict"] == "MATCH" and report["evidence"] is False
    assert report["rows_compared"] == 2
    written = json.loads(next((tmp_path / "out").glob("table1_smoke_*.json")).read_text())
    assert written["config_hash"] == report["config_hash"] and written["total_wall_s"] >= 0
    assert "lock_sha256" in written and "packages" in written


@pytest.mark.slow
def test_a_changed_reference_is_reported_as_a_mismatch(tmp_path: Path) -> None:
    ref = tmp_path / "golden.csv"
    shutil.copy(ROOT / "tests" / "golden" / "table1_smoke.csv", ref)
    df = pd.read_csv(ref)
    df.loc[df["model"] == "lr", "a_aut_mean"] += 0.05
    df.to_csv(ref, index=False)
    report = reproduce_table1(
        repo_root=ROOT, smoke=True, out_dir=tmp_path / "out", work_dir=tmp_path / "work",
        require_clean=False, stored_table=ref,
    )  # fmt: skip
    assert report["verdict"] == "MISMATCH" and report["problems"]
    assert report["max_abs_diff"] == pytest.approx(0.05, abs=1e-6)


@pytest.mark.slow
def test_cli_exit_codes(tmp_path: Path, monkeypatch, capsys) -> None:
    args = ["reproduce", "table1", "--smoke", "--allow-dirty", "--out", str(tmp_path / "o"),
            "--work-dir", str(tmp_path / "w")]  # fmt: skip
    assert cli.main(args) == 0
    assert "MATCH" in capsys.readouterr().out

    from driftwatch.data.download import ManualDownloadRequired

    def need_manual(*a, **k):
        raise ManualDownloadRequired("download BODMAS by hand: see docs/data_cards/bodmas.md")

    monkeypatch.setattr(reproduce, "_ensure_bodmas", need_manual)
    assert cli.main(["reproduce", "table1", "--allow-dirty", "--out", str(tmp_path / "o2")]) == 3
    assert "by hand" in capsys.readouterr().err
