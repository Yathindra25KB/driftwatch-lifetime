"""The full kill matrix: real suites in subprocesses, one mutant each (slow)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_no_suite_the_mutation_harness_runs_is_marked_slow():
    """The harness runs its suites with ``-m "not slow"``; a slow-marked suite is silently skipped.

    A speed-up once marked ``test_slicer_review_fixes.py`` slow, and the mutant that only its
    metamorphic test kills (``public_order_stratified``) survived until the kill matrix ran.
    """
    from conftest import SLOW_MODULES

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import mutation_check
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    suites = {Path(s).name for s in mutation_check.SUITES}
    assert not suites & SLOW_MODULES, sorted(suites & SLOW_MODULES)


@pytest.mark.slow
def test_every_mutant_is_killed_by_the_real_suites():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "mutation_check.py"), "--no-report"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
