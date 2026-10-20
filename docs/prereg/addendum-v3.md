# Pre-registration addendum v3: RQ4, drift monitors and retraining (E4)

**Status: DRAFT, not approved. It is registered by the annotated git tag `prereg-v3` once the researcher approves it; UNLOCKED only until that tag exists.** The tag, not this line, is the lock. It must predate the first E4 result (the first file under `results/e4/`). It is never moved or deleted.

Scope: this addendum adds RQ4 to `docs/PREREG.md` (tag `prereg-v1`) and `docs/prereg/addendum-v2.md` (tag `prereg-v2`) and changes nothing registered there. Everything not stated here is as registered in v1 and v2: windows, ratio, threshold, models, the conformal layer, the two-stage bootstrap, the decision rule, the exclusion and failure rules, and units.

## What was known when this was written

- E0 to E3 are complete and have been read (CLAIMS E-01 to E-43). E3 shows how the random arm behaves on the conformal path, and E4's periodic arm uses the same configuration.
- No E4 run on real data exists.
- The monitor code was tested on synthetic streams only: `tests/test_monitors.py`, `tests/test_runner_e4.py`, `scripts/monitor_synthetic.py`.
- Two monitor designs were changed after the synthetic no-drift checks failed them, before any real-data run (ADR-0010):
  - p-uniformity: the one-sample KS against U(0, 1) was replaced by a two-sample KS against the calibration scores.
  - MMD: the reference-only standardisation was replaced by a pooled standardisation.
- A real-data smoke run (one seed, one window per cell, all 19 cells per dataset, 20 Oct 2026) measured only time, memory and failures. Its F1 values were not read.
  - Every cell completed.
  - Peak memory was 0.91 GB on BODMAS and 0.57 GB on LAMDA, under the 1.5 GiB cap.
  - The longest single fit was 2.5 s, so no fit approaches the 60 s rule.
  - The grid's extrapolation is 3.0 h for BODMAS and 8.8 h for LAMDA. This is an upper bound: smoke runs keep no disk cache, so the domain classifier's null is refitted in every cell, while evidence runs fit it once per window and share it.
  - During the smoke runs, the domain classifier's solver was changed from liblinear to lbfgs for cost (ADR-0010).

## Hypothesis (guide, RQ4)

Periodic retraining is a hard baseline. Monitor-triggered retraining may fail to beat it. A negative or flat result is reported as it is.

## Design

- **Arms.** All arms run on the E3 conformal path:
  - random selector, reserved share 0.20 of the budget;
  - probability score, hold-out 0.20, calibration buffer 1,000;
  - minimum 20 rows per class (v2 values).

  Every arm therefore queries the same rows in every slot, so **labels spent are equal by construction**. The tables check this slot by slot and stop on a difference. The arms are:
  - `never`;
  - `periodic(3)`, which is E3's random arm;
  - `monitor-m`, for each monitor m;
  - `matched-m`, the matched-retrains control for each monitor m.
- **Models and data.** LR and LightGBM (v1 hyperparameters), LAMDA and BODMAS, A-AUT windows as in v1.
- **Budget and delays.** B = 1% of the evaluated slot; delay d ∈ {0, 3}.
- **E4 numbers are comparable with E3's random arm, never with E2 absolutes.**

### The four monitors (one interface: `update(slot view, state) -> alarm`)

Frozen values, ADR-0010:

