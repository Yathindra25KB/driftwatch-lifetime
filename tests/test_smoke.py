"""Smoke tests: the package imports and follows the guide's package map."""

from __future__ import annotations

import importlib
import pkgutil

import pytest

import driftwatch
from driftwatch import cli

PACKAGE_MAP = {"data", "models", "sim", "conformal", "monitors", "metrics"}


def test_version_is_a_string():
    assert isinstance(driftwatch.__version__, str) and driftwatch.__version__


def test_package_map_matches_guide_section_8():
    found = {m.name for m in pkgutil.iter_modules(driftwatch.__path__)}
    assert found == PACKAGE_MAP | {"cli"}


@pytest.mark.parametrize("name", sorted(PACKAGE_MAP))
def test_subpackages_import(name):
    module = importlib.import_module(f"driftwatch.{name}")
    assert module.__doc__  # each docstring names the phase that fills it


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    assert driftwatch.__version__ in capsys.readouterr().out


def test_cli_without_arguments_succeeds():
    assert cli.main([]) == 0
