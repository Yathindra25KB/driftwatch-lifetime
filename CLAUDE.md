# DriftWatch: global rules for Claude Code

Keep this file under 200 lines (test enforced). Details live in docs/PROTOCOL.md, docs/PREREG.md and docs/DECISIONS/. Folder-specific rules live in .claude/rules/.

## What this project is
Open-source study of malware-detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring, under one time-aware protocol (TESSERACT C1-C3; AUT and A-AUT). Data: LAMDA (Android), BODMAS (Windows PE), optional EMBER2024. Feature files only. The researcher is Yathindra (final-year B.Tech CSE, VISTAS); Claude Code is the engineering lead. Machine: Windows 11, 8 GB RAM (7.2 GB usable), no GPU.

Single sources of truth: docs/PROTOCOL.md (every protocol constant), docs/PREREG.md (hypotheses), docs/DECISIONS/ (ADRs), docs/PHASES.md (status, hours), docs/CLAIMS.md (number -> file -> commit). The current phase prompt is docs/prompts/phase-NN.md.

## Hard rules (never break; ask the researcher if one seems to block progress)
1. Never download, run, open, decompile or redistribute malware samples or binaries. Feature files only.
2. C1, C2 and C3 are assertions that raise. Never weaken, skip or delete a constraint test to get green.
3. Label delay lives only in sim/queue.py. Nothing reads a label before its release slot.
4. True labels are for queue release and metric scoring only. Selectors, policies and monitors never see held-back labels.
5. Fit scalers, thresholds, feature selectors and calibration sets on the current training window only.
6. One YAML config per run. Log config hash, seeds and package versions; store per-slot predictions.
7. Never edit locked files: docs/PREREG.md after a prereg-vN tag; locked golden files. Use an addendum or an ADR.
8. No number enters a README, report or paper unless it is in docs/CLAIMS.md with file and commit. Toy and sandbox numbers are never evidence.
9. Never write "first" as a contribution claim. State what was measured. Tag facts [verified] / [verify] / [estimate].
10. Do not tune a monitor until it wins. Report negative and flat results as they are.
11. Respect licences. Commit no dataset content except the synthetic fixture (under 1 MB).
12. No evasion tooling and no adversarial-example generation.

## Stop rules (decided in advance; do not argue around them)
- G1, end of week 4 (Sun 8 Nov 2026): no sensible time-aware baseline on one dataset -> fix the slicer; no simulator work.
- G2, end of week 8 (Sun 6 Dec 2026): simulator not end to end on one dataset -> cut to one dataset and one model.
- G3, end of week 14 (Sun 17 Jan 2027): Tier 1 results and core chapters missing -> cancel Tier 2 and 3; finish the report.
- G4, end of week 19 (Sun 21 Feb 2027): Tier 2 incomplete -> label the rest future work; no Tier 3.
- Hour check: under 5 h per week on average for four weeks -> single dataset.
- A fit over 60 s on this laptop: shrink the grid (delay 2, budget 0.5%, windows, seeds on non-headline cells) before shrinking the claim.
- Gates are decided by the researcher from the gate card and the evidence file, never by Claude.

## Commands (Git Bash or PowerShell; same commands)
- `uv sync --frozen`: install exactly the locked environment
- `uv run pytest -q`: fast tests (slow marker excluded); `uv run pytest -m slow`: slow tests
- `uv run ruff check . && uv run ruff format .`: lint and format
- `uv run python scripts/check_guardrails.py`: prove every guardrail fires (temp repo, never the real one)
- `uv run driftwatch --version`; later phases add `data verify`, `run <config>`, `grid <config> --chunk i/n`, `reproduce table1`

## Conventions
Python 3.12, type hints, src layout (src/driftwatch/), pathlib, logging (no print in library code), explicit seeds passed as parameters, no global state, small functions, tests next to behaviour, conventional commits. One config file per run; the config hash covers the config, code version and lock file.

## Licence and ethics
Code is MIT. LAMDA (MIT), BODMAS (BSD-2), EMBER2024 (Apache-2.0) keep their licences; AndroZoo and SOREL-20M are not used. data/ and results/ are never committed. The repository describes how detectors decay, not how to evade them (docs/ETHICS.md).

## Workflow
- Plan mode first for anything touching more than three files. Show the plan; wait for approval.
- Ask (AskUserQuestion) only for decisions that are the researcher's: scope, slots, windows, pre-registrations, cuts, gates, ADR approval, publishing. Discover everything else yourself.
- One branch per phase (`phase-NN-<slug>`), small conventional commits. Never push, publish, create remote resources or change repository visibility without asking first.
- Never weaken, skip or delete a guardrail or test to get green. If one looks wrong, write an ADR and ask.
- Independent review: leakage-reviewer for data, sim and conformal code; stats-reviewer for analysis and claims.
- Finish each phase with the phase-closeout skill: tests, lint, PHASES.md entry (status, evidence, commit, hours the researcher reports), config hashes, HANDOFF check, commit.

## Guardrails you will meet (do not work around them)
- The PreToolUse guard (.claude/hooks/guard.py) blocks: edits that change docs/PREREG.md or a tagged addendum after its prereg tag; edits to committed tests/golden/ files; force pushes; `git add` of data/ or results/; recursive deletes outside temp folders; downloads from hosts outside its allowlist. A block is a rule, not a bug: stop and ask.
- The Stop gate runs the fast tests when you try to finish; red tests mean keep working.
- Permissions deny reading secrets and editing data/** and docs/source/**; pushes, network tools, publishing and edits to .claude/settings.json or .claude/hooks/ ask the researcher.
- Two shells exist on this machine (Bash = Git Bash, and PowerShell); the same rules apply to both.

## Context hygiene
- Never load data/ or results/ dumps into context. Use head, counts and summaries.
- Write long outputs to files and summarise them.
- After /compact or in a new session, re-read docs/PHASES.md and the current phase prompt in docs/prompts/.
