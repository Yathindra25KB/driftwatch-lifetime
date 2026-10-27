# Test coverage

Measured on 22 Oct 2026 on commit 46ec2d9 plus the Phase 10 tests listed below (not yet committed when it ran), with `uv run --with pytest-cov pytest -q -m "slow or not slow" --cov=driftwatch` (no dependency was added and `uv.lock` did not change; the raw report is `results/logs/coverage.json`, not committed). The whole suite, fast and slow tests together, passed.

**Overall: 93.9% of 7091 statements.**

## The areas the Phase 10 plan names

Line coverage says a line ran, not that its behaviour is pinned. For these four areas the protection that matters is the kill matrix of the slicer mutants (`tests/test_mutation_matrix.py`) and the spy and label-invariance tests (`tests/test_sim_sealed.py`, `tests/test_runner_e4.py`), which coverage does not measure.

| Area | Module | Statements | Covered | % | Lines not covered |
|---|---|---|---|---|---|
| Constraints (C1 to C3) | `data/constraints.py` | 108 | 107 | 99.1 | 208 |
| Label queue (delay rule, sealed labels) | `sim/queue.py` | 145 | 142 | 97.9 | 54, 55, 118 |
| Conformal layer | `conformal/mondrian.py` | 42 | 42 | 100.0 | none |
| Conformal layer | `conformal/nonconformity.py` | 63 | 61 | 96.8 | 63, 75 |
| Conformal layer | `conformal/recalibrate.py` | 106 | 106 | 100.0 | none |
| Monitors | `monitors/base.py` | 85 | 82 | 96.5 | 54, 56, 58 |
| Monitors | `monitors/ks.py` | 54 | 51 | 94.4 | 40, 45, 46 |
| Monitors | `monitors/mmd.py` | 58 | 57 | 98.3 | 94 |
| Monitors | `monitors/domain_clf.py` | 76 | 70 | 92.1 | 49, 59, 97, 98, 111, 117 |
| Monitors | `monitors/p_uniformity.py` | 35 | 34 | 97.1 | 69 |
| Monitors | `sim/monitoring.py` | 105 | 105 | 100.0 | none |

## Modules below 90%

| Module | % | Why the rest is not covered |
|---|---|---|
| `data/download.py` | 35.7 | network downloads; exercised by the clean-clone reproduction, not by tests |
| `__init__.py` | 66.7 | version lookup fallback |
| `cli.py` | 73.4 | the data, run and reproduce subcommands that need downloaded data |
| `sim/reproduce.py` | 79.2 | the full (non-smoke) reproduction that fetches BODMAS |
| `metrics/e0_tables.py` | 87.5 | see the missing lines in the raw report |
| `data/tables.py` | 89.2 | see the missing lines in the raw report |
| `data/lamda.py` | 89.7 | see the missing lines in the raw report |
| `metrics/e4_tables.py` | 89.8 | see the missing lines in the raw report |

## What this measurement found

The first run of this measurement failed one test: `tests/test_mutation_matrix.py` reported that the slicer mutant `public_order_stratified` survived. The cause was a speed-up made earlier (commit c8a525f), which marked `tests/test_slicer_review_fixes.py` slow. The mutation harness runs its suites with `-m "not slow"`, so it never ran the one test that kills that mutant, and a leakage guardrail was weaker than the matrix in `reports/mutation_matrix.md` says. The module takes about 4 seconds, so it is fast again, and `tests/test_mutation_matrix.py` now has a fast test that fails if any suite the harness runs is marked slow. The kill matrix passes with every mutant killed.

## Tests added in Phase 10

- `tests/test_validation_branches.py`: the refusals in the constraints, the label queue and the conformal layer (a missing timestamp, labels outside 0 and 1, a malformed kept set, an empty window, an empty calibration buffer).
- `tests/test_fixture_regenerates.py`: the committed fixture is what the generator writes, byte for byte, and stays under 1 MB.
- `tests/test_configs_parse.py`: every config in `configs/` parses and plans its cells.
- `tests/test_audit_results.py`: the results audit.

Not covered on purpose: the defensive branch in `check_c3` that raises when the achieved ratio exceeds the target after every earlier check has passed (it cannot be reached with valid inputs), and the network paths of `data/download.py`.
