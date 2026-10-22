# Chapter 8: Discussion and limitations (partial draft)

> Status: draft written by Claude Code for the researcher to rewrite and defend; completed on 22 Oct 2026 for Tiers 1 and 2. The limits in sections 8.2 and 8.3 were written before the results (`docs/PREREG.md`, "Known limits") and are not softened by them. No number is stated here without a claim id (the cell counts are in section 8.5 [E-26, E-40, E-48]). Target length: six pages.

## 8.1 What was measured

The study applied one time-aware protocol to two feature datasets, LAMDA for Android and BODMAS for Windows PE, and measured how the A-AUT of two detectors changes with label delay, analyst budget, the choice of which samples to label, and the trigger for retraining. It also measured how large the gap is between a randomly split test and the time-aware score. Each experiment was registered before its first result (tags `prereg-v1` to `prereg-v3`) [P-17, E-48]. Below, "detected" means the 95% interval excludes zero in the hypothesised direction and "equivalent" means the whole interval lies within plus or minus 0.01 of A-AUT, as the registration defines them [P-10]; the words "confirmed" and "refuted" are not used. All differences are in A-AUT units.

**RQ1, the random-split gap.** Under the registered per-slot comparator the gap is 0.03 to 0.04 on LAMDA and 0.006 to 0.035 on BODMAS, below the 0.05 band (the LAMDA logistic-regression interval still contains 0.05); under the window-level comparator it is 0.14 to 0.15 on LAMDA [E-35]. The primary comparator was chosen after both numbers had been seen and is biased downwards on LAMDA [E-18]. What the intervals allow: a gap above the band is established under one definition and not under the other, and nothing in the design separates temporal leakage from the other differences between the comparators.

**RQ2, delay and budget.** On LAMDA, periodic retraining at 5% of the slot with no extra delay is above never retraining by 0.017 [0.007, 0.024] for logistic regression and 0.020 [0.012, 0.022] for LightGBM, detected in both; a delay of three slots at the same budget costs 0.011 [0.005, 0.017] and 0.013 [0.008, 0.015], detected in both [E-30]. The budget response is positive, and diminishing returns are detected in one stratum of four [E-30, E-34]. On BODMAS the differences are at most 0.003 [E-29] and the delay axis measures one refit, not a curve [P-12]. The effects are hundredths of A-AUT against standard deviations over windows of 0.05 to 0.07 [E-28], so the data resolve differences of about that size and no finer.

**RQ3, selection under delay.** On LAMDA, with ten seeds and 16 windows, the advantage of uncertainty or credibility selection over random selection at equal labels is 0.0109 to 0.0177 with no delay and 0.0015 to 0.0095 after three slots, and the registered interaction is positive, with intervals excluding zero, in all eight selector, budget and model rows, 0.0061 to 0.0118 [E-42, E-43]. The advantage was therefore smaller after a delay of three slots in this sample, in both models. It is not separated from the change in class mix that selection brings [E-47], the seeds beyond the first five were added after the five-seed rows were read [E-42], and on BODMAS the interaction equals the delay-0 advantage by construction [E-41]. The study does not show that credibility adds anything over uncertainty.

**RQ4, monitors as a retraining trigger.** None of the 32 monitor-minus-periodic contrasts has an interval above zero [E-59, E-60]. On LAMDA, logistic regression with the KS monitor is below periodic retraining at both delays (reversed), the only rows that reach past the 0.01 margin; the other rows are equivalent or lie below zero inside the margin [E-59]. At the same number of refits, the timing of the alarms made no difference larger than 0.01 on LAMDA, where timing could be tested [E-61]. The monitors alarmed in most slots and detected drops in F1 no better than alarming at random would [E-63]. What this allows: at a budget of 1% and one frozen alarm level per monitor, no monitor was better than retraining every third slot, and several were slightly worse. It does not show that monitors cannot help at another level or budget.

**RQ5, agreement across platforms.** Not run (Tier 3). The experiments of RQ1 to RQ4 were run on both platforms, but their geometries differ, so a comparison of directions and magnitudes was not registered and is not made here.

## 8.2 What the results do not show

These statements are the ones a reader is most likely to attribute to the study, and the registered design does not support them.

- **That the random-split gap is caused by temporal leakage.** The per-slot comparator reaches a lower malware ratio than the time-aware series on LAMDA [P-14], and the two registered comparators disagree about whether the 0.05 band is met on LAMDA [E-19]. The report states the gap under each definition and does not attribute it.
- **A delay curve on BODMAS.** With six evaluation slots and retraining every third slot, a BODMAS window has one useful refit, and at a delay of three periodic retraining equals never retraining by construction [P-12]. A BODMAS number about delay is a number about one refit.
- **Independent replication.** LAMDA's 16 rolling windows are about four independent twelve-month blocks, and logistic regression is deterministic given its training rows, so seeds are draws of the C3 subsample and of the selection, not replicates of the model [P-12]. The intervals are wide because of the registered two-stage design, which counts within-window variation twice; that is an argument from the design, not a measured coverage (chapter 3, section 3.4), and the window stage is coarse in strata with few windows.
- **That labels do not help when a flat result appears.** In the earlier diagnostic, retraining changed a small share of decisions at the smallest budgets [P-13]; a flat A-AUT at the smallest budget is the resolution of a few tens of labels per slot, not a finding that labels are useless.
- **More than a bounded statement about selection.** E3 is reported in section 7.5 with its own limits:
  - two delays only;
  - ten seeds on LAMDA, over about four independent blocks of windows;
  - a BODMAS interaction that equals the delay-0 advantage by construction;
  - a selector advantage that is not separated from the change in class mix of the arrived labels [E-47];
  - a trap arm whose A-AUT is confounded with not retraining [E-45].

  Its numbers are not comparable with E2 absolutes (ADR-0009).
