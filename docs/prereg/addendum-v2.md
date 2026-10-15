# Pre-registration addendum v2: RQ3, selection under delay (E3)

**Status: DRAFT for the researcher's approval. It becomes the registered addendum only when the annotated tag `prereg-v2` exists on the commit that contains it, and that tag must predate the first E3 result (the first file under `results/e3/`).** The tag is created by the researcher's go and is never moved or deleted.

Scope: this addendum adds RQ3 to `docs/PREREG.md` (tag `prereg-v1`) and changes nothing registered there. Everything not stated here (windows, ratio, threshold, models, the two-stage bootstrap, the decision rule, the exclusion and failure rules, units) is as registered in v1.

## What was known when this was written

E2 had not finished (the BODMAS cells were partly complete and LAMDA had not started). **No E2 result had been read and no E3 run existed.** The E3 code was tested on synthetic streams only. If E2 results are read before this addendum is tagged, that must be stated here and in the CLAIMS ledger.

## Hypothesis (guide, RQ3)

The advantage of uncertainty or credibility selection over random selection shrinks as delay grows, because the selected samples are stale by the time their labels return.

## Design

- **Arms:** random, uncertainty (closest to 0.5), credibility (lowest Mondrian p-value of the predicted class). Retraining: periodic(3). Models: LR and LightGBM. Datasets: LAMDA and BODMAS.
- **Equal labels spent.** Every arm spends the same number of labels in every slot: a random reserved slice (share `calibration_fraction`, default 0.20 of the budget) plus the selector's choice. The runner asserts equality in every slot; the tables repeat the check.
- **Calibration data.** Only the initial time-ordered hold-out and the arrived labels of the reserved random slice. Rows a selector chose never enter the calibration buffer (a contamination test must fail otherwise). Calibration rows are not training rows (ADR-0009), and this holds for every arm, including random.
- **Initial model.** Fitted on the initial window minus its newest 20% of rows by time (the hold-out), for every arm. Consequently **E3 numbers are comparable only with each other, never with E2 absolutes.**
- **Recalibration.** Buffer of the most recent 1,000 arrived calibration rows (plus the hold-out initially); scores are recomputed under the model in force in every slot in which calibration rows arrived or the model was refitted; at least 20 rows of each class are needed, otherwise the previous calibration is kept and the skip is counted. Credibility selection falls back to random for a slot with no calibration and logs it.
- **Nonconformity score (primary):** one minus the model probability of the class. **Comparison score:** distance to the class centroid in the detector's feature space, centroids from the current training pool.
- **Prediction-set diagnostic:** sets `{c : p_c > 0.10}`; coverage is scored with the stored true labels (scoring only).

## Cells (reduced grid)

| Group | Cells per dataset | Seeds |
|---|---|---|
| Main | selectors {random, uncertainty, credibility} x delay {0, 3} x budget {1, 2}% x score probability, reserved share 0.20 = 12 | 0 to 4 |
| Reserved-slice ablation | credibility at d = 0, B = 2%, reserved share {0 (trap), 0.10, 0.40} (0.20 is in Main) = 3 | 0 to 4 |
| Score comparison | credibility at d = 0, B = 2%, centroid score = 1 | 0 to 4 |
| Extra seeds | the 12 Main cells again with seeds 5 to 9, on BODMAS; on LAMDA only if the researcher's hours allow | 5 to 9 |

BODMAS is run first. If hours or compute run short, LAMDA E3 is cut and E3 is reported on BODMAS only, and the report says so.

## Primary contrasts (per dataset x model, 4 strata)

For selector `S` in {uncertainty, credibility}, budget `B` in {1%, 2%}, delay `d` in {0, 3}: `adv_S(d, B) = A-AUT(S, d, B) - A-AUT(random, d, B)`, paired on windows and seeds.

- **Primary (RQ3):** the interaction `I_S(B) = adv_S(0, B) - adv_S(3, B)`. The hypothesis predicts a positive value. 2 selectors x 2 budgets = 4 per stratum, 16 in the family.
- **Secondary, descriptive:** the per-delay advantages `adv_S(d, B)` with their intervals and absolute label counts; the reserved-slice ablation (A-AUT difference to random, set coverage against 0.90, mean credibility, skipped recalibrations); the score comparison.

Decision rules, interval method, margin (0.01 AUT), Holm family (fixed size, missing contrasts at p = 1), exclusion rules and units are as in v1. The 0% reserved-slice arm is a **deliberate trap demonstration** and is labelled as such everywhere; it is not a candidate design.

## Known limits (written before the results)

- **BODMAS has one useful refit per window** (nE = 6, period 3). At d = 3 no label queried before it has arrived, so periodic equals never and `adv_S(3, B)` is zero by construction on BODMAS. The BODMAS interaction therefore equals `adv_S(0, B)` and is not a test of "shrinks with delay"; LAMDA is the informative dataset for RQ3 (three refit events per window). The report says so next to every BODMAS interaction.
- **Few labels.** At 1% to 2% of a slot, the selected labels are tens per slot; a difference between selectors may be below the resolution of the data.
- **Selection changes the pool class prior.** An uncertainty or credibility arm trains on a different class mix than random selection; the study reports the arrived class share per arm and does not correct for it.
- **Seeds are subsample draws** (C3 and selection), not independent replicates of a deterministic model.

## Exclusions and failures

As in v1: a failed cell is logged with its reason and never rerun because of its result; bugs found after the tag are fixed in a new commit with the affected cells invalidated and rerun.

## Not done in this addendum

No monitors (RQ4), no tuning of any value above after the tag, no re-implementation of HCC or Transcendent (cited as related work; selecting under a budget is not claimed as new).
