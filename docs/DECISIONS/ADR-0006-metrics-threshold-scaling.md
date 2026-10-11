# ADR-0006: Metrics, decision threshold, scaling policy, A-AUT windows and E0 hyperparameters

**Status:** PROPOSED. Values frozen on 2026-10-11, before any E0 AUT existed, when the researcher delegated the open choices ("do what feels best and logical"): LightGBM `fast`, fixed 0.5 threshold, ADR-0005 headline windows with Chow's stride secondary, sanity band left `[verify]`. Formal acceptance (PROPOSED to ACCEPTED) stays with the researcher at phase closeout; nothing below was chosen by looking at an AUT.
**Date:** 2026-10-11
**Deciders:** Yathindra (researcher, approves); Claude Code (engineering lead, proposes)
**Phase:** 4

This ADR fixes the open values "decision threshold, scaling policy, A-AUT window formula" in PROTOCOL section 5 and settles D5, D6 and D17. It also records the model hyperparameters that docs/PREREG.md lists before E0 runs. No E0 evaluation slot has been scored. The only model runs so far are timing and convergence probes on training windows (`scripts/bench_fit.py`), which print no scores.

## Context
- **Metrics (PROTOCOL section 3).** Per-slot F1 of the malware class, FPR and FNR at a fixed threshold, AUT, A-AUT, labels spent, recovery time.
- **AUT (D17).** The guide writes `AUT(f, N) = 1/(N-1) * sum (f_k + f_{k+1}) / 2`. The TESSERACT arXiv v4 comment (accessed 2026-10-11) says earlier versions of Eq. (4) carried an extra 1/N factor, a typo, and that the results rely on numpy's area under the curve.
- **A-AUT windows (Chow et al., arXiv 2506.23814v2, accessed 2026-10-11).** A-AUT is the mean and standard deviation of AUT over rolling windows (Eq. 1). For nE >= nT, training windows start every nT slots and `k = floor((|D| - nE) / nT)` (Eq. 2-4). For nE < nT (appendix A-E) windows advance by nE and `k = floor((|D| - nT) / nE)` (Eq. 6-8). Both are `stride = min(nT, nE)`. The paper does not say which standard deviation it reports.
- **ADR-0005 (accepted)** fixes LAMDA nT 4, nE 12, stride 3 and BODMAS nT 3, nE 6, stride 2. Chow's stride would be 4 and 3. nT > nE does not occur in either dataset.
- **Decision threshold (D5).** The guide says only "a fixed decision threshold". The Phase 4 prompt gives 0.5 and allows a tuned threshold only from the final training slot.
- **Recovery time (D6).** "Slots until F1 returns to 90% of its pre-drop level after a drop event" needs a drop-event rule; the guide gives one only "for example".
- **Training prevalence.** Training windows are raw (ADR-0004, ADR-0005): the largest windows are 63% malware (LAMDA) and 35% (BODMAS), and across the ADR-0005 rolling windows the training prior runs from 8% to 73% on LAMDA and 35% to 55% on BODMAS (measured in E0, CLAIMS E-08), while evaluation slots are at most 10%.

## Options considered

### 1. Decision threshold
- **A. Fixed 0.5 for every model, dataset and window** (default of the Phase 4 prompt).
- **B. Tuned on the final training slot.** Allowed by the prompt, but the model has already been fitted on that slot, so the threshold is in-sample unless the model is fitted on the earlier slots only; that changes what "the model" is.
- **C. Prior-shift corrected.** Move the threshold so that the decision is optimal at the evaluation ratio, from the training window's class balance and the C3 ratio only. No labels beyond the training window are used, but it is a different detector from a fixed 0.5.

### 2. Scaling for logistic regression
- **A. StandardScaler fitted in `fit` on the training window; centred only for dense features.** Sparse LAMDA stays sparse.
- **B. MaxAbsScaler.** Bounded on the training window, sparse-friendly, but squashes heavy-tailed EMBER-style features.
- **C. No scaling on LAMDA.** Counts 0 to 17 are on one scale already, but features then have unequal regularisation.

