# Chapter 7: Experiments and results (draft)

> Status: draft written by Claude Code in Phase 6 for the researcher to rewrite, verify and defend. Every number carries a claim id from `docs/CLAIMS.md` (file and commit there). The analysis was registered before the grid was run (tag `prereg-v1`; chapter 3 explains the method); results are reported as measured, flat ones included. Wording follows the registered rule: a contrast is **detected** when its 95% interval excludes zero in the hypothesised direction, and "equivalent" means the whole interval lies within plus or minus 0.01 of A-AUT. **[researcher: verify]** marks sentences whose reading of a number you should check. E3 (selection) is added in section 7.5 once its rows are in the ledger.

## 7.1 What was run

| Experiment | What | Data | Status |
|---|---|---|---|
| E0 | Baselines: LR and LightGBM, never retrained, time-aware windows, A-AUT; random-split comparator | LAMDA, BODMAS | done (Phase 4) |
| E1 | Random split against time-aware per evaluation slot, both comparators | LAMDA, BODMAS | done (Phase 5) |
| E2 | Delay x budget grid under never and periodic(3) retraining, random selection | LAMDA, BODMAS | done: all 54 cells complete, none failed [E-26] |

All runs use the windows of ADR-0005 (LAMDA four training and twelve evaluation months, stride three; BODMAS three training and six evaluation two-week slots, stride two), a 10% target malware ratio per evaluation slot, a fixed threshold of 0.5, and the two models with the fixed hyperparameters of the registration [P-02, P-03]. Seeds are draws of the C3 subsample and of the selection (chapter 3).

## 7.2 E0 and E1: the time-aware baseline and the random-split gap (RQ1)

**Time-aware A-AUT with no retraining.** On BODMAS the logistic model scores 0.912 and LightGBM 0.977; on LAMDA 0.678 and 0.760 [E-02, E-03]. The same figures are reproduced by the E1 time-aware series and by the never arm of E2 [E-16, E-27, E-28]. The BODMAS values exceed 0.90, which the protocol treats as a leakage alarm until explained. The real-data canary passes on LAMDA and is inconclusive on BODMAS (no gap to close), unchanged when it was re-run on the final code [E-09, E-22]. BODMAS evaluates only 20 distinct two-week slots, about nine months in two stretches [E-12], and no explanation beyond that is claimed here **[researcher: verify and decide how to word the open alarm]**.

**The gap, under two definitions.** RQ1 registered the gap between random-split F1 and time-aware AUT against a band of 0.05, with the per-slot matched comparator as primary (ADR-0008). Both readings were seen before registration (CLAIMS E-19) and both are reported [E-35]:

| Dataset, model [E-35] | Per-slot matched gap (primary), 95% interval | Window-level E0 gap (secondary), 95% interval |
|---|---|---|
| LAMDA, LR | 0.0295 [-0.0125, 0.0768] | 0.1523 [0.0988, 0.1759] |
| LAMDA, LightGBM | 0.0403 [0.0240, 0.0481] | 0.1369 [0.0909, 0.1595] |
| BODMAS, LR | 0.0354 [0.0271, 0.0395] | 0.0282 [0.0135, 0.0382] |
| BODMAS, LightGBM | 0.0057 [0.0013, 0.0074] | -0.0002 [-0.0082, 0.0068] |

Under the primary comparator no cell reaches the 0.05 band, not even its point estimate; under the window-level comparator both LAMDA models are above it with the lower end of the interval above it too, and both BODMAS models are below. The two comparators differ in what they score (the window-level one includes held-out rows of the training-era slots and one global C3 draw), and the per-slot comparator reaches a lower malware ratio than the time-aware series on LAMDA [E-18, P-14]. The honest statement is that **the size of the gap depends on how the comparator is defined, that it is not established as large under the registered primary definition, and that the data do not show it to be caused by temporal leakage alone** [E-19].

## 7.3 E2: label delay and analyst budget (RQ2)

**Set-up.** Periodic retraining every third evaluation slot, labels arriving after `d` extra slots, a budget of 0.5%, 1%, 2% or 5% of the evaluated slot (about 22 to 218 labels per slot on LAMDA and 14 to 141 on BODMAS) [E-28, E-27], random selection, retraining on the initial window plus arrived labels. Absolute counts at 5%: LAMDA 218 labels queried per slot, 2,619 per window, of which 2,393 arrive before the window ends; BODMAS 141 per slot, 844 per window, 705 arrived [E-37].

**Cell values.** A-AUT on LAMDA moves from 0.679 (LR) and 0.760 (LightGBM) with no retraining to 0.694 and 0.781 with periodic retraining at 5% of the slot and no extra delay [E-28]. On BODMAS the same arms are 0.912 and 0.977 and 0.915 and 0.977 [E-27]. The full 4 x 4 grids, with the standard deviation over windows in every cell, are `reports/figures/e2_heatmap_lamda.png` and `e2_heatmap_bodmas.png`.

**Registered contrasts, 10 seeds.** Differences of A-AUT with 95% intervals; the two delay contrasts compare delay 0 with delay 3 [E-29, E-30]:

