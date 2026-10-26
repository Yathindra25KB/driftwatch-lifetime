"""scripts/docs_versions.py: the version index of the documentation site."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "docs_versions", ROOT / "scripts" / "docs_versions.py"
)
dv = importlib.util.module_from_spec(_spec)
sys.modules["docs_versions"] = dv
_spec.loader.exec_module(dv)


def site(tmp_path: Path, *names: str) -> Path:
    for n in names:
        (tmp_path / n).mkdir()
    (tmp_path / "stray.txt").write_text("x")
    (tmp_path / "v0.1").mkdir()  # not a release folder
    return tmp_path


def test_latest_first_then_releases_newest_first(tmp_path: Path) -> None:
    root = site(tmp_path, "latest", "v0.1.0", "v0.10.0", "v0.2.1")
    assert [v["name"] for v in dv.versions(root)] == ["latest", "v0.10.0", "v0.2.1", "v0.1.0"]


def test_index_files_are_written(tmp_path: Path) -> None:
    root = site(tmp_path, "latest", "v0.1.0")
    assert dv.main([str(root)]) == 0
    assert [v["name"] for v in json.loads((root / "versions.json").read_text())] == [
        "latest",
        "v0.1.0",
    ]
    assert "url=latest/" in (root / "index.html").read_text()
    assert 'href="v0.1.0/"' in (root / "versions.html").read_text()
    assert (root / ".nojekyll").exists()


def test_no_latest_yet(tmp_path: Path) -> None:
    root = site(tmp_path, "v0.1.0")
    assert [v["name"] for v in dv.versions(root)] == ["v0.1.0"]


def test_bad_usage_exits_2(tmp_path: Path) -> None:
    assert dv.main([]) == 2
    assert dv.main([str(tmp_path / "missing")]) == 2
