"""The built wheel and sdist hold the package and nothing else (slow: runs `uv build`)."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "check_release", ROOT / "scripts" / "check_release.py"
)
cr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cr)

pytestmark = pytest.mark.slow


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not on PATH")
def test_built_distribution_passes_the_release_check(tmp_path: Path) -> None:
    subprocess.run(
        ["uv", "build", "--out-dir", str(tmp_path)], cwd=ROOT, check=True, capture_output=True
    )
    assert cr.check_dist(tmp_path) == []
    wheel = next(tmp_path.glob("*.whl"))
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    assert "driftwatch/_golden/smoke_table1.csv" in names
    assert not any(
        n.startswith(("tests/", "scripts/", "docs/", "data/", "results/")) for n in names
    )
