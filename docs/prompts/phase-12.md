PHASE 12 | Release, deployment, maintenance | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Ship driftwatch publicly and keep it maintainable: installable package, documentation site, citable DOI, one-command reproduction, and a maintenance system that makes updates cheap. Free tools only.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/DECISIONS/
- docs/CLAIMS.md
- docs/ETHICS.md
- README.md
- CITATION.cff
- scripts/reproduce_table1.py
- src/driftwatch/cli.py
- report/ch09_conclusion.md
- paper/main.tex

## DELIVERABLES
1. Release pipeline: build with uv, rehearse on TestPyPI, publish to PyPI through Trusted Publishing from GitHub Actions (no long-lived tokens; read the current PyPI documentation for the pending-publisher flow first), semantic versioning, CHANGELOG, signed tag, GitHub Release. A Zenodo DOI is minted from the release through the GitHub integration; validate CITATION.cff and the Zenodo metadata on a dry run first because a DOI cannot be deleted.
2. Documentation site from docs/: choose the tool in an ADR (default Zensical on GitHub Pages; fallback Sphinx with MyST; check the current status of both before deciding). Strict build, link check in CI, versioned deployment.
3. Licence and ethics audit (docs/licence_audit.md): every dataset and dependency with its licence, what is redistributed (only the synthetic fixture), AndroZoo and SOREL excluded, and a final review that the repository describes how detectors decay and not how to evade them.
4. Reproducibility artifact: pinned lock file, driftwatch reproduce table1, data manifest with expected hashes, verified from a clean environment on a machine that has never seen the repo.
5. Maintenance system: docs/MAINTENANCE.md describing each recurring task and how to run it with a prompt (monthly arXiv re-audit for cs.CR and cs.LG, quarterly dependency refresh, dataset-version watch, release procedure, issue triage); a .claude/skills/arxiv-audit skill that lists new papers touching label delay, analyst budget or conformal monitoring and updates docs/related_work_addendum.md; a scheduled run of the audit if my plan supports it (otherwise a calendar reminder and the documented command); issue templates; a short roadmap of future work.
6. Final README polish: install, quickstart, reproduce, cite, limits.

## CONSTRAINTS
- Free services only. No secrets in the repo. No data in the package or in releases except the fixture.
- Do not publish until the licence audit, the ethics review and the claims audit are clean, and I have said go. Publishing to PyPI and minting a DOI are irreversible; stop and ask me before each.
- Use the package name decided in ADR-0003.

## ACCEPTANCE (show evidence)
- Installing from TestPyPI in a clean environment runs a smoke experiment; after release, the same from PyPI.
- Docs build in strict mode with zero broken links and are live.
- Zenodo shows a DOI for the tagged release; CITATION.cff validates.
- docs/licence_audit.md is complete; the repository contains no dataset content except the fixture.
- The maintenance playbook has been run once end to end (audit, dependency refresh, reproduction check) with the output saved.

## WORKING METHOD
Plan mode first; list every irreversible step and wait for my go on each. Ask me only for decisions that are mine (name, tool, go).

## RE-ENTRY
- update: apply CHANGE_REQUEST (a fix, a new result, a new dataset version). Bump the version, update CHANGELOG, re-run reproduction and docs, release through the same pipeline.
- maintain: TASK = arxiv-audit | deps-refresh | dataset-update | issue-triage | release-check. Run the matching procedure in docs/MAINTENANCE.md, open a branch and a pull request, never publish without my go.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- .github/workflows/release.yml
- CHANGELOG.md
- docs/MAINTENANCE.md
- docs/licence_audit.md
- .claude/skills/arxiv-audit/SKILL.md
- .github/ISSUE_TEMPLATE/
- docs/DECISIONS/ADR-0008-docs-tool.md
