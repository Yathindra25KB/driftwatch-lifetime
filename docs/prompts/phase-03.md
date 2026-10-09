PHASE 3 | Time slicer, C1-C3, leakage canary | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Make temporal leakage mechanically impossible and detectable. Every later result depends on this phase; do not rush it and do not start any model or simulator work.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/DECISIONS/ADR-0004-slot-definition.md
- src/driftwatch/data/loaders.py
- reports/data_inventory.md
- tests/fixtures/

## DELIVERABLES
1. A slicer that, for a dataset, the approved slot definition and a window spec, yields the initial training window (nT slots) and then evaluation slots one at a time. A rolling-window generator (nT, nE, stride) for A-AUT that never spans a data gap and skips slots that fail the minimum-size gate; log what was skipped.
2. C1, C2 and C3 as checks that raise exceptions, never warnings, in the constraints module. C1: every training sample is strictly older than every evaluation sample. C2: each evaluation slot contains malware and benign samples from the same time window only. C3: each evaluation slot reaches the target malware ratio (default 10%, configurable, plus one sensitivity ratio) by seeded subsampling of malware only. Log per slot the counts before and after subsampling and the share of malware discarded.
3. A per-slot manifest (slot id, time bounds, counts) written with every run.
4. Tests, including property-based tests on random synthetic timelines, and mutation checks: deliberately break the slicer (shift a boundary, shuffle timestamps, leak one sample) and show the tests fail. test_constraints must implement the guide's definition exactly.
5. The leakage canary: with timestamps shuffled, a trivial model's AUT must move toward its random-split score. A test on the fixture now, and a script for the real data that Phase 4 will run.
6. An independent review: run the leakage-reviewer subagent on the slicer and constraints, save its findings under docs/reviews/, fix what it finds.
7. An ADR (next number) proposing nT, nE and stride per dataset, the minimum-size gate numbers and the ratio policy, derived from the inventory. Status PROPOSED until I approve it.

## CONSTRAINTS
- No model code beyond a trivial fixture model. Never densify LAMDA. Deterministic given a seed; seeds are explicit parameters.
- Never weaken, skip or delete a constraint test to get green. If a test looks wrong, write an ADR and ask me.
- No dependence on a specific dataset in the slicer logic; it works on any time-indexed table.

## ACCEPTANCE (show evidence)
- All constraint and property tests pass; every mutation check fails when it should (paste the failing output).
- Canary on the fixture: AUT with shuffled timestamps is clearly above AUT with true timestamps.
- leakage-reviewer reports no unresolved C1-C3 violation.
- Full-dataset slicing finishes in minutes and never densifies LAMDA.
- I have approved the window ADR.

## STOP RULE
The guide says not to compress this phase. If the canary does not move AUT toward the random-split value, treat the slicer as broken: diagnose and fix before anything else.

## WORKING METHOD
Plan mode first. Write the tests before the implementation. Ask me only for decisions that are mine (window parameters, size gate).

## RE-ENTRY
- update: apply CHANGE_REQUEST (a new slot length, ratio or dataset). Update tests first, show they fail on the old logic, then change the slicer, rerun the canary and the reviewer.
- maintain: rerun mutation checks and the canary on current data caches; report any change.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- src/driftwatch/data/slicer.py
- src/driftwatch/data/constraints.py
- tests/test_constraints.py
- tests/test_leakage_canary.py
- scripts/leakage_canary.py
- docs/reviews/slicer-review.md
- docs/DECISIONS/ADR-0005-windows-and-size-gate.md
