# Leakage review: Phase 9 (E4 drift monitors)

**Reviewer:** leakage-reviewer subagent (read-only), 20 Oct 2026, on branch `phase-09-monitors-e4` at 025449e plus the working tree.
**Scope:** `monitors/*`, `sim/monitoring.py`, `sim/runner_e3.py` (monitor step, rule R, matched source), `sim/policies.py`, `sim/config.py`, `sim/grid_e4.py`, `metrics/monitor_scores.py`, `metrics/e4_tables.py`, `scripts/make_e4.py`, the E4 configs, ADR-0010 and the E4 tests.
**Verdict:** no blocker and no major finding. The reviewer found no path by which held-back evaluation labels or future slot data reach a monitor, a policy, a retrain or the matched control:
- the alarm on slot `s` acts no earlier than the retrain before `s + 1`;
- rule R moves the reference only to an already streamed slot at or before `s − 1 − d`, and uses features only;
- the statistic cache holds only functions of features and seeded draws, for pairs every arm meets at the same time;
- labels spent are enforced equal per slot.

## Findings and resolutions (fixed in 108d5b2)

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | minor | The runtime spy wraps only the slot's label arrays. It could not see the metric door's `y_true` reaching a monitor through a later edit. | New test `test_monitor_outputs_do_not_depend_on_the_labels_the_runner_holds`. It permutes every label that the scoring and release doors hand out, and the never-arm monitor columns stay identical. |
| 2 | minor | The disk-cache key omitted `holdout_fraction` and the data version. A dirty tree could reuse stale statistics. | The cache is now keyed by window, hold-out fraction and source-provenance digest under the code version. A dirty or unknown version writes no disk cache. Tested. |
| 3 | minor | The matched schedule repeated the queue's delay arithmetic. | Added `LabelQueue.release_slot(t)`. The queue uses it, and so does the matched schedule. |
| 4 | minor | The matched arm can refit fewer times than k (a no-op at an event). This was not flagged. | The window rows record `matched_k_source` and `matched_refit_shortfall`. M-C rows report the shortfall share and mean. Addendum v3 says so. |
| 5 | minor | The matched source's settings were not checked. | The source's dataset, slots, window, ratio, model, selector, delay, budget, pool, nonconf and trigger must equal this arm's, or the run raises. Tested. |
| 6 | minor | The import ban saw top-level imports only. | It walks the whole syntax tree, so lazy imports are covered. |
| 7 | note | `p_uniformity` together with `calibration_in_pool: true` would compare against in-sample scores. | The config refuses the combination. Tested. |
| 8 | note | After a refit, about 0.8% of the reference slot's rows are training rows (in-sample score logit in MMD). | Accepted and recorded in ADR-0010 (about 2 of 200 rows). |
| 9 | note | The matched-count control is non-causal (it knows the window's refit count) and conservative for the monitor. | Stated in addendum v3, Known limits. |
| 10 | note | Settings are not frozen until addendum v3 is tagged. | `driftwatch grid` refuses E4 evidence cells before the `prereg-v3` tag (smoke allowed). Tested. |
