# Maintenance playbook

Recurring tasks that keep the project correct and citable after release. Each task has a cadence, a prompt to paste into Claude Code (re-entry mode `maintain`, defined in the Phase 12 prompt), the commands it runs, what a good result looks like, and where the output goes.

**Rules that apply to every task**

- Work on a branch named `maint/<YYYY-MM>-<task>` and open a pull request. Never push to `main`, tag, publish to PyPI or touch Zenodo without the researcher's explicit go ([releasing](RELEASING.md)).
- A maintenance change must not move a reported number. If a refresh changes any table, figure or claim, stop: that is a `CHANGE_REQUEST` with an addendum, not maintenance.
- Never edit `docs/PREREG.md`, a tagged addendum or a locked golden file (hard rule 7 in `CLAUDE.md`).
- Save the output of the run under `reports/maintenance/<YYYY-MM>-<task>.md` and cite it in the pull request.

| Task | Cadence | Automation | Time |
|---|---|---|---|
| [arXiv audit](#arxiv-audit) | monthly, on the 1st | GitHub Actions opens an issue; the skill triages | 30 min |
| [Dependency refresh](#dependency-refresh) | quarterly (Jan, Apr, Jul, Oct) | manual | 1 to 2 h |
| [Dataset-version watch](#dataset-version-watch) | quarterly, and before a release | `scripts/dataset_watch.py` | 15 min |
| [Release check](#release-check) | before every release | `scripts/check_release.py` and CI | 30 min |
| [Issue triage](#issue-triage) | weekly while issues are open | manual | 15 min |
| [Release](RELEASING.md) | when there is something to ship | `release.yml` | 1 h |

## arXiv audit

**Purpose.** Find new papers on label delay, labelling budgets or conformal and drift monitoring for malware detection, so the related-work addendum and chapter 5 do not go stale.

**Automation.** `.github/workflows/arxiv-audit.yml` runs `scripts/arxiv_audit.py` on the 1st of each month and opens an issue titled `arXiv audit YYYY-MM` that lists the candidates. A calendar reminder is in `docs/maintenance/arxiv-audit.ics` for months where the workflow did not run.

**Prompt**

> PHASE 12 | MODE: maintain | TASK = arxiv-audit. Run the `arxiv-audit` skill for the period since the last audit. Open a branch `maint/<YYYY-MM>-arxiv` and a pull request that updates `docs/related_work_addendum.md` only. Do not edit the report chapters; list any chapter that should change in the pull request description.

**Commands (by hand)**

```bash
uv run python scripts/arxiv_audit.py            # writes reports/arxiv_audit/<date>.md and .json
```

**Good result.** A list of candidates, each classified as relevant to delay, budget, conformal or monitor, or not relevant; relevant ones added to the addendum with their arXiv id, date read and one sentence, marked `[verify]` until read in full. The skill never invents a reference: an entry needs an arXiv id that resolves (`scripts/check_bib.py` rules apply before anything goes into `paper/references.bib`).

## Dependency refresh

**Purpose.** Pick up security fixes and keep the environment installable, without changing a result.

**Prompt**

> PHASE 12 | MODE: maintain | TASK = deps-refresh. On a branch `maint/<YYYY-MM>-deps`: run `uv lock --upgrade`, then the full test suite, the slow suite, ruff, the guardrail demo, the smoke experiment, the licence lister and the table rebuilds. Report every package whose version changed, every licence that changed, and whether any rebuilt table differs from the committed one. Do not merge; open a pull request.

**Commands**

```bash
uv lock --upgrade
uv sync --frozen
uv run pytest -q && uv run pytest -q -m slow
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_guardrails.py
uv run driftwatch smoke
uv run python scripts/list_licences.py          # new GPL or UNKNOWN entries must be read by a person
uv run python scripts/make_tables.py --results results/e2 --e1-root results/e1
uv run python scripts/make_e3.py --results results/e3
uv run python scripts/make_e4.py --results results/e4
git status --short reports/                     # must be empty: no number moved
```

**Good result.** Tests green, `git status reports/` empty, no new unknown or GPL-family licence. The new `uv.lock` hash goes in `docs/PHASES.md` and `docs/licence_audit.md` is regenerated. **If a table moved,** do not merge: revert the lock and open an issue describing which package changed the number.

**Notes.** `sphinx` is capped below 9.2 while the project requires Python 3.12 (ADR-0011); lift the cap only together with `requires-python`. A change to `requires-python` is an ADR.

## Dataset-version watch

**Purpose.** Know when LAMDA or BODMAS publishes a new version. A new version never replaces the studied one silently.

```bash
uv run python scripts/dataset_watch.py          # exit 0: unchanged; 1: changed; 2: could not read
```

LAMDA is compared by Hugging Face revision against `data/manifest.json`; BODMAS by the newest commit of its project repository against the download time.

**Prompt (only if the watch reports a change)**

> PHASE 12 | MODE: maintain | TASK = dataset-update. Read the upstream change notes for the changed dataset and summarise them with links. Do not download or rebuild anything. List what a rerun would need (new manifest, rebuilt caches, the grids that would be rerun and their cell time from `docs/GRID.md`) and which registered analyses a change in the data would make invalid. Open an issue with the summary.

Rerunning on a new version is a `CHANGE_REQUEST`: a new data card, a new manifest, a new pre-registration addendum before any run, and a minor version bump with a CHANGELOG entry under **Results**.

## Release check

Run before every release, and whenever a release workflow fails.

```bash
uv run python scripts/check_release.py                 # pyproject, CITATION.cff and CHANGELOG agree
uv build && uv run python scripts/check_release.py --dist dist
uvx twine check --strict dist/*
uv run python scripts/zenodo_dry_run.py --check        # .zenodo.json is well formed
uv run python scripts/claims_audit.py                  # every number has a ledger row
uv run python scripts/check_bib.py                     # every reference resolves
uv run --group docs sphinx-build -c docs -W --keep-going -b html . _site
uv run --group docs sphinx-build -c docs -b linkcheck . _linkcheck
```

**Prompt**

> PHASE 12 | MODE: maintain | TASK = release-check. Run the release-check commands in `docs/MAINTENANCE.md`, fill the preconditions checklist of `docs/RELEASING.md` with evidence for each item, and report anything red. Do not tag or publish.

## Issue triage

Labels: `bug`, `reproduction-failure`, `dataset-update`, `related-work`, `question`, `wontfix`. Templates are in `.github/ISSUE_TEMPLATE/`.

| Report | Action |
|---|---|
| `reproduction-failure` | Ask for the exit code, OS, `driftwatch --version` and the report in `reports/reproduction/`. Exit 3 is the dataset host refusing the download: point to the manual path in the data card |
| `bug` in a constraint (C1 to C3), the label queue or sealed labels | Highest priority: reproduce with a failing test first. A fix never weakens a test |
| A request for **evasion or attack tooling**, adversarial-example generation, or running or distributing malware | Decline, citing [the ethics statement](ETHICS.md); close |
| A request that a result changes | Explain that results change only through a new pre-registration; invite a proposal |
| `related-work` | Add to the next arXiv audit |

**Prompt**

> PHASE 12 | MODE: maintain | TASK = issue-triage. List open issues, propose a label and a one-paragraph response for each, and flag any that ask for something the ethics statement excludes. Post nothing; show me the drafts.
