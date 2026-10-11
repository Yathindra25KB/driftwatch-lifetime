PHASE 9 | Drift monitors and scoring (E4) | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Implement four drift monitors behind one alarm interface, wire in the monitor-triggered retraining policy, and answer RQ4: which monitor best triggers retraining under label delay, and does any of them beat simple periodic retraining? Score monitors the way arXiv 2606.07789 scores drift detectors. Decide Gate G4.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/PREREG.md
- docs/prereg/addendum-v2.md
- docs/CLAIMS.md
- src/driftwatch/conformal/mondrian.py
- src/driftwatch/conformal/recalibrate.py
- src/driftwatch/sim/policies.py
- src/driftwatch/sim/runner.py
- scripts/run_grid.py
- scripts/make_tables.py
- scripts/make_figures.py
- reports/tables/e3_selection.csv

## DELIVERABLES
1. Monitors/ks.py (two-sample KS on the top-k features chosen from the training window, with multiple-testing correction), monitors/mmd.py (RBF kernel, subsampled, permutation threshold; for LR and LightGBM use model scores and a low-dimensional projection because they have no learned embedding, and record that choice in an ADR), monitors/domain_clf.py (reference window versus current slot, cross-validated AUC, permutation null) and monitors/p_uniformity.py (KS test of conformal p-values against uniform; the guide's sandbox showed a fraction-threshold rule never fires). One interface: update(slot data, state) -> alarm decision. Monitors never see true labels; the conformal monitor uses only calibration labels that have already arrived.
2. The monitor-triggered policy: retrain on alarm using only arrived labels, with a minimum gap between retrains and a documented rule for an alarm with no new labels.
3. metrics/monitor_scores.py: drop events defined from true labels (per-slot F1 at least 0.05 below the trailing 3-slot mean), then alarm precision, alarm recall and detection delay. True labels are used for scoring only.
4. docs/prereg/addendum-v3.md before any E4 run: monitor hyperparameters and thresholds frozen, RQ4 contrasts, matched-comparison rules, reduced-grid rules. I approve, then tag prereg-v3.
5. E4: monitor quality table; AUT comparison of monitor-triggered versus periodic retraining at matched labels spent and, separately, at matched number of retrains; per-monitor intervals; tables and figures regenerated from stored predictions. Run the stats-reviewer and fix findings.
6. reports/G4.md: Tier 2 status, what was cut, and the Tier 3 go or no-go checklist result. Update ch06_method.md and ch07_experiments.md with ledgered numbers only.

## CONSTRAINTS
- Do not tune monitors until one wins (guide E4 rule). Settings are frozen by prereg-v3. If periodic wins, report that; a careful negative result is a result.
- Same slicer, simulator, pool design and metric as before. Keep monitor compute bounded: subsample slots, cap domain-classifier fits, cache policy-independent statistics.
- No true labels inside any monitor (spy test).

## ACCEPTANCE (show evidence)
- Synthetic change-point tests: each monitor detects a known shift with the expected delay; on a no-drift stream the false-alarm rate is near nominal.
- The spy test passes. prereg-v3 tag predates E4 results.
- E4 table shows labels spent and retrain counts next to AUT, for every policy.
- stats-reviewer findings resolved; Ch 7 E4 numbers are all in docs/CLAIMS.md.
- reports/G4.md exists.

## STOP RULE
If Tier 2 is incomplete at the end of week 19, report what exists, label the rest future work, and do not start Tier 3.

## WORKING METHOD
Plan mode first. Show me the alarm interface and the retrain-trigger timeline in a diagram before coding. Ask me only for decisions that are mine (frozen thresholds, G4).

## RE-ENTRY
- update: apply CHANGE_REQUEST (a new monitor or threshold rule). Pre-register as an addendum, run only the new cells, report the effect on conclusions.
- maintain: rerun the synthetic change-point and false-alarm tests on updated dependencies.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- src/driftwatch/monitors/ks.py
- src/driftwatch/monitors/mmd.py
- src/driftwatch/monitors/domain_clf.py
- src/driftwatch/monitors/p_uniformity.py
- src/driftwatch/metrics/monitor_scores.py
- tests/test_monitors.py
- docs/prereg/addendum-v3.md
- configs/e4_bodmas.yaml
- configs/e4_lamda.yaml
- reports/tables/e4_monitors.csv
- reports/figures/e4_monitors.png
- reports/G4.md
- docs/reviews/stats-review-e4.md
