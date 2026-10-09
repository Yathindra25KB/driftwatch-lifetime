PHASE 8 | Conformal layer and selection (E3) | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Add the conformal layer and the two smarter selectors, then answer RQ3: does uncertainty- or credibility-based selection still beat random selection when labels arrive late, at equal labels spent? Mind the exchangeability trap.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/PREREG.md
- docs/CLAIMS.md
- reports/G3.md
- src/driftwatch/sim/selectors.py
- src/driftwatch/sim/runner.py
- src/driftwatch/metrics/aut.py
- scripts/run_grid.py
- scripts/make_tables.py
- scripts/make_figures.py
- report/ch06_method.md
- report/ch07_experiments.md

## DELIVERABLES
1. conformal/mondrian.py: class-conditional (Mondrian) p-values p_c(x) = (1 + #{calibration samples of class c with score >= s_c(x)}) / (n_c + 1), and credibility as the p-value of the predicted class. Unit tests against hand-worked examples, and a uniformity check on exchangeable synthetic data.
2. conformal/nonconformity.py with two pluggable scores (one minus the model probability for the class; distance to the class centroid in feature space) and conformal/recalibrate.py with an explicit recalibration rule: a calibration buffer of recent releases, minimum samples per class, keep the previous calibration otherwise, and a count of skipped recalibrations. The initial calibration comes from a time-ordered hold-out inside the initial training window that was not used to train that model.
3. Uncertainty (closest to 0.5) and credibility (lowest p-value of the predicted class) selectors that plug into the existing selector interface. All selectors spend identical budgets, with a random reserved calibration slice (default 20%); calibration labels must come only from that random slice.
4. Tests: calibration contamination (a selected sample entering the calibration buffer must fail a test); equal labels spent across arms; delay still handled only by the queue.
5. An addendum docs/prereg/addendum-v2.md before any E3 run: RQ3 contrasts, the reserved-slice ablation (0% as a deliberate trap demonstration, 10, 20, 40%), the nonconformity-score comparison, reduced-grid rules. I approve it, then tag prereg-v2.
6. E3 runs on the pre-registered cells, tables and figures regenerated from stored predictions; run the stats-reviewer and fix findings; update ch06_method.md and ch07_experiments.md using ledgered numbers only.

## CONSTRAINTS
- Do not re-implement Chen et al.'s HCC or Transcendent; cite them as related work. Selecting under a budget is not claimed as new.
- No monitors yet. No tuning after prereg-v2. Keep the same slicer, simulator, pool design and metric as Tier 1.
- Compute: start with the reduced E3 grid (for example delays {0,3}, budgets {1,2}); extend only if my hours allow. Offload chunks with the existing CLI.

## ACCEPTANCE (show evidence)
- Hand-worked p-value examples pass; uniformity check passes on exchangeable data.
- The contamination test demonstrably fails when a selected sample is put in the calibration buffer.
- Labels spent are equal across selectors in every cell (assertion in the runner and in the tables).
- prereg-v2 tag predates E3 results. Tables and figures regenerate with no fits.
- stats-reviewer findings resolved; Ch 7 E3 claims are all in docs/CLAIMS.md.

## STOP RULE
Cut if Tier 1 was not completed by Gate G3 (guide E3 rule). If compute or hours run short, keep BODMAS only for E3 and say so.

## WORKING METHOD
Plan mode first. Show me the recalibration rule and the selector budget accounting in a diagram before coding. Ask me only for decisions that are mine (addendum approval, reduced grid).

## RE-ENTRY
- update: apply CHANGE_REQUEST (new nonconformity score, new selector). Pre-register as an addendum, run only new cells, update tables and CLAIMS.md.
- maintain: rerun the conformal unit tests and the uniformity check on updated dependencies.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- src/driftwatch/conformal/mondrian.py
- src/driftwatch/conformal/nonconformity.py
- src/driftwatch/conformal/recalibrate.py
- tests/test_conformal.py
- docs/prereg/addendum-v2.md
- configs/e3_bodmas.yaml
- configs/e3_lamda.yaml
- reports/tables/e3_selection.csv
- reports/figures/e3_selection.png
- docs/reviews/stats-review-e3.md
