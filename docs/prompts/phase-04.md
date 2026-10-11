PHASE 4 | Models, AUT/A-AUT, E0 baselines | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Produce trustworthy baselines under the protocol and the metric implementation everything else is judged by, then decide Gate G1 with evidence. Do not start the simulator.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/DECISIONS/ADR-0005-windows-and-size-gate.md
- src/driftwatch/data/slicer.py
- src/driftwatch/data/constraints.py
- src/driftwatch/data/loaders.py
- scripts/leakage_canary.py
- docs/PREREG.md

## DELIVERABLES
1. A model interface (fit, predict_proba, fixed decision threshold, explicit seed) with logistic regression (feature scaling fitted on the training window only; sparse-friendly for LAMDA) and LightGBM in a configurable "fast profile". Provide scripts/bench_fit.py that measures fit time at the largest training window on this machine and records cores and RAM.
2. Metrics: per-slot F1 of the malware class, FPR and FNR, AUT by the trapezoid rule, A-AUT as mean and standard deviation of AUT over rolling windows (follow Chow et al., arXiv 2506.23814, and verify the window formula against the paper's appendix, including the case nT > nE), labels spent, recovery time. Unit tests as the guide specifies: constant F1 gives that constant; a known two-point example matches the hand-computed trapezoid.
3. A result store: one row per (config hash, seed, window, slot) plus raw per-slot predictions in Parquet, with config hash, package versions and seeds. One CLI entry, `driftwatch run <config.yaml>`, deterministic given the config.
4. E0: a baseline table for both models on BODMAS and LAMDA under the time-aware protocol, the random-split F1 for the same data, and the real-data leakage canary. Publish published ranges from the guide only as a sanity band, never as a target.
5. reports/G1.md: pass or fail against the criteria below, with the evidence.
6. An ADR (next number) for the decision threshold (default fixed 0.5; any tuned threshold may use only the final training slot), the scaling policy and the A-AUT window formula.

## CONSTRAINTS
- No simulator, labels queue, selectors, conformal or monitors in this phase.
- Do not tune hyperparameters to chase published numbers. Hyperparameters are fixed in config and recorded in docs/PREREG.md before E0 runs.
- If a fit takes more than 60 seconds on my machine, apply the fast profile, then feature or row subsampling, and report; shrink the grid before shrinking the claim (guide E2 rule).

## ACCEPTANCE (show evidence)
- AUT tests pass. A rerun from the same config gives identical per-slot predictions (compare hashes).
- On at least one dataset, time-aware AUT(F1) is below the random-split F1 by the margin set in PREREG (sanity band, at least 0.05 unless I changed it) and the real-data canary moves AUT toward the random number. Any AUT above 0.90 on a hard split is explained or treated as a leakage alarm.
- Fit-time table for both models on both datasets, and a statement of whether the 60 s limit holds.
- reports/G1.md states PASS or FAIL against: sensible baseline on at least one dataset; canary passes; tests green; fit-time budget.

## STOP RULE (guide, week 4)
If no sensible time-aware baseline exists on at least one dataset, stop adding features and fix the slicer. Do not proceed to Phase 5.

## WORKING METHOD
Plan mode first. Tests before code. Ask me only for decisions that are mine (threshold policy, window formula ambiguities).

## RE-ENTRY
- update: apply CHANGE_REQUEST (new model, metric or window rule). Add the test first, rerun E0, show before and after, update the ADR.
- maintain: rerun E0 on the locked environment, compare against the stored baseline table, report any numerical drift and its cause (package update, data change).

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- src/driftwatch/models/linear.py
- src/driftwatch/models/lgbm.py
- src/driftwatch/metrics/aut.py
- tests/test_aut.py
- scripts/bench_fit.py
- configs/e0_bodmas.yaml
- configs/e0_lamda.yaml
- reports/tables/e0_baselines.csv
- reports/G1.md
- docs/DECISIONS/ADR-0006-metrics-threshold-scaling.md
