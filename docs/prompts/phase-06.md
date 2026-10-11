PHASE 6 | Tier 1 grid (E2) and statistics | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Run the pre-registered delay-by-budget grid (E2) on both datasets and produce the Tier 1 evidence for RQ2 with honest statistics. The question is how A-AUT changes with label delay and analyst budget under never and periodic retraining.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/PREREG.md
- src/driftwatch/sim/runner.py
- src/driftwatch/sim/queue.py
- src/driftwatch/metrics/aut.py
- reports/G2.md
- docs/DECISIONS/ADR-0007-pool-composition-and-budget.md
- reports/figures/e1_random_vs_time.png
- docs/CLAIMS.md

## DELIVERABLES
1. Pre-registration lock. Finalise docs/PREREG.md: RQ1 and RQ2 hypotheses, primary metric AUT(F1), the exact contrasts (for example d=0 versus d=3 at B=1% and 5% under periodic; periodic at 5% versus never; the budget response 0.5 to 5%), seeds, windows, test and decision rules, exclusion rules. Show me the diff, wait for my approval, then tag prereg-v1. After the tag, changes are addendum files only.
2. Grid configs: delay {0,1,2,3}, budget {0.5,1,2,5}% of the evaluated slot, policies never and periodic(3), models LR and LightGBM, both datasets, rolling windows for A-AUT, 5 seeds; the pre-registered headline contrasts repeated with 10 seeds. The never policy runs once per (dataset, model, window, seed), not once per cell.
3. A resumable grid driver with chunking (--chunk i/n), one result file per cell, a progress ledger, and a smoke grid first (1 seed, 1 window) that prints a timing extrapolation for the full grid before I commit to it. Provide a documented path to run chunks on Kaggle or Colab using the same CLI.
4. Statistics: bootstrap confidence intervals that resample windows first and then seeds within windows; Wilcoxon signed-rank only as a supporting check; effect sizes in plain units (AUT lost per slot of delay, AUT gained per extra label) with intervals; report absolute query counts next to percentages.
5. scripts/make_tables.py and scripts/make_figures.py regenerate every table and figure (A-AUT heat maps with std, per-slot curves, labels-spent and recovery-time tables) from stored predictions with no model fits.
6. Run the stats-reviewer subagent on the analysis code and on the claims; save notes to docs/reviews/stats-review-e2.md and fix findings.
7. Draft report/ch07_experiments.md (E1 and E2) and report/ch03_analysis.md using only numbers present in docs/CLAIMS.md; every claim carries file and commit.

## CONSTRAINTS
- No cell is dropped, rerun or re-seeded because its result looks wrong. A failure is logged with its reason. Negative and flat results are reported as they are.
- Do not change simulator, metric or pool design after prereg-v1; if a bug is found, fix it in a new commit, state which results it invalidates, and rerun exactly those.
- Never read large result dumps into context; use summaries and head.
- If any fit exceeds 60 seconds, shrink the grid in this order: delay 2, budget 0.5%, windows, seeds on non-headline cells. Shrink the grid before the claim.

## ACCEPTANCE (show evidence)
- Tag prereg-v1 exists and predates the first grid result; the path guard blocks PREREG edits afterwards.
- Every cell is complete or logged as failed with a reason. Counts of planned versus completed cells are reported.
- make_tables and make_figures regenerate identical outputs (hash equal) with no fits.
- stats-reviewer findings resolved; every number in Ch 7 is in docs/CLAIMS.md.
- The leakage canary is re-run on the final code and passes.

## WORKING METHOD
Plan mode first. Show me the compute plan (cells, fits, time per fit, total hours, where each chunk runs) before the grid starts. Ask me only for decisions that are mine (PREREG approval, where chunks run).

## RE-ENTRY
- update: apply CHANGE_REQUEST (extra delay, budget or model). Add it as a pre-registered addendum, run only the new cells, regenerate tables and figures, update CLAIMS.md.
- maintain: rerun the smoke grid on updated dependencies and compare against stored results; report numerical drift and cause.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- configs/e2_bodmas.yaml
- configs/e2_lamda.yaml
- scripts/run_grid.py
- scripts/make_tables.py
- scripts/make_figures.py
- reports/tables/e2_aaut.csv
- reports/figures/e2_heatmap_bodmas.png
- reports/figures/e2_heatmap_lamda.png
- docs/reviews/stats-review-e2.md
- report/ch07_experiments.md
- report/ch03_analysis.md
