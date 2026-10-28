# ADR-0010: Monitor inputs, reference rule, label-free p-values and bounded monitor compute

**Status:** ACCEPTED by the researcher on 2026-10-20 (option A in every section, as proposed). It is registered with `docs/prereg/addendum-v3.md` (tag `prereg-v3`).
**Date:** 2026-10-20
**Deciders:** Yathindra (researcher, decides); Claude Code (engineering lead, proposes)
**Phase:** 9

## Context
- The guide (§8, PROTOCOL §4) names four monitors behind one alarm interface: KS on top features, MMD on embeddings, domain-classifier AUC, and a KS test of conformal p-values. Monitors never see true labels; the conformal monitor uses only calibration labels that have already arrived (`.claude/rules/conformal-monitors.md`).
- The detectors are logistic regression and LightGBM. Neither has a learned embedding, so "MMD on embeddings" needs a stated substitute (Phase 9 prompt: "use model scores and a low-dimensional projection ... and record that choice in an ADR").
- A monitor compares the current slot with a *reference*. What the reference is after a retrain is not fixed by the guide. With label delay `d` a refit before slot `s` can only use labels queried up to slot `s - 1 - d`.
- Compute is bounded by an 8 GB laptop: the domain classifier with a per-test permutation null would need hundreds of fits per slot (Phase 9 prompt: "cap domain-classifier fits, cache policy-independent statistics").
- On a no-drift synthetic stream, a one-sample KS of conformal p-values against U(0, 1) alarmed in 25% of 200 slots at alpha 0.01 (fixed calibration set of about 300 rows per class, 500 test rows). The test treats the calibration distribution as exact. Found before any E4 run, while writing `tests/test_monitors.py`; commit 42eef7a.

## Options and decisions

### 1. MMD input for models without an embedding
- **A (proposed):** a TruncatedSVD projection (16 components) fitted without labels on the window's proper training rows (the window minus the time-ordered hold-out), plus the logit of the malware probability under the model in force; columns standardised on the pooled sample (reference plus slot) and an RBF kernel with the median-heuristic bandwidth on the pooled sample, both invariant under the permutations so the test stays exact; 200 rows per side; 199 permutations. (A first version standardised on the reference sample only; it gave 6 alarms in 200 no-drift synthetic slots and was replaced before any E4 run, commit bdad6e0.)
- B: model score only (one dimension). It sees no covariate shift that leaves the score unchanged.
- C: raw features. Kernel distances in 2,381 to 4,561 dimensions are dominated by noise; the cost is high.

### 2. Reference rule (rule R)
- **A (proposed):** the reference is a seeded sample (500 rows, features only) of the newest data the model in force was fitted on: initially the window's time-ordered hold-out (the newest 20% of the initial window by time); after a refit, the newest evaluation slot whose labelled rows were in the pool at that fit (at most `s - 1 - d`). An arm that never refits keeps the initial reference. The p-uniformity monitor's reference is the calibration buffer, by construction.
- B: the reference is the last slot seen before the refit (`s - 1`), whatever the delay. It describes data the model has not been trained on when `d > 0`.
- C: a fixed reference (the initial window) for the whole window. After drift, every monitor would keep alarming, and the monitor-triggered policy would collapse to "retrain every `min_gap` slots".

### 3. Label-free conformal p-values and the uniformity test
- **A (proposed):** score `1 - max(P, 1 - P)` under the model in force, Mondrian by *predicted* class (threshold 0.5, ADR-0006), compared with the calibration rows of the same predicted class (features of rows that have arrived; their labels are not read). Test: two-sample KS between the slot's scores (500 rows) and the calibration scores, per predicted class, Bonferroni over the classes present; undecided when a class has fewer than 20 calibration rows. The two-sample null accounts for the finite calibration set; on the 200-slot no-drift stream it passes the false-alarm test.
- B: E3's label-based Mondrian p-values (true class). These need the slot's labels, which a monitor may not see.
- C: one-sample KS of p-values against U(0, 1). Invalid conditional on the calibration set (25% false alarms, see Context).

### 4. Domain-classifier null and bounded compute
- **A (proposed):** logistic regression (C = 1, lbfgs, at most 200 iterations, features scaled inside each fold; lbfgs was chosen over liblinear for cost, about 6x faster on 1,000 x 2,381 dense rows), 5-fold stratified cross-validated AUC, 500 rows per side. The permutation null (99 draws) is computed **once per window** on the initial reference (two disjoint random halves of the hold-out get domain labels 0 and 1), shared by every seed, model and arm, and reused for later references of the window. `p = (1 + #{null >= AUC}) / 100`, so alarm at alpha 0.01 means the AUC exceeds all 99 null draws. The approximation: the null of a later reference is taken to equal that of the initial one, and the null uses at most 500 rows per side.
- B: a full permutation test per slot (99 x 5 fits per test). Hundreds of hours on LAMDA.

### 5. Policy-independent statistic cache
- **A (proposed):** KS and domain-classifier statistics depend only on (window, seed, reference slot, current slot) and seeded draws, so they are cached per window: in memory, and on disk under `<monitors.cache>/<code version>/<window digest>.json` for evidence runs (smoke runs write no cache). A cached value equals a fresh one (tested in `tests/test_runner_e4.py`); the cache changes cost, not results. MMD and p-uniformity depend on the model in force and are recomputed.

### 6. Common settings
`alpha = 0.01` per slot for every monitor, so the false-alarm rate on a stream with no drift has one nominal value. KS uses the top 20 features by absolute standardised class-mean difference on the proper training rows (training labels of the initial window only), Holm over the 20 tests. All four are fixed by addendum v3 and never tuned (CLAUDE.md rule 10).

## Consequences
- The MMD monitor mixes a covariate view (projection) and a model view (score logit); a shift in either can raise it.
- Under delay, rule R keeps the reference older than the latest data, so monitors tend to alarm more at `d = 3`. This is part of what E4 measures, not a defect.
- The p-uniformity monitor adapts to drift as reserved-slice rows arrive; under delay its calibration set is staler.
- The domain-classifier null is approximate for later references; its validity is checked on synthetic no-drift streams only.
- After a refit, the reference slot's sample can contain a few rows that are training rows of the model in force (about 0.8% of the slot at B = 1%). Their score logit in MMD is in-sample. The effect is about 2 of 200 rows and is accepted, not corrected (leakage review, Phase 9, note 8).
- The disk cache is keyed by window, hold-out fraction and a digest of the data source's provenance, under the code version. A dirty or unknown code version writes no disk cache (leakage review, finding 2).
- To revisit only through a new addendum: any threshold, sample size, k, component count or reference rule.

## Evidence and references
- `src/driftwatch/monitors/`, `src/driftwatch/sim/monitoring.py`, `tests/test_monitors.py` (change-point detection within 1 slot for all four; at most 6 alarms in 200 no-drift slots, run with `pytest -m slow`), `tests/test_runner_e4.py` (rule R, cache equality, runtime label spy).
- `scripts/monitor_synthetic.py` -> `reports/tables/e4_synthetic_checks.csv` (synthetic, never evidence): every monitor alarms in the shift slot in 5 of 5 change-point streams and never before it; no-drift alarm rate over 8 reference draws x 100 slots at alpha 0.01: KS 1.75% (one reference draw 7%), MMD 0.13%, domain classifier 0%, p-uniformity 0.13%. The KS rate is above nominal because one reference draw serves many slots (alarms are dependent given the reference); this is stated in addendum v3, not tuned away.
- PROTOCOL §3 (monitor quality), §4 (Mondrian p-value); ADR-0006 (threshold 0.5); ADR-0009 (calibration rows are not training rows).
