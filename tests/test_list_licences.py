"""scripts/list_licences.py: reads licences from installed metadata and flags unknown ones."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ll = load_script("list_licences")
# locked only for the emscripten (Pyodide) platform: never installed on Windows or Linux
PLATFORM_ONLY = {"httpx2-jsfetch"}


def test_names_and_requirements_are_normalised() -> None:
    assert ll.norm("Typing_Extensions") == "typing-extensions"
    assert ll.requirement_name("scikit-learn>=1.9.1") == "scikit-learn"
    assert ll.requirement_name("hypothesis[cli]>=6; python_version>'3'") == "hypothesis"


def test_direct_dependencies_come_from_pyproject() -> None:
    runtime, dev = ll.direct_dependencies(ROOT / "pyproject.toml")
    assert {"numpy", "lightgbm", "scikit-learn"} <= runtime
    assert {"pytest", "ruff"} <= dev


def test_every_locked_package_has_a_licence_except_platform_only_ones() -> None:
    table = ll.rows()
    assert len(table) > 30
    unknown = {r["package"] for r in table if r["licence"] == "UNKNOWN"}
    assert unknown <= PLATFORM_ONLY, unknown
    kinds = {r["package"]: r["kind"] for r in table}
    assert kinds["numpy"] == "direct, runtime" and kinds["pytest"] == "direct, development"
    assert "driftwatch-lifetime" not in kinds


def test_no_locked_package_is_gpl_or_agpl() -> None:
    bad = [
        r["package"]
        for r in ll.rows()
        if "GPL" in r["licence"].upper() and "LGPL" not in r["licence"].upper()
    ]
    assert not bad, bad
