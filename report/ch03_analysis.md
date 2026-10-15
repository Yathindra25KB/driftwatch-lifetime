# Chapter 3: How the results are analysed (draft)

> Status: draft written by Claude Code in Phase 6 for the researcher to rewrite, verify and defend. This chapter describes the analysis that was registered before any grid result existed (`docs/PREREG.md`, tag `prereg-v1`, 15 Oct 2026) and the code that implements it (`src/driftwatch/metrics/stats.py`, `grid_tables.py`, `scripts/make_tables.py`). It contains no experimental result. Protocol constants carry a claim id from `docs/CLAIMS.md`. Paragraphs marked **[researcher: verify]** are choices you should check against your own reading of the sources. The guide does not define this chapter beyond its name; I treated it as the chapter that explains how to read the numbers in chapter 7.

## 3.1 What is being compared

Every experiment in this study compares *arms*. An arm is one detector policy under one set of conditions: for example "logistic regression, retrained every three slots, labels arriving after one extra slot, 2% of each slot bought". Two arms are compared on the same data: the same windows, the same slots and the same seeds, so that the only difference between them is the condition under study. Arms that differ in what they train on still see the same test rows, because the evaluation slots and their malware subsampling (constraint C3) depend only on the seed and the slot, not on the arm [P-01].

The unit of data is the **window**: a few training slots followed by a few evaluation slots (LAMDA four and twelve, BODMAS three and six [P-02]). A model is trained on the first part and used on the second, one slot at a time (chapter 6). Windows overlap: consecutive windows share evaluation slots. This matters for every statement about uncertainty in section 3.4.

## 3.2 The quantities

- **F1 per slot.** The F1 score of the malware class on one evaluation slot, computed from the stored true labels and the stored decisions at the fixed threshold 0.5 [P-03]. Chapter 7 recomputes it from `predictions.parquet`; the slot table written during the run is only a cross-check, and the table code refuses a result in which the two disagree.
- **AUT.** The normalised area under the per-slot F1 curve inside one window, by the trapezoid rule: `AUT = 1/(N-1) * sum (f_k + f_(k+1)) / 2` [P-04]. A value of 1.0 means no decay at all; it is not "accuracy". AUT needs at least two evaluation slots, so a window with fewer is excluded and counted.
- **A-AUT.** The mean of AUT over the rolling windows, reported with the standard deviation over windows (ddof 1) [P-04]. When a quantity is averaged over seeds it is averaged inside each window first, so that a window counts once however many seeds were run.
- **Labels spent.** The number of labels requested. Budgets are percentages of the evaluated slot, but the report always shows the absolute count next to the percentage (a slot holds a few thousand rows, so 0.5% to 5% is tens to a couple of hundred labels per slot [P-05]).
- **Recovery time.** Slots until F1 returns to 90% of its level before a drop, where a drop is a fall of at least 0.05 below the mean of the previous three slots. It is descriptive only, and a drop that never recovers inside the window is counted as not recovered [P-06].

## 3.3 What the contrasts are

A **contrast** is a difference of A-AUT between two arms that differ in one condition. The registered primary contrasts, for each dataset and each model [P-07]:

| Id | Question | Plus arm minus minus arm |
|---|---|---|
| C-D1 | What does late labelling cost at a small budget? | periodic, delay 0, 1% **minus** periodic, delay 3, 1% |
| C-D2 | The same at a larger budget | periodic, delay 0, 5% **minus** periodic, delay 3, 5% |
| C-P | Does retraining on bought labels beat never retraining? | periodic, delay 0, 5% **minus** never |
| C-B | What does a larger budget buy? | periodic, delay 0, 5% **minus** periodic, delay 0, 0.5% |

Everything else (the full grid of delay and budget, the slope over four delays, the shape of the budget response) is descriptive and is labelled so. No claim is made about a single cell of the grid.

## 3.4 Uncertainty: why windows come first

If the 16 LAMDA windows were independent, a plain bootstrap over windows would be enough. They are not: with a window of twelve evaluation slots advancing by three, each slot appears in about four windows, so the 16 windows hold roughly four independent twelve-month blocks. A bootstrap that treated them as independent would be too confident. The analysis therefore resamples in two stages [P-08]:

