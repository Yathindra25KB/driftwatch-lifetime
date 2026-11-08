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
    # hidden folders by name (a blanket ".*/**" would also match "./x", the name Sphinx gives
    # the top of docs/_static while copying it, and silently drop every static file)
    ".git",
    ".github",
    ".venv",
    ".cache",
    ".claude",
    ".claude-state",
    ".omc",
    ".agents",
    ".codex",
    ".playwright-mcp",
    ".pytest-tmp",
    ".pytest_cache",
    ".ruff_cache",
    ".hypothesis",
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
    "CODE_OF_CONDUCT.md",
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
    # Zenodo's DOI links are checked by hand when a version is released (CLAIMS E-83)
    r"https://doi\.org/10\.5281/zenodo\..*",
    # GitHub answers scripted requests for this repository's own pages (file pages, badges,
    # compare and release pages) with 500, 504 or a timeout, even from its own runners; the Docs
    # runs of 8 Nov 2026 failed three times on it. The links point at the repository itself and
    # the file links were checked against the tree (CLAIMS E-84), so they are not fetched.
    r"https://github\.com/Yathindra25KB/driftwatch-lifetime/.*",
    # a release candidate page is not kept stable
    r"https://test\.pypi\.org/project/driftwatch-lifetime/.*",
]

html_theme = "furo"
html_title = f"DriftWatch {release}"
html_static_path = ["_static"]
html_css_files = ["print.css"]
# The site's front page is docs/index (root_doc), so the built folder has no index.html of its
# own. This copies a redirect to the root of every version folder, so that .../latest/ and
# .../v0.1.0/ (the URLs in CITATION.cff and pyproject.toml) open the documentation.
html_extra_path = ["_extra"]
html_theme_options = {
    "source_repository": "https://github.com/Yathindra25KB/driftwatch-lifetime/",
    "source_branch": "main",
    "source_directory": "",
}
