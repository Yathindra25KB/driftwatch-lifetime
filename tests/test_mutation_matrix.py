"""The full kill matrix: real suites in subprocesses, one mutant each (slow)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.slow
def test_every_mutant_is_killed_by_the_real_suites():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "mutation_check.py"), "--no-report"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
