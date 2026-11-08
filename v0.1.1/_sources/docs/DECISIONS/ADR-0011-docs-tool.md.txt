# ADR-0011: Documentation site tool

**Status:** ACCEPTED by the researcher on 2026-10-26 (option C, chosen in the Phase 12 plan question round)
**Date:** 2026-10-26
**Deciders:** Yathindra (researcher, decides); Claude Code (engineering lead, proposes)
**Phase:** 12

The Phase 12 prompt names this record `ADR-0008-docs-tool.md`. ADR-0008 was already taken in Phase 6 (the RQ1 comparator and E2 design), and ADR numbers are never reused, so this record is ADR-0011.

## Context
- Phase 12 asks for a documentation site built from `docs/`, a strict build, a link check in CI and versioned deployment. It must be free and hosted on GitHub Pages.
- `docs/` is plain Markdown (CommonMark plus pipe tables) with relative links into `../reports/`, `../report/` and source files. The report chapters live in `report/` and must not be copied, because CLAIMS.md and the claims audit read them where they are.
- The prompt's default is Zensical, with Sphinx and MyST as the fallback, "check the current status of both before deciding".

## Options considered

### Option A: Zensical (prompt default)
- Status (PyPI, 2026-10-26): version 0.0.73, classifier `Development Status :: 3 - Alpha`. It is the successor to Material for MkDocs, by the same team.
- Versioning: the March 2026 Zensical newsletter calls its fork of `mike` "intentionally a stopgap", with native versioning only on the roadmap.
- Pros: modern look; reads `mkdocs.yml`.
- Cons: alpha, so a minor upgrade can break the build. The quarterly dependency refresh would then turn into docs repair. No documented strict mode was found.

### Option B: MkDocs with Material
- Status (PyPI, 2026-10-26): mkdocs-material 9.8.0, classifier `Development Status :: 7 - Inactive`. The maintainers give critical fixes only until 2026-11-05.
- Pros: proven, `--strict`, `mike` versioning.
- Cons: we would adopt a tool in its last week of maintenance.

### Option C: Sphinx with MyST and the Furo theme
- Status (PyPI, 2026-10-26): sphinx 9.2.0 (Production/Stable), myst-parser 5.1.0 (Beta, long-lived), furo 2025.12.19 (Production/Stable), sphinxcontrib-mermaid 2.1.1.
- Strict build: `sphinx-build -W --keep-going` turns every warning, including broken cross-references, into a failure.
- Link check: the built-in `linkcheck` builder.
- Versioning: each version is built into its own folder on the `gh-pages` branch (`latest/` from `main`, `vX.Y.Z/` from tags), with a `versions.json` switcher. A plain git branch, no extra tool.
- Pros: mature; renders the existing Markdown with few changes; `{include}` pulls the report chapters in without copies; autodoc gives an API reference.
- Cons: plainer look; slower builds; a small custom version switcher to maintain.

## Decision (choice)
**Option C: Sphinx + MyST + Furo, strict build (`-W --keep-going`), `linkcheck` in CI, versioned folders on `gh-pages`.**

The reasons are stability over the maintenance horizon (quarterly refreshes for years) and a strict mode that is documented and enforced by the tool. Zensical should be re-evaluated when it leaves alpha and ships native versioning (`docs/ROADMAP.md`).

## Consequences
- New dependency group `docs` in `pyproject.toml`, locked in `uv.lock`. It is not a runtime dependency, so the PyPI package does not grow. Sphinx is held at `>=9.1.1,<9.2`: Sphinx 9.2.0 requires Python 3.13 and this project is pinned to 3.12 (`requires_python` on PyPI, checked 2026-10-26); lift the cap when the project moves to 3.13.
- `docs/conf.py` and `docs/index.md` define the site. Process files (`docs/prompts/`, `docs/source/`) are excluded.
- `.github/workflows/docs.yml` builds strictly on every pull request and runs the link check, also weekly on a schedule. It deploys `latest/` on `main` and `vX.Y.Z/` on tags.
- Revisit when Zensical reaches beta with native versioning, or if Furo stops being maintained.

## Evidence and references
- PyPI JSON API, accessed 2026-10-26: https://pypi.org/pypi/zensical/json, https://pypi.org/pypi/mkdocs-material/json, https://pypi.org/pypi/sphinx/json, https://pypi.org/pypi/myst-parser/json, https://pypi.org/pypi/furo/json
- Zensical Monthly, March 2026 (versioning stopgap), accessed 2026-10-26: https://mail.zensical.org/monthly/2026/03/
- Material for MkDocs maintenance notice (critical fixes until 2026-11-05), reported in the Zensical announcement, accessed 2026-10-26: https://zensical.org/about/roadmap/
- Sphinx `-W` and `--keep-going`: https://www.sphinx-doc.org/en/master/man/sphinx-build.html; `linkcheck` builder: https://www.sphinx-doc.org/en/master/usage/builders/index.html
