# Chapter 1: Introduction (draft)

> Status: draft written by Claude Code in Phase 7 for the researcher to rewrite in their own words and defend. Numbers enter only through `docs/CLAIMS.md` and carry their claim id. Paragraphs marked **[researcher: verify]** need your check against the sources. No experimental result is stated in this chapter; results are in chapter 7. Target length: about 5 pages.

## 1.1 Motivation

A malware detector is a program that decides, from features extracted from a file, whether the file is malware. It is trained once on samples collected up to some date and then used on samples that arrive later. Malware changes, and so does the benign software it hides among, so the pattern the detector learned fits later data less well. This loss of fit over time is called **concept drift**, and the time a detector stays useful before it has to be retrained is its **lifetime**.

Two things make the lifetime question harder than it first looks.

The first is evaluation. If a detector is tested on samples drawn at random from the same pool it was trained on, its score is high, because the test samples are close relatives of the training samples in time. If it is tested only on samples that are *newer* than everything it was trained on, its score is lower. The gap between the two is not a property of the detector; it is a property of how the test was built. The TESSERACT study showed this for Android malware and proposed three constraints for a fair experiment (pendlebury2019tesseract): **C1**, every training sample is older than every test sample; **C2**, each test slot holds malware and benign samples from the same time window; **C3**, the test data keep a realistic share of malware. A time-aware score such as AUT (the normalised area under the F1-versus-time curve) and its rolling-window version A-AUT make results comparable across studies (chow2025beyond).

The second is operations. A detector is not trained once. Analysts get a few suspicious samples per day or per week, label them by hand or in a sandbox, and the labels come back **late**: a sample seen today may only be labelled a week or a month later. The analysts' time is limited, so only a **budget** of samples per period can be labelled. In such a setting the practical questions are how much a delay costs, how much a larger budget buys, which samples to spend the budget on, and when to retrain at all.

## 1.2 Problem statement

This study asks how long a malware detector stays useful when labels arrive late and the labelling budget is fixed, under one time-aware protocol that is the same for every experiment. It adds a third ingredient, **conformal drift monitoring**: a method that turns a model's score into a p-value saying how unusual a sample is compared with labelled calibration samples, which can serve both to choose samples to label and to signal that the detector should be retrained. The report states what was measured; it does not claim that any approach is best.

## 1.3 Research questions

The questions and their registered analysis are in `docs/PREREG.md` (tag `prereg-v1` for RQ1 and RQ2; later addenda for RQ3 to RQ5). In plain words:

- **RQ1.** How large is the gap between the F1 of a randomly split test and the time-aware AUT(F1), for the same models on the same data?
- **RQ2.** How does A-AUT depend on label delay and analyst budget under never retraining and periodic retraining?
- **RQ3.** Does choosing samples by uncertainty or credibility still beat choosing at random when labels are late, at equal numbers of labels spent?
- **RQ4.** Does a drift monitor beat simple periodic retraining as a trigger?
- **RQ5.** Do the directions of the effects agree across Android and Windows PE data?

RQ1 and RQ2 are the Tier 1 questions of this report; RQ3 and RQ4 (Tier 2) and RQ5 (Tier 3) depend on the stop rules in `CLAUDE.md` and on what was finished, and the status is stated in chapter 8.

## 1.4 Contribution

> We study malware detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring in a single time-aware protocol, reported with A-AUT, on Android and Windows PE data.

That is the whole claim of the work. It is a statement of what was measured, not of priority: neighbouring work treats subsets of these ingredients (chapter 5 and `docs/related_work_addendum.md`), and the search behind that statement was limited. What the study adds is the combination in one protocol, the pre-registered grid, and a code base that reproduces its tables from stored predictions.

## 1.5 Scope, data and ethics

The study uses pre-extracted feature files only: LAMDA for Android, with 1,008,381 apps and about 37% malware [D-01]; and BODMAS for Windows PE, with 134,435 samples [D-07]. Both keep their own licences (`docs/ETHICS.md`). No malware sample, binary or decompiled code is downloaded, executed, opened or redistributed. The repository describes how detectors decay, not how to defeat them: it contains no evasion tooling and generates no adversarial examples.

Scope is divided in tiers. Tier 1 (E0 to E2) is the protocol, the random-versus-time comparison and the delay-by-budget grid, on both datasets. Tier 2 (E3, E4) adds conformal selection and monitors. Tier 3 (E5, E6) is optional. What was finished is stated in chapter 8 and `docs/PHASES.md`. **[researcher: verify the tier scope against your VISTAS submission and the stop-rule outcome at the time of writing.]**

## 1.6 Report outline

| Chapter | Content |
|---|---|
| 2 | The threat and detector landscape, in the terms used here |
| 3 | How results are analysed: metrics, contrasts, uncertainty and what the statistics cannot show |
| 4 | Recent techniques and attacks, from dated sources (first draft) |
| 5 | Related work, placed against delay, budget and conformal monitoring |
| 6 | The method: slicer, constraints, the label queue and the simulator |
| 7 | Experiments E0 to E2 and their results |
| 8 | Discussion, limitations and what the results do not show |

Terms are defined where first used; a reader who knows machine learning but not malware analysis should be able to follow every chapter.
