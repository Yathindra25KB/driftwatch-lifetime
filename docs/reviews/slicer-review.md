# Leakage review: Phase 3 time slicer and constraints

**Reviewer:** leakage-reviewer subagent (read-only; it did not write the code), 11 Oct 2026.
**Scope:** `src/driftwatch/data/` constraints, slicer, tables, presets, canary, synthetic, loaders (public view), `scripts/leakage_canary.py`, and their tests. Code at commit `4ce5cba` plus ADR-0005 `fc36e5b`.
**Method:** the reviewer read the files in full and ran the existing tests (115 passed). It could run only `uv run pytest`, so it did not execute probes of its own.
**Result of pass 1:** 14 findings: 0 blockers, 3 major, 11 minor. No C1, C2 or C3 violation was found on the table or cached paths. The risk it identified is at the interface to later phases.

## What it checked and found sound
- **C1.** `check_c1` is strict, raises on equal timestamps, empty sides and missing timestamps, and runs per evaluation slot against the real training timestamps. Slot assignment is half-open everywhere.
- **C2, cached path.** Every row's timestamp lies inside its base unit and so inside its slot, by construction of the ISO-week and month units and the Monday-anchored grid.
- **C3.** Malware-only, seeded by `(seed, crc32(slot id))`, independent of window and of input row order, exact `Fraction` arithmetic, nested across ratios, counts in the manifest.
- **Gate and gaps.** Empty, partial and failing slots are never in a window; `_open_window` re-asserts a contiguous, usable grid; skips are logged with reasons.
- **Canary.** The shuffled and random-split baselines are leak-free; the training size comes from the plan, not from what a leaky slicer returned.

## Findings and dispositions

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | major | The "opaque" `PublicSlot.row_id` and row order are not opaque: BODMAS `row_id` is the time rank, malware subsampling leaves gaps in the id sequence exactly where malware was dropped, and LAMDA ids encode the source file | **Fixed** (`ee4bcd0`). `EvalSlot.public()` returns a seeded, label-independent shuffle with handles `0..n-1` and an isolated feature copy; `EvalSlot.resolve` maps handles back for the queue and metrics. Tests: `test_f1_*` (point-biserial correlation of order and handles with the label stays under 0.25 on a class-linked slot where the unshuffled order correlates above 0.5); mutant `public_ids_are_row_ids` |
| 2 | major | `NO_GAP` exited 0 like `PASS`; the only leak test was a total leak | **Fixed.** `NO_GAP` is inconclusive and exits 3 with an explicit message; it never counts toward G1. The sensitivity limit is measured and pinned (`test_canary_sensitivity_to_partial_leaks_is_pinned_not_assumed`): leaking 1 of 10 evaluation slots raises true AUT 0.79 to 0.84 yet still reads PASS; leaking 3 closes the gap (NO_GAP, warning). Small leaks are caught by C1/C2 and the oracle tests, not by the canary alone; the script docstring says so |
| 3 | major, carried | A `Window` bundles training rows, the future schedule and the source (true `y`, `ts` of any later slot). Nothing structural stops a policy from reading held-back labels | **Carried to Phase 5.** No selector, policy or monitor exists yet. Rule for Phase 5: they receive only `PublicSlot` and `TrainWindow`, never `Window` or `EvalSlot`; labels reach only the queue and the metrics. The spy test (sentinel `y` that raises on any read) lands in the same change as the first selector (ADR-0004 item 7) |
| 4 | minor | C2 ran only after subsampling, so a stray out-of-window malware row could be subsampled away unseen; training rows had no window check | **Fixed.** `check_c2` runs on the whole raw evaluation slot, again on kept rows, and on every training slot at window open. Tests: `test_f4_*` with a hostile source |
| 5 | minor | `n_seen_in_train` used only the initial window although ADR-0004 says "the training pool" | **Fixed.** Renamed `n_seen_in_initial_train`, documented as past-only against the initial window; a vector present only in a later slot counts 0 (`test_f5_*`). The pool that includes released labels is the simulator's (Phase 5) |
| 6 | minor | `check_c3` validates counts only, so a seed-dependent but biased draw would pass | **Fixed.** Statistical test on the draw's position distribution and mutant `oldest_malware` |
| 7 | minor | The C2 and C3 call sites were pinned only through the oracle | **Fixed.** `test_f4_*` and `test_f7_*` expect the specific `C2Violation` / `C3Violation` from the slicer |
| 8 | minor | The production-like configuration (anchor, exclusion) was exercised only by the full-data run | **Fixed.** `test_f8_*` checks row, label and feature alignment after exclusion against raw meta |
| 9 | minor | `window_id` had no ratio or seed; C3 counts were logged only with a `SliceLog` | **Fixed.** `window_id` starts with the spec digest; each evaluation slot's C3 counts go through `logging` regardless |
| 10 | minor | A `RowFilter` always received `label` | **Fixed.** A filter sees only its declared columns; the cache planner no longer passes labels. The BODMAS placeholder rule is class-conditional by effect (it removes benign rows only), which ADR-0004 accepts and the manifest counts per class |
| 11 | minor | The public view shared a mutable feature array with the scoring path | **Fixed** by the public copy in 1. `TrainWindow` concatenations are derived copies |
| 12 | minor | The BODMAS rows published without a UTC offset (read as UTC) were not reported per slot | **Fixed.** `n_naive_ts` per slot in the slot manifest. Q4 stays "assumed UTC" as a threat to validity |
| 13 | minor | A base unit emptied by the filter did not make its slot partial | **Fixed.** The slot is marked partial and is therefore unusable (`test_f13_*`) |
| 14 | minor | ADR-0005 cited this file before it existed | **Fixed** by this file |