| Monitor | Input (no labels of evaluated slots) | Test | Alarm |
|---|---|---|---|
| KS | the 20 features with the largest absolute standardised class-mean difference on the window's proper training rows (initial window, its own labels), fixed per window; 500 vs 500 rows | two-sample KS per feature, Holm over the 20 | smallest adjusted p ≤ 0.01 |
| MMD | TruncatedSVD (16 components) fitted without labels on the proper training rows, plus the logit of the model's malware probability; pooled standardisation; RBF kernel, pooled median-heuristic bandwidth; 200 vs 200 rows | 199 seeded permutations | p ≤ 0.01 |
| Domain classifier | raw features, 500 vs 500 rows | LR (C = 1, lbfgs, 200 iterations, scaled per fold), 5-fold stratified CV AUC; null of 99 random-label splits of the initial reference, computed once per window | p = (1 + #{null ≥ AUC}) / 100 ≤ 0.01 |
| p-uniformity | label-free conformal scores `1 − max(P, 1 − P)`, Mondrian by predicted class; calibration = features of the arrived calibration rows | two-sample KS of the slot's scores (500 rows) against the calibration scores per predicted class, Bonferroni over classes | p ≤ 0.01; undecided (counted, no alarm) if a predicted class has fewer than 20 calibration rows |

Every subsample, permutation and fold is seeded by (seed, window, slot) only.

**Reference (rule R).** The initial reference is a 500-row seeded sample of the window's time-ordered hold-out. After a refit, the reference becomes the sample of the newest evaluation slot whose labelled rows were in the pool at that fit, which is at most `s − 1 − d`. Arms that never refit keep the initial reference.

### Policies

- **Monitor-triggered.** The monitor runs on slot `s` after `s` is scored. An alarm makes a retrain event before slot `s + 1` when at least **min_gap = 2** slots have passed since the last actual refit. The initial model counts as a refit at slot 0.
- **Alarm with no new labels.** If no new label has arrived, the event is a logged no-op.
- **Alarms are never carried.** An alarm is consumed at the next slot whether it refits, makes a no-op or is blocked by the gap.
- **Matched-count control.** For each (window, seed, model), k is the monitor arm's number of actual refits. The k events are placed evenly over slots `1 + d .. nE − 1`: event j is at `first + floor((j + 1)·n / (k + 1))`. They are chosen without looking at data. Events with no new label are no-ops, so the control can refit fewer times than k. Its refit count is reported.

## Cells (reduced grid), per dataset

| Cell | Count | Seeds |
|---|---|---|
| never, with all four monitors observing (primary monitor quality) | 1 | 0 to 4 |
| periodic(3) at d ∈ {0, 3} | 2 | 0 to 4 |
| monitor-m at d ∈ {0, 3}, m ∈ {KS, MMD, domain classifier, p-uniformity} | 8 | 0 to 4 |
| matched-m at d ∈ {0, 3} | 8 | 0 to 4 |

That is 19 cells per dataset and 38 in all. **Seeds 5 to 9** for all 19 cells run only if the researcher says so. The same seed and cell rules as E3 apply. BODMAS runs first.

**Shrink order**, if compute runs short and before any claim is cut:
1. LAMDA seeds stay 0 to 4.
2. Drop d = 3 on BODMAS (where periodic equals never at d = 3).
3. Cut LAMDA E4 and report BODMAS only, saying so.

## Primary contrasts (per dataset × model)

A positive value favours the monitor.

- **M-P(m, d)** = A-AUT(monitor-m, d) − A-AUT(periodic(3), d). This is the comparison at matched labels spent: 4 monitors × 2 delays = 8 per stratum, 32 in the family.
- **M-C(m, d)** = A-AUT(monitor-m, d) − A-AUT(matched-m, d). This is the comparison at a matched number of retrains, and it isolates timing: 8 per stratum, 32 in the family.

The decision rule, the interval method (v1 two-stage bootstrap, 10,000 replicates, bootstrap seed 20261215) and the 0.01 AUT margin are as in v1. Wilcoxon on per-seed paired means is a supporting check only, with Holm **within each family** (32; a missing contrast counts as p = 1). With 5 seeds the smallest two-sided Wilcoxon p is 0.0625, so no Holm-adjusted p can fall below 0.0625. Every row shows A-AUT, labels spent per window and refits per window for both arms.

**Answer to RQ4.** Monitors are said to beat periodic retraining only for the (dataset, model, monitor, delay) cells where M-P is detected positive. Otherwise the report says periodic is not beaten at this resolution and gives the interval half-widths. No pooled claim is made across datasets or models.

## Monitor quality (secondary, descriptive)

The measure is alarm precision, alarm recall and detection delay against drop events defined from true labels:
- **Drop event:** F1 at least 0.05 below the trailing 3-slot mean, the PREREG v1 recovery-time definition (`metrics.slot.drop_events`).
- **Match:** an alarm at `s` matches a drop at `t` when `t ≤ s ≤ t + 2`.
- **Precision:** computed over alarms at slots ≥ 3.

Intervals use the two-stage bootstrap of the per-(window, seed) counts, with ratios of pooled counts. The primary context is the never cell (all four monitors observing, fixed reference). The secondary context is each monitor arm's own alarms against its own F1. Alarm rate per slot and the undecided share are reported beside these.

## Known limits (written before the results)

- **BODMAS geometry.** nE = 6, so periodic(3) has one useful refit, and at d = 3 periodic equals never. Monitors can refit from slot 2 (min_gap 2). On BODMAS, M-P is therefore partly a "more refits" contrast; M-C isolates timing. The report says so next to every BODMAS M-P.
- **False alarms given one reference.** Under no drift, the rate is nominal on average over reference draws. A fixed reference makes alarms within a window dependent, so in a given window the rate can be higher: in the synthetic check, KS ran at 1.75% pooled and 7% for one reference draw (ADR-0010). The never-cell alarm rate is reported beside precision.
- **Large slots.** Real slots are large and real drift is common, so the tests may alarm in most slots. If they do, monitor-triggered retraining reduces to "retrain every 2 slots", and M-P measures retrain frequency more than detection. The alarm rate is reported, and the thresholds are not changed.
- **The matched-count control is non-causal.** It learns at the start of a window how many refits its monitor arm made in that window, which depends on later slots. It carries one count per window and no timing or labels. It favours the control, so M-C is conservative for the monitor and cannot inflate a monitor's advantage. The control can refit fewer times than k when an event finds no new label. M-C rows report the share of windows with such a shortfall and its mean.
- **Monitor quality is a reading of association.** A drop event is a fall in F1 of the model in force. A monitor that sees covariate shift with no F1 fall counts as a false alarm.
- **Few labels.** At 1% of a slot, refits change few decisions (E1 diagnostic, CLAIMS E-13 to E-15). Flat contrasts are plausible.
- **Seeds are subsample draws** (C3 and selection), not independent replicates.

## Exclusions and failures

As in v1:
- A failed cell is logged with its reason and is never rerun because of its result.
- Bugs found after the tag are fixed in a new commit, the affected cells are marked invalidated and exactly those are rerun.
- If a matched cell's source monitor cell failed, the matched cell is reported as not computed, together with its source's reason.

## Not done in this addendum

- No tuning of any value above after the tag.
- No other monitors (ADWIN, DDM and other label-based detectors are out of scope: they need labels).
- No monitor-triggered *labelling*: the budget is spent every slot, as in v1.
- No re-implementation of Transcendent or HCC.
