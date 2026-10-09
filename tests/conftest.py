"""Shared fixtures: the hook modules under .claude/hooks and small temporary git repos."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from hypothesis import settings

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"

# Derandomised in CI so a property-test failure reproduces exactly.
settings.register_profile("ci", derandomize=True, deadline=None)
settings.register_profile("dev", deadline=None)
settings.load_profile("ci")

GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid"]
GIT += ["-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", "-c", "core.autocrlf=false"]


def load_hook(name: str) -> ModuleType:
    path = HOOKS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"hook_{name}", path)
    assert spec is not None and spec.loader is not None, path
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    out = subprocess.run([*GIT, "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return out.stdout


def make_repo(path: Path, files: dict[str, str], tags: tuple[str, ...] = ()) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    for rel, text in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode("utf-8"))
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "init")
    for tag in tags:
        git(path, "tag", tag)
    return path


@pytest.fixture(scope="session")
def guard() -> ModuleType:
    return load_hook("guard")


PREREG_TEXT = "# PREREG\n\nRQ1 locked text\n"


@pytest.fixture(scope="session")
def locked_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Repo with docs/PREREG.md and addendum-v2 committed and tagged prereg-v1, prereg-v2."""
    files = {
        "docs/PREREG.md": PREREG_TEXT,
        "docs/prereg/addendum-v2.md": "addendum v2\n",
        "tests/golden/expected.csv": "a,b\n1,2\n",
        "src/x.py": "x = 1\n",
    }
    return make_repo(tmp_path_factory.mktemp("locked"), files, tags=("prereg-v1", "prereg-v2"))


@pytest.fixture(scope="session")
def unlocked_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Repo with docs/PREREG.md committed but no prereg tag."""
    return make_repo(tmp_path_factory.mktemp("unlocked"), {"docs/PREREG.md": PREREG_TEXT})


@pytest.fixture(scope="session")
def data_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Repo whose .gitignore is missing, with untracked files under data/ and results/."""
    repo = make_repo(tmp_path_factory.mktemp("data"), {"src/x.py": "x = 1\n"})
    for rel in ("data/raw.bin", "data/manifest.json", "results/r.csv", "src/y.py"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("content\n", encoding="utf-8")
    return repo


@pytest.fixture(scope="session")
def ignored_data_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Repo whose .gitignore ignores data/ (except the manifest) and results/."""
    gitignore = "/data/*\n!/data/manifest.json\n/results/\n"
    repo = make_repo(tmp_path_factory.mktemp("ignored"), {".gitignore": gitignore})
    for rel in ("data/raw.bin", "results/r.csv", "src/y.py"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text("content\n", encoding="utf-8")
    return repo
