PHASE 1 | Foundations and governance | MODE: build | CHANGE_REQUEST: none | REVISION: 1.2 (10 Oct 2026)

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am Yathindra, a final-year B.Tech CSE student at VISTAS; you are the engineering lead and I am the researcher. Scope: Tier 1 + Tier 2 in full, Tier 3 optional. Hardware: 8 GB RAM laptop (7.2 GB usable; revision 1.2 corrects the earlier 16 GB). Where a source document assumes more memory, this line wins: list each such place in docs/PHASES.md. Free tools only. No malware is ever executed, opened or redistributed; feature files only. Global rules will live in CLAUDE.md, which you create in this phase.

## MISSION
Stand up the foundation every later phase depends on: a reproducible Python project, a guardrail layer that makes the research rules mechanically hard to break (even for you), and the governance documents. No data and no science code in this phase. This phase is the one place where a mistake silently corrupts all eleven later phases, so correctness beats speed. Budget: about 8 hours of my attention (6 supervising, 2 writing).

## HOW I WANT YOU TO WORK
- You are in plan mode. Until I approve the plan, only read, search, run read-only commands and ask me questions. Edit nothing.
- Your plan must contain: (a) what you found in pre-flight; (b) every file you will create, grouped by deliverable; (c) the order of work; (d) which skills, subagents and connectors you will use for which step; (e) the evidence you will show for each acceptance item; (f) risks and the open questions you still need me to answer; (g) an honest estimate of my hours. Reject your own plan if it skips an acceptance item or a stop rule.
- Ask me questions with AskUserQuestion (details below). Do not guess answers that are mine. Do not ask what you can discover yourself.
- Work on a branch `phase-01-foundations`. Small conventional commits. Never push, never create a remote repository, never change repository visibility without asking me first.

## DISCOVER YOUR TOOLS BEFORE PLANNING (silent, then say what you will use)
1. Skills and plugins: list what is installed (ListSkills / `/skills`, ListPlugins / `/plugin`). Use a listed skill instead of improvising when one fits. Expected useful ones, if present: skill-creator (for authoring the phase-closeout skill and the two subagent definitions), engineering:architecture (ADR format), engineering:documentation (README, ETHICS, data-handling wording), engineering:testing-strategy (guardrail and hook tests), engineering:code-review (final review of the diff). If a skill is not installed, do the step by hand and tell me which skill would have helped. Use SearchSkills / SuggestSkills only if a gap blocks the work.
2. Subagents: use `claude-code-guide` to answer every Claude Code syntax question from the current official docs (list below); use `Explore` for repo-state reconnaissance; use a fresh `general-purpose` agent for the independent adversarial review at the end. Do not spawn agents for work you can do inline.
3. Connectors: check what is connected (ListConnectors / `/mcp`). If a GitHub connector or `gh` is authenticated, use it for repository, branch, CI-run and Actions-status work after I approve creating anything. If none is available, give me exact manual commands instead. Do not connect or use anything unrelated (no deployment, database or design connectors in this phase).
4. Web: use WebFetch/WebSearch for official docs and for package-name availability checks. Bash network use stays limited to package installs.

