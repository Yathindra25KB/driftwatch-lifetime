"""Repository invariants, checked by the Stop gate on every finish.

Defense in depth behind the PreToolUse guard: however a change was made (a
shell trick, a script, a git history operation), these tests turn it red.
- docs/PREREG.md equals its blob at the highest prereg-v* tag; tagged addenda equal theirs;
- a LOCKED status line names tags that exist;
- committed tests/golden/ files are unchanged against HEAD;
- nothing under data/ (except data/manifest.json) or results/ is tracked.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from conftest import PREREG_TEXT, ROOT, git

TAG_RE = re.compile(r"prereg-v(\d+)")


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    # decode as UTF-8 like the working-tree read below; the Windows default code page turned
    # the first non-ASCII registered file (addendum v3) into a false "differs from its tag"
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8"
    )


def prereg_drift(repo: Path) -> list[str]:
    tags = [
        t for t in run_git(repo, "tag", "--list", "prereg-v*").stdout.split() if TAG_RE.fullmatch(t)
    ]
    problems = []
    if tags:
        highest = max(tags, key=lambda t: int(TAG_RE.fullmatch(t).group(1)))
        locked = {"docs/PREREG.md": highest}
        locked |= {f"docs/prereg/addendum-v{TAG_RE.fullmatch(t).group(1)}.md": t for t in tags}
        for rel, tag in locked.items():
            blob = run_git(repo, "show", f"{tag}:{rel}")
            if blob.returncode != 0:
                continue  # file not part of that tag (e.g. no addendum for prereg-v1)
            path = repo / rel
            current = path.read_text(encoding="utf-8") if path.is_file() else None
            if current is None or current.replace("\r\n", "\n") != blob.stdout.replace(
                "\r\n", "\n"
            ):
                problems.append(f"{rel} differs from {tag}")
    prereg = repo / "docs" / "PREREG.md"
    if prereg.is_file():
        status = next(
            (ln for ln in prereg.read_text(encoding="utf-8").splitlines() if "Status:" in ln), ""
        )
        if "LOCKED" in status and "UNLOCKED" not in status:
            for tag in TAG_RE.findall(status):
                if f"prereg-v{tag}" not in tags:
                    problems.append(f"status names prereg-v{tag} but the tag does not exist")
    return problems


def golden_drift(repo: Path) -> list[str]:
    out = run_git(repo, "diff", "--name-only", "HEAD", "--", "tests/golden").stdout
    return out.split()


def tracked_data(repo: Path) -> list[str]:
    out = run_git(repo, "ls-files", "--", "data", "results").stdout.split()
    return [p for p in out if p != "data/manifest.json"]


needs_git = pytest.mark.skipif(not (ROOT / ".git").exists(), reason="not a git checkout")


@needs_git
def test_prereg_matches_its_tags():
    assert prereg_drift(ROOT) == []


@needs_git
def test_committed_golden_files_unchanged():
    assert golden_drift(ROOT) == []


@needs_git
def test_no_data_or_results_tracked():
    assert tracked_data(ROOT) == []


# --- the checks above can fail ------------------------------------------------------------


def test_prereg_drift_detected(tmp_path):
    from conftest import make_repo

    repo = make_repo(tmp_path / "r", {"docs/PREREG.md": PREREG_TEXT}, tags=("prereg-v1",))
    assert prereg_drift(repo) == []
    (repo / "docs" / "PREREG.md").write_text(PREREG_TEXT + "edited by a script\n", encoding="utf-8")
    assert prereg_drift(repo) == ["docs/PREREG.md differs from prereg-v1"]


def test_deleted_lock_tag_detected(tmp_path):
    from conftest import make_repo

    text = "**Status: LOCKED** (prereg-v1)\n"
    repo = make_repo(tmp_path / "r", {"docs/PREREG.md": text}, tags=("prereg-v1",))
    assert prereg_drift(repo) == []
    git(repo, "tag", "-d", "prereg-v1")
    assert prereg_drift(repo) == ["status names prereg-v1 but the tag does not exist"]


def test_golden_and_data_drift_detected(tmp_path):
    from conftest import make_repo

    repo = make_repo(tmp_path / "r", {"tests/golden/a.csv": "1\n", "data/x.bin": "x\n"})
    (repo / "tests" / "golden" / "a.csv").write_text("2\n", encoding="utf-8")
    assert golden_drift(repo) == ["tests/golden/a.csv"]
    assert tracked_data(repo) == ["data/x.bin"]
