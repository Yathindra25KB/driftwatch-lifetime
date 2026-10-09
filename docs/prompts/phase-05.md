PHASE 5 | Delay and budget simulator, E1 | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Build the simulator that is the project's scientific instrument. It streams one rolling window slot by slot under a label delay, a per-slot analyst budget, a selector and a retraining policy. Label delay must live in exactly one place. Finish with E1 and Gate G2.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/PREREG.md
- src/driftwatch/data/slicer.py
- src/driftwatch/data/constraints.py
- src/driftwatch/models/linear.py
- src/driftwatch/models/lgbm.py
- src/driftwatch/metrics/aut.py
- reports/G1.md
- docs/DECISIONS/ADR-0005-windows-and-size-gate.md

## DELIVERABLES
1. sim/queue.py is the only module that knows about delay d: a label queried in slot t becomes usable from slot t+1+d (d=0 means the next slot). Labels that would arrive after the window ends are ignored; document the rule.
2. sim/selectors.py: random selection now, with an interface that uncertainty and credibility selectors can plug into in Phase 8. Budget is a percentage of the evaluated slot (0.5, 1, 2, 5); log the absolute count with the percentage. A reserved random calibration slice is a parameter (default 20%, effective once conformal exists).
3. sim/policies.py: never, periodic (every 3 slots) and a monitor-triggered interface that raises NotImplementedError until Phase 9. Retraining uses only labels that have arrived.
4. sim/runner.py: config in, per-slot results out. Deterministic, resumable without duplicate rows, a cache for initial models keyed by a sub-hash of (dataset, window, model, seed), and parallelism across runs (one thread per run) rather than inside them.
5. A sealed label store: the held-back labels are reachable only through the queue's release call and the metric code. Policies and selectors must not be able to read them; prove it with a spy test.
6. Training-pool design: initial window plus arrived labels, with the weight of new labels and any windowing as explicit parameters. Run a "label influence" check (how many predictions change after retraining at 0.5% versus 5% budget) and write an ADR that fixes the pool design before any grid runs. Do not choose the design by looking at AUT.
7. E1 (RQ1): F1 versus time under a random split and under the time-aware protocol on the same data and the same C3 ratio, for both models, as one figure generated from stored predictions only.
8. A regression fixture rebuilt from the guide's Appendix A toy stream: assert the qualitative ordering (never is worst; more labels help; longer delay hurts). Do not copy its numbers anywhere; they are not evidence.
9. reports/G2.md: PASS or FAIL against the criteria below. Draft report/ch06_method.md (simulator section with a queue timeline diagram), report/ch05_related_work.md and report/ch02_landscape.md from sources you retrieve now, with access dates; mark anything unverified [verify].

## CONSTRAINTS
- No conformal layer and no monitors yet. No tuning of anything against AUT.
- True labels are for queue release and metric scoring only (CLAUDE.md rule). Never read data/ or results/ dumps into context; summarise.
- Every number in a draft chapter must exist in docs/CLAIMS.md with a file and commit, or be written as a [verify] placeholder.

## ACCEPTANCE (show evidence)
- test_queue_delay passes for d in {0,1,2,3}, including property-based tests; nothing is lost or duplicated.
- The spy test passes; leakage-reviewer reports nothing unresolved on queue, pool and runner.
- Same config and seed reproduce identical per-slot predictions; an interrupted run resumes cleanly.
- The regression fixture reproduces the guide's qualitative ordering.
- E1 figure exists and regenerates from stored predictions with no model fits.
- reports/G2.md exists.

## STOP RULE (guide, week 8)
If the simulator with label delay and budget does not run end to end on one dataset, cut to one dataset and one model. Tier 1 stays valid. Report the cut; do not hide it.

## WORKING METHOD
Plan mode first; show me the data flow (stream, queue, pool, policy) as a diagram before coding. Tests before code. Ask me only for decisions that are mine (pool design, truncation rule).

## RE-ENTRY
- update: apply CHANGE_REQUEST (new policy, selector or pool rule). Extend tests first, rerun the regression fixture and E1, record an ADR, and list which stored results are now stale.
- maintain: rerun the regression fixture and the queue tests on updated dependencies; confirm resume and determinism still hold.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- src/driftwatch/sim/queue.py
- src/driftwatch/sim/selectors.py
- src/driftwatch/sim/policies.py
- src/driftwatch/sim/runner.py
- tests/test_queue_delay.py
- tests/test_runner_regression.py
- configs/e1_bodmas.yaml
- configs/e1_lamda.yaml
- reports/figures/e1_random_vs_time.png
- reports/G2.md
- docs/DECISIONS/ADR-0007-pool-composition-and-budget.md
- report/ch05_related_work.md
- report/ch06_method.md
- report/ch02_landscape.md