1. **Windows, in blocks.** Windows are put in time order and resampled as blocks of consecutive windows, each as long as the number of windows that share a slot (`ceil(nE / stride)`: four on LAMDA, three on BODMAS). This keeps the dependence between neighbours inside each resampled block.
2. **Seeds, inside each window.** Within every selected window the seeds are resampled with replacement. A seed here is a different draw of the C3 subsample and of the random selection; for logistic regression, which is deterministic given its training rows, seeds are not independent replicates of the model, only of those draws.

Both arms of a contrast are cut with the same indices, so the contrast is paired window by window and seed by seed. The interval is the 2.5th to 97.5th percentile of 10,000 replicates with a fixed bootstrap seed [P-08].

The two stages count within-window variation twice, so the interval is wider than a plain standard error would give: about the square root of two wider when seed noise dominates (checked on independent synthetic cells in `tests/test_stats.py`). That was accepted when the analysis was registered. It is the cautious direction for a study that is meant to report flat results as they are. **[researcher: verify the sentence about double counting against a reference on two-stage (cluster) bootstraps before you cite it.]**

## 3.5 Effect sizes in plain units

An A-AUT difference of 0.02 is hard to interpret on its own. The report also states each contrast in the unit a practitioner would use [P-09]:

- **AUT lost per slot of delay**: the delay contrast divided by the three slots between the two delays, and, as a second estimate, the least-squares slope of A-AUT over the four delays at a fixed budget.
- **AUT gained per 100 extra labels per slot**: the difference of A-AUT divided by the difference in the mean number of labels bought per slot, times 100. The report gives the absolute counts on both sides, so the unit can be checked.

The unit of C-P is the same, with the never arm at zero labels.

## 3.6 The decision rule, and the equivalence margin

A contrast is called **detected** in a stratum (one dataset, one model) when its 95% interval excludes zero in the direction that was hypothesised [P-10]. Otherwise it is "not detected", and the half-width of the interval is the *resolution*: the size of effect the data could have shown. When the whole interval lies inside plus or minus 0.01 of A-AUT, the result is reported as "no change larger than 0.01"; the margin was set before the results, as an estimate, and is not tuned [P-10]. A contrast that was not detected is a result, not a failure to be repaired by adding seeds or windows.

The Wilcoxon signed-rank test on the per-seed paired means is reported only as a supporting check. With five paired seeds the smallest p-value it can return is 0.0625, and with ten it is about 0.002 [P-11]; the registered family of sixteen primary contrasts is adjusted with the Holm step-down method. No decision uses it.

## 3.7 What these statistics cannot show

These limits were written before the results (`docs/PREREG.md`, "Known limits") and apply whatever the numbers turn out to be [P-12].

- **Windows are not independent and there are few independent blocks.** Intervals are wide on LAMDA and the BODMAS evidence rests on six overlapping windows of one short period.
- **BODMAS has one useful refit per window.** With six evaluation slots and retraining every third slot, the single refit comes before the third slot. At a delay of three nothing queried before it has arrived, so periodic retraining equals never retraining by construction. The BODMAS delay axis is a delay in one refit, not a delay curve.
- **The labels are few.** Retraining changed 0.2% to 2.1% of decisions in the earlier diagnostic [P-13]. A flat result at the smallest budget does not show that labels do not help.
- **Repeated feature vectors.** A vector that was bought in one slot and reappears in a later slot is already in the pool. The share of rows that repeat a pool vector is reported per slot; the rows are not removed [P-12].
- **The random-split comparator is a different instrument.** The gap used for RQ1 is a difference of two evaluation procedures, and the comparator reaches a lower malware ratio than the time-aware series on LAMDA [P-14]. The report states the gap and does not call it a leakage-only quantity.
- **One platform per result.** Every cell was run on one machine; numbers from another machine may differ in the last digits, and that is reported, not corrected.

## 3.8 Reading chapter 7

Each table in chapter 7 gives, for a contrast: the estimate, its interval, the unit value, the absolute label counts, the number of windows and seeds, and whether the registered rule called it detected. A table never gives a bare percentage of a budget without its count. Cells that failed are listed with their reason and are not replaced.
