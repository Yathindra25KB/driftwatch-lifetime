---
name: arxiv-audit
description: Monthly re-audit of arXiv (cs.CR, cs.LG) for new papers on label delay, labelling or analyst budget, and conformal or drift monitoring in malware detection, then triage into docs/related_work_addendum.md. Use it when the researcher asks for the arXiv audit, the related-work refresh or "what is new in the literature", when an "arXiv audit" issue is opened by the monthly workflow, or when a prompt says TASK = arxiv-audit, even if they do not name the skill.
---

# arXiv audit

Keeps `docs/related_work_addendum.md` current. The script finds candidates by keyword; **you read each abstract and decide**. Never write a claim about a paper you have not read, never invent an identifier, and never use the word "first" about this project (CLAUDE.md hard rule 9).

Work on a branch `maint/<YYYY-MM>-arxiv`. Touch `docs/related_work_addendum.md` and `reports/arxiv_audit/` only. Do not edit the report chapters or `paper/references.bib`: list the chapters that should change in the pull request description.

## 1. Collect candidates
```bash
uv run python scripts/arxiv_audit.py
```
It reads `reports/arxiv_audit/state.json` for the last audit date (override with `--since YYYY-MM-DD`; `--no-state` leaves the state file alone), queries the arXiv API for `cs.CR` and `cs.LG`, and writes `reports/arxiv_audit/<date>.md` and `.json`. If the monthly workflow already opened an issue, use the list in it and skip this step. Exit code 2 means arXiv could not be read: report that and stop, do not retry in a loop (the API asks for one request per three seconds).

## 2. Read each candidate
For every row, open `https://arxiv.org/abs/<id>` (WebFetch) and read the abstract. Classify it:

| Class | Meaning |
|---|---|
| **delay** | treats the time a label takes to arrive as a parameter |
| **budget** | fixes or studies the number of labels an analyst can buy |
| **conformal / monitor** | uses conformal p-values, or a drift monitor, as a signal |
| **time-aware** | an evaluation protocol on temporal splits (TESSERACT-like) |
| **not relevant** | keyword match only (say why in a few words) |

A paper can have several classes. "Not in the abstract" is not "no": write exactly that.

## 3. Update the addendum
For each relevant paper, append a row to the table of `docs/related_work_addendum.md` with the same six columns as the existing rows (work and arXiv id with date, what the abstract says, delay, budget, conformal or monitor, position against this study). Add a line above the table naming the audit date, for example `Audit 2026-12-01: 3 added, 9 read and set aside`. Keep every new entry marked **[verify: read in full before citing]**. Descriptions are your paraphrase of the abstract, with the access date.

If a paper combines label delay, a fixed budget and conformal monitoring on malware, say so plainly in the pull request: it changes the positioning sentence and the researcher must decide what to do. Do not change the contribution statement yourself.

## 4. Check and hand over
```bash
uv run python scripts/claims_audit.py     # must still PASS
uv run pytest -q tests/test_arxiv_audit.py
```
Commit with a conventional message (`docs(related-work): arXiv audit YYYY-MM`) and open a pull request listing: the period, how many candidates, how many added, how many set aside, and any chapter that should change. Never merge it yourself.

## Failure handling
- No candidates is a valid result: record "0 candidates" in the pull request and still update `state.json`.
- Duplicates: skip an arXiv id already in the addendum or in `paper/references.bib` (a new version of a known paper is a note on its row, not a new row).
- A candidate you cannot open: list it under "could not be read" in the pull request rather than guessing from its title.