### 3. Spread of A-AUT
- **A. Sample standard deviation (ddof = 1)**, with the number of windows reported next to it.
- **B. Population standard deviation (ddof = 0).**

### 4. LightGBM profile in E0
- **A. `fast`** (63 bins, half the features per tree, 80% row bagging).
- **B. `default`** (library defaults).

## Decision (proposed)
1. **AUT** is the guide's formula, implemented as the mean of the trapezoids between consecutive slots (equal to `np.trapezoid(f, dx = 1/(N-1))`). A test pins the equivalence, the hand-computed examples and constant F1. AUT needs at least two evaluation slots.
2. **A-AUT** is `(mean, sample std over windows, n windows)`, option 3A. The headline windows are ADR-0005's. E0 also reports A-AUT at Chow's stride `min(nT, nE)` as a labelled secondary column (LAMDA 12 windows, BODMAS 4), so the figure is comparable with the literature's window geometry. The slicer reproduces Chow's windows exactly at that stride (test). Windows overlap, so the std understates uncertainty; effect sizes with bootstrap intervals over slots come in Phase 6.
3. **Threshold: fixed 0.5** (option 1A). A sample is called malware when P(malware) is strictly above 0.5. Any tuned threshold, now or later, may use only the final training slot and must be a new ADR. Option 1C is listed for the researcher: it would raise the threshold on training windows with a high malware share (up to 73% on LAMDA), and E0 shows how large that spread is. It is not used in E0.
4. **Scaling: option 2A.** Trees get no scaling. The scaler is created inside `fit` from the training rows only; a fitted model carries its window id, and scoring under another id raises. Zero-variance features are left unscaled and no clipping is applied. Dense features stay float32 (moments are accumulated in float64) to fit the 1.5 GB memory cap.
5. **Per-slot scores** are F1 of the malware class, FPR and FNR from the confusion counts of the slot after C3. A slot needs both classes (C2 guarantees it). **Labels spent** is the number of analyst queries; it is 0 in E0 and the initial training labels are reported separately as `n_train_rows`.
6. **Drop event and recovery (D6).** A drop at slot t is F1 at least 0.05 below the mean of the three slots before it; that mean is the pre-drop level. Recovery is the first later slot with F1 at least 0.90 of the level; the time is the number of slots from the drop. A drop that never recovers inside the window is censored. Events do not overlap: scanning resumes after a recovery and stops at a censored drop. In E0 (never retrain) recovery is reported only as a count of events and of recoveries.
7. **Random-split comparators (amended before any E0 result, after the leakage review).** For each window, the training and evaluation rows are pooled and the same models and hyperparameters are fitted on a random training set of the same size as the time-aware window; the rest is the test set, with malware subsampled to the same ratio by the same malware-only rule (C3, checked, counts stored). The comparator violates C1 by design: it is what a time-blind evaluation reports. Two draws are stored:
   - **`matched` (headline, column `f1_random_split`).** The training set has the same numbers of malware and benign rows as the time-aware window, so the class prior is identical and only time differs.
   - **`pooled` (secondary, column `f1_random_pooled`).** A plain random subset of the pool, whose class prior is the pool's. The first version of the runner had only this draw; the review noted that the gap against it mixes a prior effect with decay (the time-aware prior is the window's own, up to 63% malware on LAMDA 2013).

   Both compare a pooled F1 against the mean of per-slot F1 (AUT); this is the guide's comparison and is stated in the report. Neither is matched per slot: test malware is capped once over the whole pool, so months with very large malware counts weigh more than in the time-aware path (E0: comparator test ratio 0.098 against 0.084 on LAMDA). The gap is therefore "time-aware minus a time-blind evaluation", and RQ1's attribution to temporal leakage needs a per-slot-matched comparator that E0 does not provide.
