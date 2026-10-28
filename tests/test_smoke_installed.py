"""The smoke experiment runs without a source checkout (what an installed wheel sees)."""

from __future__ import annotations

import filecmp
import json
from pathlib import Path

import pytest

from driftwatch.cli import main
from driftwatch.sim import reproduce

ROOT = Path(__file__).resolve().parents[1]


def test_packaged_golden_equals_the_committed_golden() -> None:
    """The wheel ships a copy of the locked golden table; the copies must not drift apart."""
    committed = ROOT / reproduce.SMOKE_GOLDEN
    assert filecmp.cmp(committed, reproduce.PACKAGED_GOLDEN, shallow=False)


def test_a_repository_is_a_checkout_and_an_empty_folder_is_not(tmp_path: Path) -> None:
    assert reproduce.is_checkout(ROOT)
    assert not reproduce.is_checkout(tmp_path)


def test_smoke_regenerates_the_fixture_and_matches_without_a_checkout(tmp_path: Path) -> None:
    report = reproduce.reproduce_table1(
        repo_root=tmp_path / "no-checkout-here",
        out_dir=tmp_path / "out",
        work_dir=tmp_path / "work",
        smoke=True,
    )
    assert report["verdict"] == "MATCH"
    assert report["rows_compared"] == 2
    assert (tmp_path / "work" / "fixture" / "raw").is_dir()
    assert any("regenerated" in n for n in report["notes"])
    assert report["reference"] == str(reproduce.PACKAGED_GOLDEN)
    assert report["evidence"] is False


def test_full_reproduction_needs_a_checkout(tmp_path: Path) -> None:
    with pytest.raises(reproduce.ReproductionError, match="source checkout"):
        reproduce.reproduce_table1(repo_root=tmp_path, out_dir=tmp_path / "out", smoke=False)


def test_smoke_command_exits_zero_and_writes_a_report(tmp_path: Path, capsys) -> None:
    code = main(["smoke", "--out", str(tmp_path / "out"), "--work-dir", str(tmp_path / "work")])
    assert code == 0
    assert capsys.readouterr().out.startswith("MATCH")
    report = json.loads(next((tmp_path / "out").glob("table1_smoke_*.json")).read_text("utf-8"))
    assert report["verdict"] == "MATCH"


def test_lock_hash_falls_back_only_outside_a_checkout(tmp_path: Path) -> None:
    from driftwatch.sim.config import lock_sha256

    assert len(lock_sha256(tmp_path)) == 64  # installed package: no uv.lock, no pyproject
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="source checkout"):
        lock_sha256(tmp_path)  # a checkout that lost its lock file is an error
    (tmp_path / "uv.lock").write_bytes(b"a\r\nb\r\n")
    assert lock_sha256(tmp_path) == lock_sha256(tmp_path)
