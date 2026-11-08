# E0 baselines (Phase 4)

Never-retrain detectors under the time-aware protocol, with a random-split comparator and the real-data leakage canary. Every number here has a row in docs/CLAIMS.md (E-01 to E-12, B-05). Results are stored under `results/` (not committed); the committed tables are `reports/tables/e0_baselines.csv`, `e0_per_slot.csv`, `e0_canary.csv`, `e0_repeats.csv` and `fit_times.csv`.

## What was run
- **Code and config.** Clean commit `cd72d83`; `driftwatch run configs/e0_bodmas.yaml` and `configs/e0_lamda.yaml`; seeds 0 to 4; LR and LightGBM `fast` with the hyperparameters of ADR-0006 and docs/PREREG.md; fixed threshold 0.5. Hashes in CLAIMS E-01.
- **Windows.** ADR-0005 (LAMDA nT 4, nE 12, stride 3: 16 windows; BODMAS nT 3, nE 6, stride 2: 6 windows), size gate M = 50, C3 at 10% with cap and flag. Secondary columns: Chow's stride `min(nT, nE)` (LAMDA 12 windows, BODMAS 4), the 5% sensitivity ratio (LAMDA 11 windows, BODMAS 6), and the single-run protocol (LAMDA 3 runs, BODMAS 2).
- **Comparator.** Each window's training and evaluation rows are pooled. The random training set has the time-aware window's size and its numbers of malware and benign rows; the test set is the rest, with malware subsampled by one cap over the pool to the target ratio. It violates C1 by design. The pooled-prior draw is stored beside it.
- **What the comparator does not match.** Only the training class counts and the overall test ratio are matched. Test malware is capped over the whole pool, not per slot, so months with very large malware dumps weigh more in the comparator than in the time-aware path, which caps each slot and weights months equally. The comparator's mean test ratio is 0.098 on LAMDA against 0.084 for the time-aware slots. The gap below is therefore "time-aware minus a time-blind evaluation", not a clean estimate of the effect of time alone; attributing it to temporal leakage in the random split (RQ1) needs a comparator matched per slot, which E0 does not have.
- **Published ranges.** The guide's sanity band is `[verify]` (not supplied; the PDF could not be decoded here). No published number is used as a target.

## Headline: A-AUT against the random split (10%, ADR-0005 windows)

| Dataset | Model | A-AUT(F1), mean ± std over windows | Random-split F1 | Gap, mean over windows | Gap, range over windows | Gap, 95% block bootstrap |
|---|---|---|---|---|---|---|
| LAMDA (16) | LR | 0.678 ± 0.058 | 0.831 | 0.152 | 0.041 to 0.244 | 0.100 to 0.175 |
| LAMDA (16) | LightGBM fast | 0.760 ± 0.070 | 0.897 | 0.137 | 0.046 to 0.302 | 0.091 to 0.160 |
| BODMAS (6) | LR | 0.912 ± 0.018 | 0.940 | 0.028 | 0.000 to 0.057 | 0.014 to 0.038 |
| BODMAS (6) | LightGBM fast | 0.977 ± 0.012 | 0.977 | -0.000 | -0.024 to 0.013 | -0.008 to 0.007 |

(CLAIMS E-02, E-03.) Means over five seeds; the std is the sample std over windows, averaged over seeds.

- **Seeds are not replicates.** The LR fit ignores the seed, so five seeds are five C3 malware draws (and comparator splits); LightGBM adds bagging. The spread across seeds (0.000 to 0.004 on the table) is small next to the spread over windows (0.01 to 0.10) and must not be read as precision.
- **Windows overlap** (a LAMDA slot is in 3.4 windows on average, BODMAS 1.8, and all 16 LAMDA windows come from one 62-month run), so there are roughly four independent 12-month blocks. The interval is a moving-block bootstrap with block length ceil(nE / stride) windows (LAMDA 4, BODMAS 3). It is descriptive; the per-window range is the more direct summary.
- **LAMDA:** the gap is positive in all 16 windows (0.04 to 0.30), with a mean of 0.14 to 0.15. **BODMAS:** 0.03 for LR and none for LightGBM.
- **Pooling.** AUT is a mean of per-slot F1; the comparator is one pooled F1. Where slot prevalence varies (LAMDA 2.6% to 10%) pooling favours the comparator by an estimated 0.01 to 0.02; on BODMAS all slots sit at 10% and the effect is about zero. This does not threaten the LAMDA result.

## Secondary columns (CLAIMS E-04 to E-07)

| Dataset | Model | Chow stride | 5% ratio | Single run | Gap vs pooled-prior comparator |
|---|---|---|---|---|---|
| LAMDA | LR | 0.683 ± 0.060 (12) | 0.625 ± 0.048 (11) | 0.720 (3 runs) | 0.154 (matched 0.152) |
| LAMDA | LightGBM | 0.761 ± 0.063 (12) | 0.743 ± 0.072 (11) | 0.784 (3 runs) | 0.139 (matched 0.137) |
| BODMAS | LR | 0.912 ± 0.023 (4) | 0.846 ± 0.034 (6) | 0.897 (2 runs) | 0.032 (matched 0.028) |
| BODMAS | LightGBM | 0.977 ± 0.015 (4) | 0.960 ± 0.024 (6) | 0.971 (2 runs) | 0.001 (matched -0.000) |

