"""scripts/make_public_history.py: the checks that a filtered history is safe to publish."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("mph", ROOT / "scripts" / "make_public_history.py")
mph = importlib.util.module_from_spec(_spec)
sys.modules["mph"] = mph
_spec.loader.exec_module(mph)

IDENT = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
FAKE_TOKEN = "gh" + "p_" + "a" * 36  # assembled so this file does not itself look like a leak


def run(repo: Path, *args: str) -> None:
    subprocess.run(["git", *IDENT, "-C", str(repo), *args], check=True, capture_output=True)


def make_repo(path: Path, files: dict[str, str], tag: str | None = "prereg-v1") -> Path:
    path.mkdir(parents=True)
    run(path, "init", "-q", "-b", "main")
    for name, text in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    run(path, "add", "-A")
    run(path, "commit", "-q", "-m", "one")
    if tag:
        run(path, "tag", tag)
    return path


@pytest.fixture
def source(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "src", {"README.md": "x", "docs/source/guide.pdf": "course text"})


def test_a_clean_filtered_copy_passes(tmp_path: Path, source: Path) -> None:
    filtered = make_repo(tmp_path / "ok", {"README.md": "x"})
    assert mph.verify(filtered, source, ("docs/source",)) == []


def test_the_dropped_path_still_in_history_is_caught(tmp_path: Path, source: Path) -> None:
    leaky = make_repo(tmp_path / "leaky", {"README.md": "x", "docs/source/guide.pdf": "y"})
    problems = mph.verify(leaky, source, ("docs/source",))
    assert any("still touch" in p for p in problems)
    assert any("still present" in p for p in problems)


def test_a_lost_tag_is_caught(tmp_path: Path, source: Path) -> None:
    untagged = make_repo(tmp_path / "untagged", {"README.md": "x"}, tag=None)
    problems = mph.verify(untagged, source, ("docs/source",))
    assert any("tags lost" in p for p in problems)
    assert any("prereg-v" in p for p in problems)


def test_a_secret_shaped_string_is_caught(tmp_path: Path, source: Path) -> None:
    bad = make_repo(tmp_path / "bad", {"README.md": f"token = {FAKE_TOKEN}"})
    assert any("secret-shaped" in p for p in mph.verify(bad, source, ("docs/source",)))


def test_commit_map_pairs_old_and_new(tmp_path: Path) -> None:
    repo = tmp_path / "m"
    (repo / "filter-repo").mkdir(parents=True)
    old, new, gone = "a" * 40, "b" * 40, "0" * 40
    (repo / "filter-repo" / "commit-map").write_text(
        f"old                                      new\n{old} {new}\n{'c' * 40} {gone}\n",
        encoding="utf-8",
    )
    out = tmp_path / "map.csv"
    assert mph.write_commit_map(repo, out) == 2
    assert out.read_text(encoding="utf-8").splitlines() == ["old,new", f"{old},{new}"]


def test_a_non_empty_output_folder_is_refused(tmp_path: Path) -> None:
    (tmp_path / "keep").write_text("x")
    assert mph.main(["--out", str(tmp_path)]) == 1
