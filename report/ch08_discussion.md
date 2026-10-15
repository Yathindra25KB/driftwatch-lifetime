# Chapter 8: Discussion and limitations (partial draft)

> Status: partial draft written by Claude Code in Phase 7 for the researcher to rewrite and defend. It is partial on purpose: the Tier 1 results of chapter 7 must be read first, and the paragraphs that interpret them are marked **[researcher: write after chapter 7]**. The limits below were written before the results (`docs/PREREG.md`, "Known limits") and are not softened by them. No number is stated here without a claim id. Target length: about 6 pages.

## 8.1 What was measured

The study applied one time-aware protocol to two feature datasets, LAMDA for Android and BODMAS for Windows PE, and measured how the A-AUT of two detectors changes with label delay and analyst budget under never and periodic retraining. It also measured how large the gap is between a randomly split test and the time-aware score, under two definitions of the comparator. The protocol, the contrasts and the decision rule were registered before the grid was run (tag `prereg-v1`).

**[researcher: write after chapter 7: one paragraph per research question, in the form "what was measured, with what resolution, and what the interval allows to say". Do not write "confirmed" or "refuted"; use "detected" and "not detected" with the half-width, as the registration does.]**

## 8.2 What the results do not show

These statements are the ones a reader is most likely to attribute to the study, and the registered design does not support them.

- **That the random-split gap is caused by temporal leakage.** The per-slot comparator reaches a lower malware ratio than the time-aware series on LAMDA [P-14], and the two registered comparators disagree about whether the 0.05 band is met on LAMDA [E-19]. The report states the gap under each definition and does not attribute it.
- **A delay curve on BODMAS.** With six evaluation slots and retraining every third slot, a BODMAS window has one useful refit, and at a delay of three periodic retraining equals never retraining by construction [P-12]. A BODMAS number about delay is a number about one refit.
- **Independent replication.** LAMDA's 16 rolling windows are about four independent twelve-month blocks, and logistic regression is deterministic given its training rows, so seeds are draws of the C3 subsample and of the selection, not replicates of the model [P-12]. The intervals are wide on purpose and are conservative by the registered two-stage design.
- **That labels do not help when a flat result appears.** In the earlier diagnostic, retraining changed a small share of decisions at the smallest budgets [P-13]; a flat A-AUT at the smallest budget is the resolution of a few tens of labels per slot, not a finding that labels are useless.
- **Anything about conformal selection or drift monitors.** Those experiments (E3 to E6) were not part of Tier 1 results. If E3 has been run, it is reported in its own section and its numbers are not comparable with E2 absolutes (ADR-0009).
- **Anything about an adaptive adversary.** The datasets contain natural evolution only. A detector that decays slowly here is not thereby robust to evasion (chapter 4).
- **Results on other hardware.** Every cell was run on one laptop; numeric differences elsewhere are reported, not corrected (`docs/GRID.md`).

## 8.3 Threats to validity

1. **Time labels.** LAMDA is cut by AndroZoo's collection date, and BODMAS benign samples carry date-only or placeholder timestamps (`docs/data_cards/`). Slots are cut by first-seen date, which is not the date a sample was compiled or first seen in the wild.
2. **Class prior.** Slots below the target malware ratio were kept and flagged (cap and flag); on LAMDA a large share of months are below target [E-08]. A-AUT mixes slots at different ratios.
3. **Repeated feature vectors.** A share of evaluated rows repeats a vector from the training window [E-10], and bought labels can repeat in later slots; the share is counted per slot and the rows are kept.
4. **The pool design.** The pool is the initial window plus arrived labels, weight one, never truncated (ADR-0007), which mixes raw and subsampled rows. A different pool rule could change the budget response.
5. **Two models.** Logistic regression and LightGBM with fixed hyperparameters; no tuning was done and none is claimed to be optimal.
6. **Evaluation by one metric.** AUT of the malware-class F1 hides the cost of benign flagging; FPR and FNR per slot are in the tables but are not part of the registered contrasts.

**[researcher: verify each of these against your own reading of the data cards; mark any you consider minor.]**

## 8.4 Ethics and scope

The repository contains no malware, no decompiled code and no evasion tooling, and generates no adversarial examples (`docs/ETHICS.md`). The datasets keep their licences; BODMAS's dataset licence is not stated by its authors and is an open question (`docs/PHASES.md`). Describing how detectors decay is not the same as describing how to defeat them, and the report keeps to the former.

## 8.5 Status of the tiers

Tier 1 (E0 to E2) is complete on both datasets, with the cells that failed, if any, listed in the ledger table of chapter 7. Tier 2 (E3, E4) and Tier 3 (E5, E6) status follows the stop rules in `CLAUDE.md` and the decisions recorded in `docs/PHASES.md`. **[researcher: update this section from PHASES.md at the time of writing.]**

## 8.6 Future work

- A stratified within-slot random-split comparator, which would remove the ratio depletion of the per-slot comparator (ADR-0008).
- A longer BODMAS evaluation window, so that the delay axis has more than one refit (a new ADR).
- A circular or stationary block bootstrap as a sensitivity check on the registered window stage (an addendum before results are read).
- Selection and monitors under delay (E3, E4) on the platform with more refit events per window.