| Contrast [E-29, E-30] | LAMDA, LR | LAMDA, LightGBM | BODMAS, LR | BODMAS, LightGBM |
|---|---|---|---|---|
| C-D1, delay 0 minus 3 at 1% | 0.0032 [-0.0011, 0.0077] equivalent | 0.0046 [0.0025, 0.0057] detected, inside the margin | 0.0010 [-0.0001, 0.0023] equivalent | 0.0001 [-0.0005, 0.0008] equivalent |
| C-D2, delay 0 minus 3 at 5% | 0.0114 [0.0047, 0.0171] detected | 0.0131 [0.0083, 0.0151] detected | 0.0027 [0.0019, 0.0036] detected, inside the margin | 0.0001 [-0.0005, 0.0008] equivalent |
| C-P, periodic (d=0, 5%) minus never | 0.0168 [0.0071, 0.0243] detected | 0.0197 [0.0124, 0.0224] detected | 0.0027 [0.0019, 0.0036] detected, inside the margin | 0.0001 [-0.0005, 0.0008] equivalent |
| C-B, 5% minus 0.5% at d=0 | 0.0131 [0.0061, 0.0191] detected | 0.0165 [0.0104, 0.0187] detected | 0.0025 [0.0014, 0.0031] detected, inside the margin | 0.0012 [0.0001, 0.0020] detected, inside the margin |

On BODMAS the C-D2 and C-P columns are the same comparison: with one useful refit per window, periodic retraining at delay 3 equals never retraining by construction (chapter 3, section 3.7) [P-12]. They are therefore one finding, not two, and the BODMAS delay numbers measure a delay in a single refit. **[researcher: verify this reading of the BODMAS columns.]**

**In plain units.** On LAMDA at 5% of the slot (218 labels per slot) each extra slot of delay costs 0.0038 [0.0016, 0.0057] A-AUT for LR and 0.0044 [0.0028, 0.0050] for LightGBM; at 1% (44 labels per slot) the cost is 0.0011 [-0.0004, 0.0026] and 0.0015 [0.0008, 0.0019] [E-30]. The slope over the four delays at each budget grows with the budget on LAMDA for both models and on BODMAS for LR (for LightGBM on LAMDA 0.0007, 0.0016, 0.0026 and 0.0046 at 0.5%, 1%, 2% and 5%) [E-33]: more labels in flight means more is lost when they arrive late. Between neighbouring budgets on LAMDA, LightGBM gains 0.0166, 0.0081 and 0.0072 A-AUT per 100 extra labels per slot (0.5% to 1%, 1% to 2%, 2% to 5%); the concavity, gain 0.5% to 1% minus gain 2% to 5%, is 0.0095 [0.0029, 0.0144], diminishing returns detected. For LR the same concavity is 0.0033 [-0.0132, 0.0194], not detected [E-34].

**Reading against the hypotheses (RQ2).** On LAMDA the registered pattern is seen in both models at 5%: AUT falls with delay, rises with budget, and periodic retraining at 5% is above never retraining. At 1% the delay effect is detected for LightGBM (inside the margin) and not for LR. On BODMAS the effects are at most 0.003 A-AUT, inside the margin, and absent for LightGBM; the geometry limits what BODMAS can say. The effects on LAMDA are small in absolute terms: 0.011 to 0.020 A-AUT for contrasts whose arms differ by hundreds of labels per slot, against standard deviations over windows of about 0.05 to 0.07 [E-28]. They are measured with intervals that exclude zero, not with a claim that they matter operationally **[researcher: decide how to word the practical significance]**.

**Supporting checks.** The seed-level Wilcoxon p-values of the 16 primary contrasts and their Holm adjustment over the fixed family are in the ledger [E-31]; they are conditional on the realised windows and measure subsample noise only. The same four contrasts on seeds 0 to 4 [E-32], and at Chow's stride with fewer windows [E-36], agree in direction and size; the 5-seed rows are nested in the 10-seed set and are not a replication. At Chow's stride the LAMDA LR contrast C-P is not detected (0.0103 [-0.0016, 0.0207]), the only primary-type contrast that changes verdict.

**Recovery.** Drop events (a fall of 0.05 below the trailing three-slot mean) on LAMDA: LR 1.58 per window and seed series, recovered within the window in 73% of cases with no retraining and 81% with periodic retraining at 5%; LightGBM 1.40 and 1.46 events, recovered in 80% and 84%. On BODMAS drops are rare (LR 0.27 per series, recovered 38% both with and without retraining; LightGBM 0.03 to 0.07) [E-38]. These are descriptive counts.

**Failures and artifacts.** No cell failed and none was rerun. One LAMDA cell spanned an eight-hour computer standby; its wall time and one timed fit are artifacts, annotated in the ledger, and its predictions are unaffected [E-26].

## 7.4 What E2 does not show

See chapter 8, section 8.2. In particular: no delay curve on BODMAS, no independent replication on LAMDA (about four independent blocks), no statement about why a flat result is flat at the smallest budgets, and no result about selection or monitors.

## 7.5 E3: selection under delay (RQ3)

**[Added when the E3 rows are in the ledger; the registration is `docs/prereg/addendum-v2.md`.]**