## PRE-FLIGHT (read-only; report findings at the top of your plan)
1. Confirm these exist, else STOP and tell me which earlier step is missing: docs/source/DriftWatch_Build_Guide_v2.pdf, docs/source/DriftWatch_Implementation_Plan.pdf, docs/source/DriftWatch_Phase_Prompts.md. Read: the guide's sections 3, 6 and 8 (protocol constants, constraints, repository layout) and the plan's Section 5 (operating model), Section 7 (gates) and Appendices A to E. Do not edit anything in docs/source/.
2. Environment: detect OS and shell (WSL2 vs Windows-native matters for hooks), git version, whether this folder is already a git repo and its remote, Python, uv (version), gh, Node (if needed), free disk space, CPU cores and RAM, `claude --version`. Do not install anything yet.
3. Claude Code facts to validate from current official docs (via claude-code-guide, with the doc URL and date for each; never rely on memory, the plan's Appendix B is only a sketch):
   - settings file locations and precedence (project vs local vs user); exact permission-rule syntax for allow, ask, deny (Read, Edit, Bash patterns, path globs, whether a deny on Edit also covers Write and MultiEdit)
   - hook events and fields: PreToolUse, PostToolUse, Stop, SessionStart with `compact` matcher; the JSON schema delivered on stdin (tool_name, tool_input, `stop_hook_active`, cwd, transcript path); exit-code semantics (which codes block, where stderr goes); the `command` field and how paths and quoting work on my OS; timeouts
   - project memory: how CLAUDE.md is loaded, `.claude/rules/*.md` with `paths:` frontmatter, any size or line guidance
   - subagent file format (`.claude/agents/*.md` frontmatter: name, description, tools, model) and how to make one read-only
   - skill file format (`.claude/skills/<name>/SKILL.md` frontmatter and supporting files)
   - how plan mode is entered, how to resume sessions, how `/compact` and SessionStart interact
4. Package name: check the PyPI JSON endpoint (https://pypi.org/pypi/<name>/json; 404 means free) and TestPyPI for `driftwatch` and four alternatives you propose that describe the project (for example a suffix such as -ml or -lifetime). Report which are free. Also note any trademark-like conflicts you notice.
5. Look at my existing files in the repo folder (if any) so you do not overwrite them.

## QUESTIONS TO ASK ME (AskUserQuestion; maximum four per call, recommended option first)
Round 1, right after pre-flight and before you finalise the plan:
1. Operating system and shell (offer what you detected as the recommended option; WSL2 vs Windows-native vs macOS vs Linux).
2. Repository visibility (default recommendation: private until Gate G3, public by Phase 12) and whether I want you to create the GitHub repository now, later, or I will do it myself.
3. Code licence for ADR-0002 (MIT recommended; Apache-2.0 alternative), with a one-line trade-off each.
4. Session strategy for my Claude plan limits (one long session with /compact, or split into three sittings along the order of work below).
Then, in plain text (not multiple choice), ask for my GitHub username and the repository name I want.
Round 2, after you have the pre-flight facts:
5. PyPI distribution name for ADR-0003, offering only names you verified as free.
6. VISTAS rules I know of: capstone deadline, report template (Word or LaTeX), page rules, AI-assistance disclosure policy, whether a demo is expected. Record the answers (or "unknown, to verify") in docs/ETHICS.md and docs/PHASES.md; do not invent them. If the deadline is earlier than the end of week 24 (Sun 28 Mar 2027), say that Tier 3 and Phase 10 get removed.
7. My realistic weekly hours across placement drives and exams (plan assumes 8.5; under 5 for four weeks triggers the single-dataset rule).
8. Whether to enforce branch protection and required CI on main once the repository exists.
If any answer changes your plan, say how before asking me to approve it. Ask no further questions unless a stop rule or an irreversible action demands it.

## DELIVERABLES (outcomes, not recipes)
1. **Project skeleton.** uv-managed project pinned to Python 3.12, committed uv.lock, src layout `src/driftwatch/` whose package map follows guide section 8 (data, models, sim, conformal, monitors, metrics, cli) as empty importable packages, plus configs/, tests/, scripts/, docs/, reports/, report/, paper/, data/ (git-ignored except manifest). Tooling: ruff (lint and format), pytest (with a `slow` marker excluded by default), hypothesis, pre-commit. A proper .gitignore (data/, results/, caches, secrets, env files). Free tools only; no frameworks or services I did not ask for.
2. **CI** (GitHub Actions): lint, format check and fast tests on every push and PR; Linux required, Windows smoke job; uses `uv sync --frozen`; no secrets, no data, no network beyond package installs; runs scripts/check_guardrails.py.
3. **CLAUDE.md under 200 lines** (aim for about 90) with global rules only, built from Appendix A of the plan and adapted to my Claude Code version: pointer to docs/PROTOCOL.md; the 12 hard rules; stop rules G1 to G4, the hour check and the 60-second fit rule; test, lint and run commands; licence and ethics rules; config-per-run and seed discipline; claim tagging ([verified] / [verify] / [estimate]); "never write first as a contribution claim"; plan-mode-first and ask-only-what-is-mine workflow; the phase-closeout ritual; context hygiene. Add path-scoped rules under `.claude/rules/` (for example sim/ delay and sealed-label rules, data/ leakage rules, report/ and paper/ claims-ledger rules, configs/ hash rules) using the validated `paths:` syntax.
4. **Guardrail layer in .claude/**:
   - settings.json permissions: deny reading secrets and editing raw data; ask before network tools, `git push`, publishing commands; allow the test, lint, driftwatch and read-only git commands. Syntax validated against the docs, not the sketch.
   - Four cross-platform Python hooks (never bash-only; run the way my OS needs; measure and report the per-call latency of invoking them):
     (a) PreToolUse path and command guard: reads the tool call JSON on stdin and exits 2 with a reason on stderr to block: edits to docs/PREREG.md once any `prereg-v*` tag exists and the file differs from the tagged blob; edits to locked golden files; `git push --force` and its variants (`-f`, `--force-with-lease`, `+branch` refspecs); `git add` of data/ or results/; recursive deletes outside temp folders; downloads from hosts outside an allowlist. Decide and document what happens if the guard itself crashes (a crash exits 1, which does not block, so catch exceptions and choose fail-closed for the protected categories). Document residual bypass risks honestly (for example indirect writes through scripts) in ADR-0001.
     (b) PostToolUse formatter: ruff format and ruff check --fix on the changed Python file; never fails the tool call.
     (c) Stop gate: if `stop_hook_active` is true exit 0 (no loops); else run the fast tests; red means a short failure summary on stderr and exit 2 so you keep working; green means exit 0; treat "no tests collected" as green with a note; cap the runtime.
     (d) SessionStart(compact) re-injection: after a compaction print the hard rules, the current phase and the PHASES.md status.
   - Two read-only subagents: `leakage-reviewer` (C1 to C3, delay rule, sealed labels, scaler and threshold scope, calibration contamination, window and gap handling; returns file, line, failure scenario, severity) and `stats-reviewer` (window-first bootstrap, multiple comparisons, pre-registered vs exploratory contrasts, effect sizes, every number traceable to docs/CLAIMS.md). Tools limited to read, grep, glob and the test command.
   - One skill, `phase-closeout`: runs tests and lint, updates docs/PHASES.md (status, evidence links, commit hash, hours), records config hashes, checks every artifact in the phase's HANDOFF list exists, commits. Use skill-creator if installed.
5. **Governance documents**:
   - docs/PROTOCOL.md: single source of truth for every protocol constant, copied from guide section 6 value for value. List any difference or ambiguity you find between the guide and this prompt; do not silently resolve one.
   - docs/PREREG.md: RQ1 to RQ5 with hypothesis, primary metric, contrasts, analysis and decision rule, tag target, following plan Appendix D; status UNLOCKED; header explaining the lock-by-tag mechanism.
   - docs/DECISIONS/: ADR template (context, options, choice, consequences, status PROPOSED/ACCEPTED), ADR-0001 tooling and guardrail design (including the validated Claude Code facts with doc links and access dates, and the residual-risk list), ADR-0002 code licence, ADR-0003 PyPI package name (with the availability evidence).
   - docs/PHASES.md ledger with all 12 phases and the gates (G1 to G4, Tier 1 results, Tier 3 go/no-go, release): status, evidence links, commit, hours, notes; plus a weekly hours log table. docs/CLAIMS.md ledger (claim id, statement, value, source file, commit, tag, access date), initially empty with the rules at the top. docs/ETHICS.md (feature files only; describes how detectors decay, not how to evade them; licence and data-handling stance; VISTAS AI-assistance disclosure status). LICENSE, CITATION.cff stub (valid against the schema; validate it), README stub (what DriftWatch is and is not; status: pre-release).
   - docs/prompts/phase-01.md = this prompt verbatim (it supersedes the Phase 1 text inside DriftWatch_Phase_Prompts.md); docs/prompts/phase-02.md to phase-12.md split from DriftWatch_Phase_Prompts.md unchanged, with one exception: in phase-02.md, replace the sentence "Peak memory must stay under 6 GB (record the measured peak) because I have a 16 GB laptop." with "I have an 8 GB laptop (7.2 GB usable). Before building, measure free memory and propose a peak-memory cap for me to approve, then record the measured peak against it." Record this edit in docs/PHASES.md.
   - Low priority, only if the hours allow: report/ch01_introduction.md skeleton and paper/references.bib seeded only with references whose identifiers you can verify by fetching them; list the rest as [verify] in a TODO, never invent an entry.
6. **scripts/check_guardrails.py**: runs entirely in a temporary copy or temporary git repo (never mutating the real repo), prints a pass/fail table, exits non-zero on any failure, runs on Linux and Windows, and runs in CI. It demonstrates: locked-file edit blocked after a temporary `prereg-v1` tag; force-push variants blocked; `git add data/` blocked; formatter ran; Stop gate refuses while a deliberately failing test exists and does not loop on `stop_hook_active`; settings and hook files parse and match the validated schema.
7. **Tests**: a fast smoke test (package imports and package map), unit tests for the guard's decisions on synthetic hook JSON (including malformed input), and a test that CLAUDE.md stays under 200 lines.

## ORDER OF WORK (your plan should follow it)
A. Pre-flight and questions, then plan approval. B. Skeleton, lock file, tooling, CI definition. C. Governance docs and ADRs (ADR-0001 draft early, finish last). D. CLAUDE.md and rules. E. Hooks, settings, subagents, skill (install the hooks last so they do not obstruct their own construction). F. check_guardrails.py and tests. G. Independent adversarial review (below). H. Fixes, then phase-closeout.

## INDEPENDENT REVIEW (required, before closeout)
Spawn a fresh general-purpose subagent that has not seen this session. Give it the repo and one job: try to break the guardrails in a temporary copy. Suggested attacks: `sed -i`, `cp`, `mv`, `tee` and `python -c` writes to a locked PREREG after a tag; `git push origin +main`, `--force-with-lease`; `git add -A` when data/ exists; Write vs Edit vs MultiEdit paths; malformed JSON on stdin; a missing tag; path traversal such as `docs/../docs/PREREG.md`; Windows-style separators if I use Windows. Save its findings to docs/reviews/guardrail-review.md, fix what is fixable, and list what remains as documented residual risk in ADR-0001. Also run engineering:code-review (if installed) on the full diff.

## CONSTRAINTS
- Validate every Claude Code setting, hook field and permission-rule syntax against current official documentation (with URL and access date in ADR-0001) before writing it.
- Everything must work on my operating system; hooks are Python. If a cross-platform hook cannot be made reliable, stop and ask me.
- No dataset downloads, no model, simulator or science code, no network use other than package installs, official documentation and package-name checks.
- Never weaken, skip or delete a guardrail or test to get green; if one looks wrong, write an ADR and ask me.
- No invented facts, references, versions or doc claims; tag uncertain items [verify].
- Do not edit docs/source/. Do not push, publish or create remote resources without my explicit approval. No secrets anywhere.
- Keep it small: no extra frameworks, no template generators, no services.

## ACCEPTANCE (show evidence for each: pasted command output, not statements)
- From a clean clone: `uv sync --frozen && uv run pytest -q && uv run ruff check . && uv run ruff format --check .` passes locally; the CI workflow is valid and, if a remote exists with my approval, green on Linux and Windows.
- `uv run python scripts/check_guardrails.py` shows every scenario passing, including: locked-file edit blocked, force-push blocked, formatter ran, Stop gate refuses while a test fails and does not loop.
- CLAUDE.md has fewer than 200 lines; `/memory` lists it and the rules files (I will check).
- docs/PROTOCOL.md matches guide section 6 exactly; differences listed.
- docs/PHASES.md records Phase 1 as done with the commit hash; ADR-0001 to 0003 exist; ADR-0003 cites availability evidence; docs/reviews/guardrail-review.md exists with every finding resolved or recorded as residual risk.
- Hook latency is measured and reported; any hook slower than about one second is justified or optimised.

## STOP RULES
- A required docs/source file is missing: stop, name it.
- The current Claude Code docs contradict the plan's Appendix B: follow the docs, record the deviation in ADR-0001, tell me.
- A hook cannot be made reliable on my OS: stop and ask.
- The estimate exceeds about 10 hours of my attention: tell me which deliverable to cut (candidates in order: references.bib seeding, ch01 skeleton, Windows CI job).

## RE-ENTRY
- update: apply CHANGE_REQUEST (a new rule, hook, tool or Python bump). Update CLAUDE.md or the relevant ADR, rerun the acceptance checks and check_guardrails.py, record it in PHASES.md.
- maintain: in a branch run `uv lock --upgrade`, rerun CI and check_guardrails.py, summarise changed packages, re-validate hook and settings syntax against the current docs, never merge on red.

## HANDOFF
Before you stop: run the phase-closeout skill (this phase creates it, so run its checklist by hand the first time: tests, lint, ledger, commit); update docs/PHASES.md with status, evidence links, commit hash and the hours I report (ask me for the number); confirm these artifacts exist or explain why not:
- pyproject.toml, uv.lock, .gitignore
- CLAUDE.md, .claude/settings.json, .claude/hooks/, .claude/rules/
- .claude/agents/leakage-reviewer.md, .claude/agents/stats-reviewer.md
- .claude/skills/phase-closeout/SKILL.md
- .github/workflows/ci.yml
- docs/PROTOCOL.md, docs/PREREG.md, docs/DECISIONS/ (ADR template, 0001, 0002, 0003)
- docs/PHASES.md, docs/CLAIMS.md, docs/ETHICS.md, docs/prompts/phase-01.md to phase-12.md
- docs/reviews/guardrail-review.md
- scripts/check_guardrails.py, tests/
- README.md, LICENSE, CITATION.cff
Then give me a final report of at most 15 lines: what was built, evidence summary, deviations from this prompt, residual risks, open questions, next step (Phase 2 prerequisites: disk space, start the LAMDA download early), and the commands to open the PR and tag `phase-01-done` for me to run.