- A-AUT at Chow's stride is within 0.01 of the ADR-0005 headline in all four cases, so the stride difference (D18) does not move the result.
- The single-run values average runs of 3, 8 and 58 evaluation slots (LAMDA) unweighted; read them as a rough check only.
- The 5% ratio gives a lower A-AUT in all four cases. On BODMAS the windows are the same six, so the drop is a prevalence effect on F1. On LAMDA the 5% windows are different (11, from 2020-06) so the cause is not isolated.
- The two comparators differ by at most 0.005, but both share the global malware cap described above, so their agreement does not show that class prior is irrelevant to the time-aware path.

## Operating point (CLAIMS E-08)

| Dataset | Model | Mean FPR | Mean FNR |
|---|---|---|---|
| LAMDA | LR | 0.036 | 0.291 |
| LAMDA | LightGBM | 0.020 | 0.269 |
| BODMAS | LR | 0.017 | 0.035 |
| BODMAS | LightGBM | 0.004 | 0.014 |

- On LAMDA 29 of the 57 distinct evaluated months (51%) are below the 10% target and keep all their malware (45% of window-slot cells). F1 depends on prevalence (ADR-0005), so part of any F1 movement across months is prevalence.
- Training windows have very different class priors: 8% to 73% malware on LAMDA, 35% to 55% on BODMAS (rolling windows). With a fixed 0.5 threshold that is part of what the detector's FNR of 0.27 to 0.29 on LAMDA reflects.
- An example: LightGBM's F1 on LAMDA jumps from 0.49 (2023-10) to 0.91 (2023-11) without any retraining. The slot's ratio goes from 0.052 to 0.100, so this is prevalence, not recovery.

## Leakage checks
- **Canary (CLAIMS E-09).** LAMDA PASS: AUT with true timestamps 0.446, shuffled 0.632, random-split F1 0.631, closure 1.00, 4 windows. BODMAS NO_GAP (inconclusive, exit 3): 0.368, 0.358, 0.360, 6 windows. The canary uses a trivial nearest-centroid model; a flat BODMAS result says that model shows no decay there, not that LightGBM does not.
- **Exact repeats (CLAIMS E-10).** Rolling windows, LR, seed 0, counted per window-slot cell: 0 of 101,247 evaluated BODMAS rows repeat a feature vector of their training window; 52,985 of 838,012 (6.3%) LAMDA rows do. This is measured on the time-aware path only; it was not measured for the comparator's test sets, so no statement is made about the direction of its effect on the gap.
- **AUT above 0.90 on BODMAS.** The rule treats it as a leakage alarm until explained. Established: C1 to C3 are enforced checks that passed on every evaluated slot, and the slicer and the runner each had independent leakage reviews with no temporal leak found; no evaluated BODMAS row repeats a training vector; for LightGBM the random split scores the same as the time-aware path (for LR it is 0.03 higher). Not established: the cause of the high, flat score. The consistent reading is little drift over about nine evaluated months (20 two-week slots in two stretches, 2019-10 to 2019-12 and 2020-03 to 2020-09; January and February 2020 are lost to the benign placeholder exclusion and the size gate) with EMBER-style features. This has not been separated from an undetected artefact. G1.md carries it as an open alarm.

## Fit times and memory (CLAIMS B-05, E-01)
Largest training windows: BODMAS 17,873 rows, LAMDA 50,382 rows. Median fits: LR 1.4 s (BODMAS) and 2.6 s (LAMDA); LightGBM fast 3.5 s and 1.2 s; worst case 8.6 s (LightGBM default, BODMAS). The 60 s limit holds; no subsampling or grid shrink is needed. Peak resident memory of the full runs: BODMAS 1.40 GiB (cap 1.5 GiB, about 7% margin), LAMDA 0.90 GiB.

## Reproducibility (CLAIMS E-11)
Seed 0 of every variant, both datasets, was rerun from the same configs on the same commit and compared with `scripts/compare_runs.py`: per-cell prediction hashes and the comparator columns (random-split F1, its confusion counts, the pooled draw). Result in E-11.

## Limits
- The headline rests on LAMDA: one 62-month run with heavily overlapping windows. BODMAS gives about nine evaluated months.
- RQ1's attribution ("mostly from temporal leakage in the random split") is not tested by this comparator (see above).
- A fixed threshold of 0.5 with training priors from 8% to 73%: prevalence-corrected thresholds are not run (ADR-0006 option 1C).
- Recovery time is reported only as event counts and reads gradual decay badly (ADR-0006).
