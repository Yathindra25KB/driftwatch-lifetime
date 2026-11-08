# DriftWatch: project context (for a new Claude session)

Written 8 Nov 2026 after release 0.1.1. Paste this whole file into a Claude project as context. It is a summary: the single sources of truth are `docs/PROTOCOL.md` (every constant), `docs/PREREG.md` and `docs/prereg/` (hypotheses), `docs/DECISIONS/` (ADRs), `docs/CLAIMS.md` (every number, with file and commit), `docs/PHASES.md` (status). If this file and those disagree, they win. Facts here are marked [measured] or [verified] only where `docs/CLAIMS.md` says so.

## 1. What the project is

DriftWatch is an open-source, pre-registered study of how long a malware detector stays useful as malware changes. One time-aware protocol (TESSERACT constraints C1 to C3, reported with AUT and A-AUT) is applied to pre-extracted feature files of LAMDA (Android) and BODMAS (Windows PE). It asks how label delay, a fixed analyst budget, conformal sample selection and drift monitors change a detector's lifetime. No malware is ever downloaded, executed, opened or redistributed; only feature files are used.

The contribution statement, used word for word everywhere: "We study malware detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring in a single time-aware protocol, reported with A-AUT, on Android and Windows PE data." The project never claims to be "first".

Researcher: Yathindra K B (final-year B.Tech CSE, VISTAS; yathindrakb25@gmail.com, kept in `CITATION.cff` and in commits on the researcher's decision). Claude Code acts as the engineering lead; the researcher decides scope, pre-registrations, gates, releases and anything irreversible. The report and the paper are drafts written with Claude Code; no person has yet read them line by line (chapter 8, section 8.7).

## 2. Where everything lives

| What | Where |
|---|---|
| Public repository (canonical) | https://github.com/Yathindra25KB/driftwatch-lifetime (MIT) |
| Private archive of the development history | https://github.com/Yathindra25KB/Driftwatch- (contains `docs/source/` course documents, never public; commit hashes cited in older ledger rows are from this history, mapped in `docs/commit_map.csv`) |
| Documentation site | https://yathindra25kb.github.io/driftwatch-lifetime/latest/ (versioned folders) |
| PyPI | `driftwatch-lifetime` 0.1.0 (29 Oct 2026) and 0.1.1 (8 Nov 2026); import name `driftwatch` (ADR-0003) |
| Zenodo | version 0.1.1 DOI 10.5281/zenodo.24050865; concept DOI 10.5281/zenodo.24050864 (always the latest). 0.1.0 has no DOI |
| Local working copies (researcher's laptop) | `E:\DriftWatch` (development clone, private origin), `E:\DriftWatch-pub` (clone of the public repo) |
| Local data (never committed) | `data/` (only `data/manifest.json` is tracked), `results/` (about 7 GiB of stored per-slot predictions, hashed in `docs/predictions_manifest.csv`, archived privately) |

Evidence screenshots of the live PyPI and Zenodo pages: `docs/evidence/`. Release record: CLAIMS E-80 to E-83.

## 3. Repository map

- `src/driftwatch/`: `data/` (download, cache, slicer, C1 to C3, canary), `models/` (LR, LightGBM), `metrics/` (AUT, A-AUT, bootstrap, grid tables), `sim/` (queue, pool, selectors, policies, runner, grids E2 to E4, reproduce), `conformal/` (Mondrian p-values, nonconformity, recalibration), `monitors/` (KS, MMD, domain classifier, p-uniformity behind one alarm interface), `cli.py`, `_golden/` (smoke golden table).
- `configs/`: one YAML per run (E0, E1, E2, E3, E4 per dataset, and the label-influence diagnostics `li_*`). The run hash covers config, code version and lock file.
- `tests/`: about 1,200 tests (1,056 fast, 142 slow); constraint, queue, spy, mutation and regression tests are guardrails and are never weakened.
- `scripts/`: table and figure builders (`make_tables.py`, `make_e3.py`, `make_e4.py`, `make_figures.py`), audits (`claims_audit.py`, `check_bib.py`, `check_guardrails.py`, `check_release.py`, `audit_results.py`, `list_licences.py`), release tools (`make_public_history.py`, `zenodo_dry_run.py`, `export_architecture_pdf.py`), `reproduce_table1.py`, `arxiv_audit.py`.
- `docs/`: PROTOCOL, PREREG (locked after tag `prereg-v1`), `prereg/` addenda v2 and v3 (locked after their tags), `DECISIONS/` ADR-0001 to ADR-0011, CLAIMS, PHASES, ROADMAP, RELEASING, MAINTENANCE, ETHICS, GRID, `licence_audit.md`, `data_cards/`, `architecture/` (sections with diagrams and captures), `reviews/` (leakage, stats and guardrail reviews), `prompts/` (the 12 phase prompts), `submission_checklist.md`, `evidence/`.
- `report/`: chapters 0 to 9 (about 22,000 words). `reports/`: gate evidence G1 to G5, tables, figures, audits. `paper/`: `main.tex` and `main.pdf` (7 pages, IEEE conference template), `references.bib` (36 entries, all resolved by `check_bib.py`), `REFERENCES_TODO.md`.
- `.claude/`: project rules, hooks (a PreToolUse guard and others), skills (`phase-closeout`, `arxiv-audit`) and two reviewer agents (`leakage-reviewer`, `stats-reviewer`). `.github/`: five workflows (ci, docs, release, clean-room, arxiv-audit), issue forms.

## 4. Protocol constants (docs/PROTOCOL.md has the full list)

Slots: a month for LAMDA, two weeks for BODMAS (ADR-0004). Window geometry and size gate: ADR-0005 (LAMDA training 4 slots, evaluation 12, stride 3; BODMAS training 3, evaluation 6, stride 2; minimum 50 malware per slot). C1 no training on the future; C2 evaluate each slot on its own samples; C3 malware subsampled to 10% per slot (cap and flag; sensitivity ratio 5%). AUT = trapezoid area over per-slot F1 divided by (N-1); A-AUT = mean and sd over rolling windows. Delay d in {0,1,2,3}: a label queried in slot t is usable from slot t+1+d, and the delay lives only in `sim/queue.py`. Budget 0.5, 1, 2, 5% of the slot (absolute counts always reported). Policies: never, periodic every 3 slots, monitor-triggered. Selectors: random, uncertainty, credibility (Mondrian conformal p-value) with a reserved calibration slice. Models: logistic regression and LightGBM at fixed hyperparameters. Equivalence margin 0.01 A-AUT [P-10]; RQ1 band 0.05. Two-stage bootstrap (moving blocks of windows, then seeds), 10,000 replicates [P-08].

## 5. Questions, registrations and experiments

RQ1 how far a random split overstates the time-aware score; RQ2 what delay and budget cost or buy and whether the budget response is concave; RQ3 whether uncertainty or credibility selection beats random and whether the advantage shrinks under delay; RQ4 whether a monitor-triggered policy beats periodic retraining at the same label cost.

E0 baselines and E1 label-influence diagnostics were run and read before any registration (so RQ1 is a registered reading of known numbers). E2 (54 cells) registered at tag `prereg-v1`, E3 (56 cells) at `prereg-v2`, E4 (76 cells) at `prereg-v3`, each before its first result; all 186 cells completed with none failed [E-26, E-40, E-48]. E5 (cross-platform repeat) and E6 (EMBER2024) were not run (`reports/G5-tier3-decision.md`). Gates G1 to G4 were decided PASS by the researcher; Claude never decides a gate.

## 6. Headline results (all small; intervals are 95% two-stage bootstrap)

- Retraining on bought labels helps a little on LAMDA: periodic minus never at 5% of the slot, delay 0: 0.017 [0.007, 0.024] (LR), 0.020 [0.012, 0.022] (LightGBM) [E-30]; BODMAS about 0 [E-29].
- Late labels cost a little on LAMDA: delay 0 minus delay 3 at 5%: 0.011 and 0.013 [E-30]. Diminishing returns detected in one stratum of four [E-34].
- Random-split gap depends on the comparator: 0.03 to 0.04 (LAMDA) under the registered per-slot comparator, 0.14 to 0.15 under the window-level one [E-35]; not attributed to leakage alone [E-18].
- Selection beats random by 0.0109 to 0.0177 at delay 0 and 0.0015 to 0.0095 at delay 3 on LAMDA; interaction positive in 8 of 8 rows [E-43, E-42]; confounded with class mix of the arrived labels [E-47].
- No drift monitor beat periodic retraining; monitors alarmed in most slots, with precision near always-alarm [E-59, E-60, E-61, E-63].
- Reproduction: `driftwatch reproduce table1` MATCH on 8 rows, max difference 0.000000, 1,061 s on 8 Nov 2026 [E-82].

## 7. Limits (chapter 8 lists all 19, section 8.7 the open items)

Effects are hundredths of A-AUT against window sd of 0.05 to 0.07 [E-28]; LAMDA's 16 windows are about four independent blocks and seeds are draws, not replicates [P-12]; BODMAS has one useful refit per window; delay is simulated and the analyst is perfect; LAMDA labels are antivirus-centric with an unpublished scan date [D-16]; BODMAS's binary label basis is not stated in its paper and its dataset licence is not stated [D-18]; class prior moves per-slot F1 [E-66]; one laptop, two datasets, two detectors; the E3 trap arm never retrains [E-45]; the cluster-bootstrap width statement rests on a synthetic check [L-34].

## 8. Decisions (ADRs)

0001 tooling and guardrails; 0002 MIT licence; 0003 package name `driftwatch-lifetime` (fallback `driftwatch-sec`); 0004 slot definition; 0005 windows and size gate; 0006 metric threshold scaling; 0007 pool composition and budget; 0008 RQ1 comparator and E2 design; 0009 calibration rows are not training rows; 0010 monitor inputs and reference; 0011 docs tool (Sphinx with MyST; the phase prompt calls it ADR-0008 but that number was taken).

## 9. Hard rules (CLAUDE.md, enforced by hooks and tests)

No malware or binaries; C1 to C3 raise and are never weakened; label delay only in `sim/queue.py`; selectors, policies and monitors never see held-back labels; fit everything on the current training window only; one YAML config per run with hash, seeds and versions; never edit `docs/PREREG.md` or tagged addenda after their tag (use an addendum or ADR); no number in README, report or paper unless it is in `docs/CLAIMS.md` with file and commit; never write "first" as a contribution; do not tune a monitor until it wins; respect licences, commit no dataset content except the synthetic fixture; no evasion tooling. The Stop gate runs the fast tests; the guard blocks force pushes, `git add data/ results/`, recursive deletes outside temp folders, downloads from hosts off an allowlist (which excludes `doi.org`), and writes to locked files.

## 10. Commands

`uv sync --frozen`; `uv run pytest -q` (fast) and `uv run pytest -m slow`; `uv run ruff check . && uv run ruff format .`; `uv run python scripts/check_guardrails.py` (45 scenarios); `uv run python scripts/claims_audit.py`; `uv run python scripts/check_bib.py`; `uv run driftwatch smoke`; `uv run driftwatch reproduce table1` (about 18 minutes, 1.5 GiB cap); docs: `uv run --group docs sphinx-build -c docs -W --keep-going -b html . docs/_build/html`. Paper: `tectonic paper/main.tex` (Tectonic is installed on the researcher's laptop at `E:\tools\tectonic-env\Library\bin\tectonic.exe`).

## 11. Release and infrastructure

PyPI uses Trusted Publishing from `release.yml` (environments `testpypi` and `pypi`; the `pypi` environment needs a reviewer approval). Tags are signed with an ED25519 SSH key (`git tag -s`, verified with `git tag -v`). A published GitHub release triggers the Zenodo webhook and mints a DOI (permanent; each release is a new version under the concept DOI). The docs site is deployed by `docs.yml` to `gh-pages`. The procedure is `docs/RELEASING.md`. Branch protection on `main` requires CI; changes go in by pull request.

## 12. Quality evidence on 8 Nov 2026

1,056 fast tests and 142 slow tests pass; ruff clean; guardrail demonstration 45 of 45; claims audit PASS; bibliography 36 of 36 resolved; strict docs build and link check pass in CI; secret-shaped text found in 0 of 444 revisions of the public repository; `pip-audit` on the locked environment found no known vulnerabilities; Dependabot alerts and security updates are enabled on the public repository (8 Nov 2026); every workflow declares least-privilege permissions and pins actions by commit SHA.

## 13. Open items that only the researcher can settle

Following the venue's AI-use policy at submission (the researcher decided that the paper draft carries no disclosure paragraph; EuroS&P 2027's call requires one in the acknowledgments, which is part of why DIMVA 2027 cycle 2 was chosen); whether "Li et al. (NDSS 2025)" is the paper the original plan meant; a line-by-line reading and rewrite of the report and the paper; the capstone hand-in date (about 10 Dec 2026, exact date to confirm); the submission itself (target decided 8 Nov 2026: DIMVA 2027 cycle 2, paper deadline 18 Feb 2027, Springer LNCS, double-blind; see `docs/submission_checklist.md`); whether to rerun the E3 trap arm under an addendum; whether to deposit the stored predictions publicly (limit 18); resetting the Zenodo webhook secret that appeared in one session log (only Zenodo can rotate it: zenodo.org/account/settings/github, switch the repository off, then on; not done yet).

## 14. Gotchas learned

- A failing pre-commit hook (ruff) can abort `git commit` silently when output is filtered; always check `git log -1` after committing.
- Windows: use absolute Windows paths with the file tools; the Playwright screenshot tool can only save under the primary working directory; `rm -rf` and `$(...)` command names are blocked by the guard.
- Linkcheck now checks live GitHub and PyPI links, so a transient 504 can fail the Docs workflow; rerun the failed job.
- Memory: the machine has 7.2 GB usable; the cap for runs is 1.5 GiB; do not run the slow suite and a full reproduction at the same time (OpenBLAS allocation failures).
- Commit hashes in old CLAIMS rows belong to the private history; use `docs/commit_map.csv`.

## 15. Suggested next steps

1. Researcher: read and rewrite the paper and report; port the paper to the Springer LNCS class and build `paper/main-anon.tex` for the double-blind submission (DIMVA 2027 cycle 2, 18 Feb 2027).
2. If a trap-arm rerun, class-prior controls, a longer BODMAS window or other monitor settings are wanted: write an addendum and tag it before any run (`docs/ROADMAP.md`).
3. Release 0.2.0 only with the researcher's go (new PyPI file and new Zenodo version).
4. Keep the monthly arXiv audit (`docs/MAINTENANCE.md`) and the quarterly dependency refresh going.

## 16. Starting a new session

Read in this order: `CLAUDE.md`, this file, `docs/PHASES.md`, `docs/CLAIMS.md` (only the rows you need), the current phase prompt in `docs/prompts/`, then the code you will touch. Plan before touching more than three files. Ask the researcher for scope, pre-registration, gate and release decisions; discover everything else yourself.
