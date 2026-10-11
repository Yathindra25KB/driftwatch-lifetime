---
name: phase-closeout
description: Closing ritual for a DriftWatch phase. Runs tests, lint and the guardrail demo, checks that every HANDOFF artifact exists, records config hashes, asks the researcher for the hours spent, writes the docs/PHASES.md entry with evidence and commit hash, and commits. Use it whenever a phase prompt says "run the phase-closeout skill", when the researcher says a phase is finished, wants to wrap up or close a phase, or is ready to open the phase PR or tag phase-NN-done, even if they do not name the skill.
---

# Phase closeout

Every DriftWatch phase ends the same way. A stranger should be able to audit the ledger later: what was built, the evidence that it works, which commit holds it and how many of the researcher's hours it took. Run the steps in order from the repository root. Stop at the first red step and fix the cause; never weaken a test, check or guardrail to get green (CLAUDE.md hard rule 2 and the guardrail rules).

## 1. Identify the phase
Take NN from the branch name (`git rev-parse --abbrev-ref HEAD`, expected `phase-NN-<slug>`) and confirm it against the IN PROGRESS row in `docs/PHASES.md`. If they disagree, ask the researcher which phase is closing.

## 2. Tests, lint, guardrails
```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run python scripts/check_guardrails.py
```
All four must pass. Keep the tail of each output: these are the evidence lines for the ledger.

## 3. HANDOFF artifacts
```bash
uv run python .claude/skills/phase-closeout/scripts/check_handoff.py NN
```
It reads the HANDOFF list of `docs/prompts/phase-NN.md` and reports each item as ok or MISSING. A missing artifact is either created now or explained in the ledger's Notes column ("not produced because …"). It is never silently dropped.

## 4. Config hashes
```bash
uv run python .claude/skills/phase-closeout/scripts/config_hashes.py
```
Paste the table under a `### Phase NN config hashes` heading at the end of `docs/PHASES.md`. Later phases compare these hashes to detect results produced by a config that has since changed.

## 5. Hours
Ask the researcher with AskUserQuestion how many hours this phase took them; offer the planned hours from the ledger as context, not as the answer. Never estimate the number yourself: the hour check (under 5 h/week for four weeks) is a stop rule and depends on real numbers. Also offer to fill this week's row of the weekly hours log.

## 6. Commit the work, then the ledger
1. Commit any remaining phase work with a conventional commit (`feat:`, `fix:`, `docs:`, `test:` …).
2. Note the hash: `git rev-parse --short HEAD`. A ledger entry cannot contain its own commit's hash, so it records this work commit.
3. Update the phase row in `docs/PHASES.md`: Status `DONE`, Evidence (relative links to the reports, reviews and test outputs that prove the acceptance items), Commit (the hash from 2), Hours (from step 5), Notes (deviations, cuts, residual risks). Update any gate row the phase decided only if the researcher made that decision.
4. Commit the ledger: `docs(phases): close phase NN`.

## 7. Hand back to the researcher
Do not push, open the PR or tag; those are the researcher's actions (CLAUDE.md workflow). Print the commands for them:
```bash
git push -u origin phase-NN-<slug>
gh pr create --base main --head phase-NN-<slug> --title "Phase NN: <name>" --body-file <summary>
git tag -a phase-NN-done -m "Phase NN done" <merge-commit>   # after the PR is merged
```
Then give the phase's final report in the format its prompt asks for.
