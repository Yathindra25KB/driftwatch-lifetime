"""scripts/check_release.py: version agreement, changelog notes and distribution contents."""

from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cr = load_script("check_release")

CHANGELOG = """# Changelog

## [Unreleased]

## [0.2.0] - 2027-01-01

### Added
- thing two

## [0.1.0] - 2026-11-01

### Added
- thing one

[0.2.0]: https://example.invalid/v0.2.0
"""


def project(tmp_path: Path, version: str = "0.2.0", cff_version: str = "0.2.0") -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "x"\nversion = "{version}"\n', encoding="utf-8"
    )
    (tmp_path / "CITATION.cff").write_text(f"cff-version: 1.2.0\nversion: {cff_version}\n", "utf-8")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    return tmp_path


def test_the_repository_itself_agrees() -> None:
    assert cr.check_versions(None) == []


def test_versions_agree_and_tag_matches(tmp_path: Path) -> None:
    root = project(tmp_path)
    assert cr.check_versions("v0.2.0", root) == []


def test_mismatches_are_reported(tmp_path: Path) -> None:
    root = project(tmp_path, version="0.3.0", cff_version="0.2.0")
    problems = cr.check_versions("v0.2.0", root)
    assert any("CITATION.cff" in p for p in problems)
    assert any("no section for 0.3.0" in p for p in problems)
    assert any("tag v0.2.0" in p for p in problems)


def test_changelog_section_stops_at_next_heading_and_link_refs(tmp_path: Path) -> None:
    root = project(tmp_path)
    assert cr.changelog_section("0.2.0", root) == "### Added\n- thing two"
    assert cr.changelog_section("0.1.0", root) == "### Added\n- thing one"
    assert cr.changelog_section("9.9.9", root) is None


def _wheel(path: Path, members: list[str]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for m in members:
            zf.writestr(m, "x")


def _sdist(path: Path, members: list[str]) -> None:
    with tarfile.open(path, "w:gz") as tf:
        for m in members:
            info = tarfile.TarInfo(m)
            info.size = 1
            tf.addfile(info, io.BytesIO(b"x"))


GOOD_WHEEL = [
    "driftwatch/__init__.py",
    "driftwatch/data/loaders.py",  # the data subpackage is code, not data
    "driftwatch/_golden/smoke_table1.csv",
    "driftwatch_lifetime-0.2.0.dist-info/METADATA",
]
GOOD_SDIST = [
    "driftwatch_lifetime-0.2.0/pyproject.toml",
    "driftwatch_lifetime-0.2.0/src/driftwatch/data/slicer.py",
    "driftwatch_lifetime-0.2.0/tests/fixtures/synthetic/bodmas.npz",
]


def test_clean_distribution_passes(tmp_path: Path) -> None:
    _wheel(tmp_path / "x-0.2.0-py3-none-any.whl", GOOD_WHEEL)
    _sdist(tmp_path / "x-0.2.0.tar.gz", GOOD_SDIST)
    assert cr.check_dist(tmp_path) == []


def test_data_results_and_secrets_are_caught(tmp_path: Path) -> None:
    _wheel(tmp_path / "x-0.2.0-py3-none-any.whl", [*GOOD_WHEEL, "driftwatch/cache.parquet"])
    _sdist(
        tmp_path / "x-0.2.0.tar.gz",
        [
            *GOOD_SDIST,
            "driftwatch_lifetime-0.2.0/data/lamda/raw.parquet",
            "driftwatch_lifetime-0.2.0/results/e2/x.csv",
            "driftwatch_lifetime-0.2.0/docs/source/guide.pdf",
            "driftwatch_lifetime-0.2.0/.env",
        ],
    )
    problems = cr.check_dist(tmp_path)
    assert len(problems) == 5, problems


def test_missing_golden_table_is_caught(tmp_path: Path) -> None:
    _wheel(tmp_path / "x-0.2.0-py3-none-any.whl", ["driftwatch/__init__.py"])
    _sdist(tmp_path / "x-0.2.0.tar.gz", GOOD_SDIST)
    assert any("golden" in p for p in cr.check_dist(tmp_path))


def test_notes_cli_prints_the_section(capsys) -> None:
    from_repo = cr.changelog_section(cr.pyproject_version())
    assert cr.main(["--notes", f"v{cr.pyproject_version()}"]) == 0
    assert capsys.readouterr().out.strip() == from_repo


def test_release_candidate_is_checked_against_its_release(tmp_path: Path) -> None:
    root = project(tmp_path, version="0.2.0rc1", cff_version="0.2.0")
    assert cr.release_of("0.2.0rc1") == "0.2.0"
    assert cr.check_versions(None, root) == []
    assert cr.check_versions("v0.2.0", root)  # a final tag never points at a candidate


zd = load_script("zenodo_dry_run")


def test_zenodo_metadata_of_the_repository_is_well_formed() -> None:
    assert zd.check(zd.load()) == []


def test_zenodo_check_catches_bad_metadata() -> None:
    bad = {"title": "x", "upload_type": "dataset", "creators": [{"name": "Given Family"}]}
    bad["related_identifiers"] = [{"identifier": "http://x", "relation": "cites"}]
    problems = zd.check(bad)
    assert any("missing field description" in p for p in problems)
    assert any("upload_type" in p for p in problems)
    assert any("Family, Given" in p for p in problems)
    assert any("relation" in p for p in problems)
    assert any("https" in p for p in problems)
