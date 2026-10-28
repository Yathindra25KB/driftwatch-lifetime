# Maintenance playbook, first end-to-end run (27 Oct 2026)

The three tasks of `docs/MAINTENANCE.md` that Phase 12 asks to see run once: the arXiv audit, the dependency refresh and the reproduction check. Run on branch `maint/2026-10-first-run`, by Claude Code at the researcher's request. Nothing was merged or published by this run.

## 1. arXiv audit

- **Command:** `uv run python scripts/arxiv_audit.py --since 2026-09-01`, then the `arxiv-audit` skill (read each candidate abstract, classify, update the addendum).
- **Result:** 49 keyword candidates in cs.CR and cs.LG from 2026-09-01 to 2026-10-27 (`reports/arxiv_audit/2026-10-27.md`, `.json`). Five recorded in `docs/related_work_addendum.md` (an Android drift paper, a temporal-split Windows PE paper, a delayed-label streams paper, and two intrusion-detection neighbours), three adjacent ones set aside, 41 unrelated (biomedicine, robotics, aerospace and language-model papers that matched "conformal" or "time series").
- **What it showed about the filter:** the keyword filter is loose by design; about nine in ten candidates were irrelevant, so the triage step cannot be skipped. The combination check found no abstract that pairs label delay, a fixed analyst budget and conformal drift monitoring for malware. This is a statement about this month's candidates, not about the literature.
- **Not changed:** report chapters. The addendum names the chapters that may need a change for the researcher to decide.

## 2. Reproduction check (full Table 1, fresh data)

- **Command:** `uv run driftwatch reproduce table1 --out <scratch> --work-dir <scratch>` on a clean tracked tree at commit `d183423`.
- **What was fresh:** no BODMAS data existed under `data/reproduce`; the command downloaded it from the authors' Google Drive folder and built the cache. The three raw files were compared with the hashes in the committed manifest and were byte for byte equal.
- **Result:** `MATCH`: 8 rows compared, largest absolute difference 0.000000 against a tolerance of 0.002 for the time-aware columns. The random-split comparator columns differ by at most 0.0052, inside their looser documented tolerance of 0.02 (their draw is keyed by a digest of the data manifest and differs after a rebuild; see `docs/CLAIMS.md` E-24). Run 1,103 s, total 1,187 s; peak memory 1.48 GiB against the 1.5 GiB cap. Platform Windows 11 on the development laptop, so this is the same machine as every other run, not a different one.
- **What this does not show:** reproduction on a machine that has never seen the repository. That check is the `clean-room` workflow on fresh GitHub runners, which needs the public repository.

## 3. Dependency refresh

- **Command:** `uv lock --upgrade`, then the commands of the playbook on the upgraded environment (`uv sync --frozen`).
- **What changed (21 packages):** certifi 2026.7.22 to 2026.10.23, distlib 0.4.3 to 0.4.4, filelock 4.0.12 to 4.2.4, fonttools 4.66.1 to 4.67.0, httpcore2 and httpx2 2.13.1 to 2.16.0, huggingface-hub 2.2.0 to 2.3.0, hypothesis 6.168.5 to 6.170.12, narwhals 2.27.1 to 2.28.0, numpy 2.5.3 to 2.5.4, pandas 3.0.6 to 3.1.0, pillow 12.3.0 to 13.0.0, platformdirs 4.12.4 to 4.13.6, pluggy 1.6.0 to 1.7.0, pre-commit 4.6.2 to 4.7.0, python-dateutil 2.9.0.post0 to 3.0.0, python-discovery 1.6.1 to 1.6.5, ruff 0.16.10 to 0.17.3, soupsieve 3.0 to 3.0.4 (3.0 was a yanked release), truststore 0.10.4 to 0.10.5, virtualenv 21.14.6 to 21.15.0. Five of them are in the runtime set: numpy, pandas and huggingface-hub directly; pillow and fonttools through matplotlib.
- **Checks, all on the upgraded environment:**

| Check | Result |
|---|---|
| fast suite | 1,056 passed |
| slow suite | 142 passed in 373 s, one pandas deprecation warning in `tests/test_runner_e0.py` (`rsuffix` in `DataFrame.join`; a test-code warning, to fix before pandas 4) |
| `ruff check` and `ruff format --check` | pass with ruff 0.17.3 (no source change needed) |
| guardrail demonstration | 45 of 45 |
| `driftwatch smoke` | `MATCH`, 2 rows, max difference 0.000000 |
| smoke result tables against the baseline taken before the upgrade | 40 prediction rows, 4 slot rows, 2 window rows; every probability, decision and label identical; only `config_hash`, `window_id` and the timing column differ, as expected |
| tables rebuilt from the stored E1 to E4 predictions (`make_tables.py`, `make_e3.py`, `make_e4.py`) | all exit 0; **`git status reports/` shows no modified file: the E2, E3 and E4 tables and figures these scripts write equal the committed copies.** Not rerun: the E0 and E1 tables and the label-influence table (other scripts) |
| `check_e4_vs_e3.py` | exit 0 |
| licence lister | no GPL-family or new unknown licence; two label spellings changed (pandas now says BSD-3-Clause); python-dateutil 3.0.0's licence files read again and unchanged in structure; `docs/licence_audit.md` table regenerated |

- **One test needed a fix, found by this refresh:** `tests/test_fixture_regenerates.py` compared the bytes of the committed parquet fixture, but a parquet file stores the writer's pandas version in its metadata, so pandas 3.1.0 changed the bytes of every file while every value stayed the same. The test now compares the table contents without that metadata (npz files were already compared by content). This changes how a test compares, not what it protects: a change of any value still fails it, and the fixture files are unchanged.
- **Decision for the researcher:** the playbook says to open a pull request and not to merge. The upgrade moved no number, so it is a candidate to merge. It also changes the lock hash, which a release records; whether to take it before the first release or after is the researcher's call.
