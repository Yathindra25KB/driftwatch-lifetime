"""Sphinx configuration for the DriftWatch documentation site (ADR-0011).

The source directory is the repository root, so the relative links between docs/, report/,
reports/, src/ and scripts/ resolve inside one tree. Build from the root:

    uv run sphinx-build -c docs -W --keep-going -b html . docs/_build/html
    uv run sphinx-build -c docs -b linkcheck . docs/_build/linkcheck
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

project = "DriftWatch"
author = "Yathindra K B"
copyright = "2026, Yathindra K B (MIT licence)"
release = _project["version"]
version = release

root_doc = "docs/index"
extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
]
source_suffix = {".md": "markdown", ".rst": "restructuredtext"}

# Only the documentation is part of the site. Data, results, caches, tests, process files and
# the course documents (docs/source, not redistributed) are never read.
exclude_patterns = [
    "_build",
    "**/_build",
    ".*",
    ".*/**",
    "data",
    "results",
    "tests",
    "configs",
    "paper",
    "src/**/*.md",
    "docs/source",
    "docs/prompts",
    "docs/prereg/*.tmp",
    "node_modules",
    "AGENTS.md",
    "CLAUDE.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "reports/arxiv_audit",
    "reports/maintenance",
    "reports/reproduction",
    "reports/figures",
    "reports/tables",
]

myst_enable_extensions = ["colon_fence", "deflist", "attrs_block"]
myst_heading_anchors = 3
myst_fence_as_directive = ["mermaid"]
# claim ids such as [E-30] are plain text, not references
suppress_warnings = ["toc.not_included", "myst.header"]

# API reference
autodoc_member_order = "bysource"
autodoc_mock_imports = []
napoleon_google_docstring = False
napoleon_numpy_docstring = False

# Link check: be polite and tolerate slow publishers; the pages below block scripted clients
linkcheck_timeout = 20
linkcheck_retries = 2
linkcheck_workers = 4
linkcheck_ignore = [
    r"https://github\.com/Yathindra25KB/driftwatch-lifetime/.*",  # public after release
    r"https://yathindra25kb\.github\.io/.*",  # live after the first docs deploy
    r"https://pypi\.org/project/driftwatch-lifetime/.*",  # exists after the first upload
    r"https://test\.pypi\.org/project/driftwatch-lifetime/.*",
    r"https://doi\.org/10\.5281/zenodo\..*",  # minted at release
]

html_theme = "furo"
html_title = f"DriftWatch {release}"
html_static_path: list[str] = []
html_theme_options = {
    "source_repository": "https://github.com/Yathindra25KB/driftwatch-lifetime/",
    "source_branch": "main",
    "source_directory": "",
}
