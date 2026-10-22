# Chapter 9: Conclusion and future work (draft)

> Status: draft written by Claude Code for the researcher to rewrite and defend; written 22 Oct 2026 from the ledger (`docs/CLAIMS.md`). Every number carries a claim id and is the same number as in chapters 7 and 8; this chapter adds no result. Target length: about three pages.

## 9.1 What was done

The study asks how long a malware detector stays useful when labels arrive late, the analyst budget is fixed and a drift monitor may decide when to retrain. It applied one time-aware protocol, with the TESSERACT constraints C1 to C3 as checks that raise and AUT and A-AUT as the metric, to two pre-extracted feature datasets, LAMDA for Android and BODMAS for Windows PE, with two detectors (logistic regression and LightGBM) at fixed hyperparameters. It built a simulator in which a label queried in one slot becomes usable only after a stated number of slots, and in which selectors, policies and monitors cannot read a held-back label; a spy test and a label-invariance test pin that. Four experiments were pre-registered before their first result (tags `prereg-v1`, `prereg-v2`, `prereg-v3`) and run to completion: the delay-by-budget grid (54 cells), selection under delay (56 cells) and drift monitors (76 cells), all without a failed cell [E-26, E-40, E-48].

> We study malware detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring in a single time-aware protocol, reported with A-AUT, on Android and Windows PE data.

That sentence is the whole claim. It states what was measured, not priority: neighbouring work treats subsets of these ingredients (chapter 5), and the search behind that statement was limited.

## 9.2 What was found

Each finding is stated as chapter 8 states it: with the interval, and without "confirmed" or "refuted".

- **The gap between a random split and a time-aware score depends on how the comparator is built.** It is below the 0.05 band under the registered per-slot comparator and 0.14 to 0.15 on LAMDA under the window-level comparator [E-35]. The study does not attribute the gap to temporal leakage alone [E-18].
- **Late labels cost something on LAMDA, and bought labels help a little.** At 5% of the slot, periodic retraining is above never retraining by 0.017 [0.007, 0.024] (logistic regression) and 0.020 [0.012, 0.022] (LightGBM); a delay of three slots costs 0.011 [0.005, 0.017] and 0.013 [0.008, 0.015] [E-30]. On BODMAS the differences are at most 0.003 [E-29], and its delay axis measures one refit [P-12].
- **Selection by uncertainty or credibility was above random selection in A-AUT, and the advantage was smaller after a delay.** On LAMDA the registered interaction is positive in all eight rows, 0.0061 to 0.0118 [E-42]. The advantage is not separated from the change in class mix [E-47], and the study does not show that credibility adds anything over uncertainty.
- **No drift monitor beat retraining every third slot.** None of the 32 monitor-minus-periodic contrasts has an interval above zero [E-59, E-60]; at the same number of refits, the timing of the alarms made no difference larger than 0.01 on LAMDA [E-61]; the monitors alarmed in most slots [E-63]. This is a negative result at one budget and one frozen alarm level, and it is a result.

## 9.3 What the study contributes

The contribution is the protocol, the open code and the pre-registered grid, not a better detector; and a set of small or null effects under stated settings, reported as such. "Lifetime" is read through A-AUT and the per-slot F1 curves. A count of slots until the mean F1 first falls by 0.05 is given only as an exploratory reading of the stored curves (section 7.7, [E-68]); it is not a registered result. A reader can rerun the tables from stored predictions without refitting a model (`scripts/make_tables.py`, `make_e3.py`, `make_e4.py`), check each number against `docs/CLAIMS.md`, which gives its file and commit, and see which choices were made before and which after seeing results (`docs/PREREG.md`, the addenda and the ADRs). The audits that sit behind the numbers are part of the contribution: a slicer mutation matrix in which every deliberately broken constraint is caught, leakage reviews of the simulator, the conformal layer and the monitors, and statistics reviews of each experiment, whose findings changed the text (for example the matched-count control of E4 is reported as not testing timing where a monitor alarms in every slot [E-61, E-62]).

## 9.4 Limits that apply to every finding

The effects are small, in hundredths of A-AUT, against standard deviations over windows of 0.05 to 0.07 [E-28]; LAMDA's windows are about four independent blocks and seeds are draws of a subsample, not replicates [P-12]; BODMAS has one useful refit per window. Delay is a simulated whole number of slots, the analyst is perfect, and the labels are VirusTotal-based on LAMDA with an unpublished scan date [D-15, D-16]. Chapter 8 lists these and the others. They bound what a reader may take from the numbers; they do not soften the numbers.

## 9.5 Future work

Each item below needs a new pre-registration before any run, because a change made after seeing results would no longer be a test.

- **E5, a cross-platform comparison** under a rule written in advance for what counts as disagreement, and **E6, EMBER2024**, whose challenge set of files that evaded antivirus products could motivate the delay range [L-30]. Neither was run: the capstone deadline removed Tier 3 (`reports/G5-tier3-decision.md`).
- **Drift monitors at other settings**: a larger sample per slot, a stricter significance level, or a monitor whose reference is chosen differently, with the alarm rate reported next to precision [E-63].
- **A longer BODMAS evaluation window**, so that the delay axis has more than one refit (a new ADR).
- **Label noise and measured delay**: injecting label noise at a stated rate, and replacing the simulated delay by an observed delay distribution if one can be obtained [L-18].
- **A trap arm whose released labels also train the model**, so that calibration contamination is separated from not retraining [E-45].
- **Controls for class prior**: a random baseline matched to the malware share of the selected labels and a threshold-free score such as the area under the precision-recall curve, both computable from stored predictions [E-66, E-47].
- **A registered lifetime measure**: section 7.7 reads the number of slots until the mean F1 first falls 0.05 below its first value from the stored curves, as an exploratory description [E-68]. A registered version would fix the threshold and the start slot in advance, use per-window curves and give an interval.
- **A monitor that uses labels**: a Transcend-style credibility monitor with label-conditional p-values, which the label queue can supply only after the delay [L-12, L-14].
- **A comparator keyed by seed and time span alone**, and a deposit of the stored predictions with hashes, so that RQ1 and every table can be rebuilt without the original disk [E-24].
- **A stratified within-slot random-split comparator**, which would remove the ratio depletion of the per-slot comparator (ADR-0008) [E-18].

## 9.6 Reproducibility and release status

The repository holds the code, the configs, the tables, the figures, the claims ledger, the registrations and the decision records; it holds no dataset content except a synthetic fixture. `driftwatch reproduce table1` reproduces the first table on BODMAS; on a clean clone the time-aware columns matched to four decimals and the random-split columns within 0.006 [E-24]. The result files under `results/` are not committed; the tables are, and they regenerate from stored predictions. A workshop paper, a documentation site and a package release are not part of this report; they come after the capstone deadline, and each irreversible step waits for the researcher's explicit go (`docs/PHASES.md`).
