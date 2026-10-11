"""pytest plugin: apply one slicer mutant to the whole run.

Used only by ``scripts/mutation_check.py`` (``-p mutation_plugin`` with
``DRIFTWATCH_MUTANT=<name>``). Without the variable it does nothing.
"""

from __future__ import annotations

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    name = os.environ.get("DRIFTWATCH_MUTANT")
    if not name:
        return
    from slicer_mutants import MUTANTS

    patch = pytest.MonkeyPatch()
    MUTANTS[name].apply(patch)
    config._driftwatch_mutant_patch = patch  # type: ignore[attr-defined]


def pytest_unconfigure(config: pytest.Config) -> None:
    patch = getattr(config, "_driftwatch_mutant_patch", None)
    if patch is not None:
        patch.undo()