- **That drift monitors help, or that they cannot.** E4 (section 7.6) found no monitor that beat periodic retraining at a budget of 1% [E-59, E-60]. The limits of that reading:
  - it covers one alarm level per monitor, frozen before the run;
  - the monitors alarmed in most slots [E-63], so where they saturate, the matched-count comparison does not test timing;
  - on BODMAS the contrasts rest on one useful refit per window.

  No monitor was tuned after the results (CLAUDE.md rule 10) [P-17]. E5 and E6 (Tier 3) were not run.
- **Anything about an adaptive adversary.** The datasets contain natural evolution only. A detector that decays slowly here is not thereby robust to evasion (chapter 4).
- **Results on other hardware.** Every cell was run on one laptop; numeric differences elsewhere are reported, not corrected (`docs/GRID.md`).

## 8.3 Threats to validity

1. **Time labels.** LAMDA is cut by AndroZoo's collection date, and BODMAS benign samples carry date-only or placeholder timestamps (`docs/data_cards/`). Slots are cut by first-seen date, which is not the date a sample was compiled or first seen in the wild.
2. **Class prior.** Slots below the target malware ratio were kept and flagged (cap and flag); on LAMDA a large share of months are below target [E-08]. A-AUT mixes slots at different ratios.
3. **Repeated feature vectors.** A share of evaluated rows repeats a vector from the training window [E-10], and bought labels can repeat in later slots; the share is counted per slot and the rows are kept.
4. **The pool design.** The pool is the initial window plus arrived labels, weight one, never truncated (ADR-0007), which mixes raw and subsampled rows. A different pool rule could change the budget response.
5. **Two models.** Logistic regression and LightGBM with fixed hyperparameters; no tuning was done and none is claimed to be optimal.
6. **E3 calibration set-up.** The initial calibration hold-out is the newest 20% of the initial window by timestamp, which can cut inside a slot (a deviation from ADR-0004 item 8; on BODMAS it can make the hold-out edge class-skewed). Duplicate feature vectors between calibration rows and the training pool are not counted, which can inflate p-values. The trap arm never retrains, so its A-AUT is not read as the cost of contamination (`docs/reviews/leakage-review-e3.md`).
7. **Evaluation by one metric.** AUT of the malware-class F1 hides the cost of benign flagging; FPR and FNR per slot are in the tables but are not part of the registered contrasts.
8. **Label noise and the VirusTotal threshold.** LAMDA's labels come from VirusTotal detection counts: no detections is benign, four or more is malware, and one to three are discarded [D-15]. The dataset card calls the labelling AV-centric, and the scan date is not published, so a label may reflect knowledge later than the collection date [D-16]. The study cannot remove this form of label leakage and did not inject label noise; how BODMAS's labels were produced is not described on its project page [D-17]. The effect of a stricter or looser threshold on the lifetime was not measured.
9. **Temporal luck.** Results are for one cut of time per dataset: LAMDA's 16 rolling windows are about four independent twelve-month blocks and BODMAS has six evaluation slots per window [P-12]. A different start date, a longer span or a different slot length could give different numbers; the registered secondary check at Chow's stride changes the window step only (chapter 7, section 7.3).
10. **Simulated delay.** Delay is a whole number of slots, the same for every label. Real delays differ by sample and depend on the analysis queue (Botacin and Gomes study exactly that [L-18]); the range of zero to three slots was not calibrated to an observed delay distribution, and neither dataset records when a label became known.
11. **A simulated perfect analyst.** A queried label is the dataset's own label, returned after the delay without error. A real analyst makes mistakes, disagrees with a scanner, and may not be able to label a sample at all; the budget counts labels, not analyst hours.
12. **Dataset mix.** The two datasets differ in platform, feature type, slot length (a month against two weeks), time span, class balance and the number of refit events per window. They are analysed side by side, never pooled, and a difference between them is not attributed to the platform.
13. **One alarm level per monitor.** E4 froze every monitor setting before the run and tested one level (ADR-0010). A monitor that alarmed in most slots is a result about that setting.

**[researcher: verify each of these against your own reading of the data cards; mark any you consider minor.]**

## 8.4 Ethics and scope

The repository contains no malware, no decompiled code and no evasion tooling, and generates no adversarial examples (`docs/ETHICS.md`). The datasets keep their licences; BODMAS's dataset licence is not stated by its authors and is an open question (`docs/PHASES.md`). Describing how detectors decay is not the same as describing how to defeat them, and the report keeps to the former.

## 8.5 Status of the tiers

Tier 1 (E0 to E2) is complete on both datasets: all 54 E2 cells ran and none failed [E-26]. Tier 2 (E3, E4) is complete on both datasets: 56 E3 cells and 76 E4 cells ran and none failed [E-40, E-48]. Gates G1 to G4 were decided PASS by the researcher from the evidence files (`reports/G1.md` to `reports/G4.md`, `docs/PHASES.md`). Tier 3 (E5, E6) was not run: the go checklist failed on the capstone deadline, which is early December 2026 (`reports/G5-tier3-decision.md`).

## 8.6 Future work

- A stratified within-slot random-split comparator, which would remove the ratio depletion of the per-slot comparator (ADR-0008).
- A longer BODMAS evaluation window, so that the delay axis has more than one refit (a new ADR).
- A circular or stationary block bootstrap as a sensitivity check on the registered window stage (an addendum before results are read).
- Drift monitors at lower alarm rates, for example with a larger sample per slot or a stricter significance level, registered in a new addendum before any run. Here E4 tested one frozen level, and most monitors alarmed in most slots [E-63].
- A trap arm whose released labels also train the model, so that contamination is separated from not retraining (an addendum before the rerun).