## Pass 2: re-review of the fixes (commit `ee4bcd0`)
**Reviewer:** leakage-reviewer subagent again, read-only; 142 tests passed on its run. **Verdict: no C1, C2 or C3 violation and no sealed-label problem in the slicer remains unresolved.** All six claimed fixes held and introduced no new leakage path (the public permutation is drawn from the row count only, with entropy independent of the C3 draw). It reported 9 further findings (1 major latent, 7 minor, 1 informational):

| # | Severity | Finding | Disposition (`9b27b58`) |
|---|---|---|---|
| P1 | major, latent | `SlotData.public()` still returns the same `PublicSlot` type with dataset ids and class-linked order, and ADR-0004 item 7 and both data cards point Phase 5 at it | **Fixed.** The selector-facing view is a distinct `OpaqueSlot` (no `row_id`, no back-reference); ADR-0004 addendum 1 amends item 7; both data cards corrected; the loader view is documented as loader-level only. Test `test_p2_1_*` |
| P2 | minor | The opacity test checked linear correlation only; a class-aware regular order would pass | **Fixed.** Metamorphic test: identical counts, different label placement, identical permutation; mutant `public_order_stratified` (correlation about 0, killed only by this test) |
| P3 | minor | Handles are slot-local; resolving against the wrong slot would silently release other labels | **Fixed.** `resolve(slot_id, handles)` raises on a mismatch or an out-of-range handle |
| P4 | minor | The public order is a pure function of the seed and slot id, so a consumer that deliberately recomputes it could invert it | **Accepted, documented.** This is accident-proofing, not an adversarial boundary: consumers never import slicer internals, and the Phase 5 spy test enforces the type boundary. A per-run secret would add state for no protection against a deliberate insider |
| P5 | minor | `window_id` ignored source provenance, so runs with and without the placeholder filter shared ids | **Fixed.** A digest of the source provenance (row filter, length, anchor, exclusions, manifest hash) is part of the id |
| P6 | minor | `TableSource(exclude=...)` accepted any callable, including one that reads labels | **Fixed.** Only a `RowFilter` is accepted |
| P7 | minor | Iterating a window twice duplicated manifest rows | **Fixed.** Rows are keyed by (window id, role, slot id) and replaced |
| P8 | minor | A slicer violation inside the canary exited 1 (same as FAIL); PASS with an AUT above 0.9 exited 0 | **Fixed.** Violation exits 4; PASS with the warning exits 3 |
| P9 | informational | `EvalSlot` carries no per-row seen-before mask, which the E0 duplicate sensitivity needs | **Carried to Phase 5**, which must build the mask from the simulator's real training pool and give it to the metrics only, not to the public view |

## Evidence
- Fast suite after the pass-2 fixes: 481 passed. Kill matrix: 15 of 15 mutants killed, baseline 120 tests green (`reports/mutation_matrix.md`, commit `9b27b58`).
- Real caches after the pass-2 fixes: LAMDA 47 windows and 564 evaluation slots, BODMAS 2 windows and 24 evaluation slots, no C1-C3 violation, nothing densified.

## Evidence (pass 1)
- Fast suite after the pass-1 fixes: 472 passed. Fixes were written test-first; the 12 new regression tests failed on the code as reviewed.
- Kill matrix: 14 of 14 mutants killed, baseline green (`reports/mutation_matrix.md`). The two new mutants are `oldest_malware` and `public_ids_are_row_ids`.
- Real caches after the fixes: LAMDA 47 windows and 564 evaluation slots, BODMAS 2 windows and 24 evaluation slots, no C1-C3 violation, nothing densified, peak 0.36 and 0.65 GB. Window options unchanged.

## Not covered (code does not exist yet)
The `sim/queue.py` delay rule, fit scope for scalers and thresholds, and conformal calibration contamination. Hard rules 4 (spy test), 6 and 7 remain to be verified when those phases land; finding 3 above is their precondition.

## Deviations recorded
- The canary movement is tested on seeded synthetic timelines with planted drift, because the committed fixture has features independent of labels and cannot decay. The fixture caches prove the script runs end to end.
- C3 follows the researcher's "cap and flag" choice (ADR-0005): a slot already below the target ratio keeps all rows and is flagged `below_target`.