8. **Hyperparameters (fixed here and in docs/PREREG.md, never tuned):**

   | Model | Values | Note |
   |---|---|---|
   | Logistic regression | L2, C = 1.0, lbfgs, tol 1e-4, max_iter 1000, no class weights, threshold 0.5 | sklearn defaults except max_iter (default 100). A convergence-only probe on LAMDA's largest training window (no scores printed) stopped at the 300-iteration cap and converged at 325, so the cap is 1000. A fit that reaches the cap is recorded as `converged = false`. |
   | LightGBM `fast` | 100 trees, learning rate 0.1, 31 leaves, min child samples 20, max_bin 63, colsample_bytree 0.5, subsample 0.8 with bagging every tree, deterministic, col-wise, 4 threads | Used in E0 (option 4A) |
   | LightGBM `default` | the library defaults: 100 trees, learning rate 0.1, 31 leaves, min child samples 20, max_bin 255, no sampling | Timed only |

   Seeds for E0 are 0 to 4 (guide section 10: 5 seeds for the grid). A seed fixes the C3 malware draw, the random split and the LightGBM bagging; the logistic fit does not depend on it, so one fit serves every seed.
9. **Fit time and memory** (bench, commit afa9b34, 8 cores / 16 threads, 7.25 GB RAM): at the largest training window the slowest configured fit is 3.5 s, so the 60 s rule holds with margin and no subsampling or grid shrink is needed (CLAIMS B-01, B-05). With the two comparators the random-split step peaked at 1.37 GB in the bench; the full BODMAS E0 run's resident peak was 1.40 GiB (about 7% under the 1.5 GiB cap) and LAMDA's 0.90 GiB (CLAIMS E-01).

## Consequences
- **Easier.** One metric module and one window formula that Phases 5 to 9 reuse. The slicer, the formula and the paper's worked examples agree under test.
- **Harder or riskier.**
  - **Prevalence shift.** A model fitted at 8 to 73% malware (LAMDA) or 35 to 55% (BODMAS) and judged at 10% or less with a fixed 0.5 threshold is not prevalence-adjusted. FPR and F1 on a 10% slot will look worse than on a balanced one. This is a property of the protocol and is reported, not tuned away (option 1C stays available as a later ADR).
  - **Rare-feature scaling.** Dividing a rare LAMDA feature by its small training-window standard deviation can give very large values at test time. It is a stated limitation of option 2A, not something patched after seeing results.
  - **Headline stride differs from Chow's** on both datasets. The secondary column exists so the difference can be read off.
  - **LightGBM results are guaranteed identical only for a fixed thread count**; the count is part of the config and the run record.
  - **Recovery time reads gradual decay badly.** The target is 0.90 of the pre-drop level, so a drop of 0.05 is already above it whenever the level exceeds 0.5, and recovery is "one slot" if the next slot is near the level. A slow decay of less than 0.05 below the 3-slot mean per slot yields zero events. For a never-retrain baseline, zero events must not be read as "no drift"; the AUT and the per-slot curve carry that.
  - **Overlapping windows and few BODMAS windows** make the std over windows and the bootstrap interval descriptive, not inferential.
- **Process note (11 Oct 2026).** A first E0 run started at commit 5893df7 was stopped before any of its output was read, because the leakage review found the comparator confound above and gaps in what the comparator stored. It was replaced by a run of the amended code; no result was seen or used to choose between the two.
- **Revisit when:** the researcher rejects a value; the Phase 4 real-data canary does not pass; Phase 5 fixes the training pool (ADR-0007), which may change the training prevalence; a package pin changes (rerun E0 under `maintain`).

## Evidence and references
- `tests/test_aut.py` (constant F1, hand-computed trapezoids, Chow Eq. 2-4, 6-10, slicer agreement), `tests/test_metrics_slot.py`, `tests/test_models.py`, `tests/test_runner_e0.py`.
- `reports/tables/fit_times.csv`, `scripts/bench_fit.py` (commit afa9b34).
- Chow et al., arXiv 2506.23814v2, HTML accessed 2026-10-11, section V and appendix A-E. Pendlebury et al., arXiv 1807.07838v4, comments field accessed 2026-10-11.
- ADR-0004, ADR-0005; PROTOCOL sections 2 to 5, D1, D5, D6, D17; Build Guide sections 3, 6, 9, 10.
