# Chapter 2: Landscape (draft)

> Status: draft written by Claude Code in Phase 5 for the researcher to rewrite, verify and defend. Sources retrieved on **2026-10-13**; descriptions taken from search-result summaries are marked [verify: read the source]. Project facts carry a CLAIMS id (docs/CLAIMS.md). No threat-landscape statistic is quoted here: any figure about how much malware exists or how fast it changes must come with a retrieved source and an access date before it enters this chapter [verify].

## 2.1 The problem in one paragraph

A learned malware detector is trained on samples seen up to a date and used on samples that arrive later. Both the malware and the benign software change, so the relation the detector learned (concept drift) holds less well as time passes. Random train/test splits mix past and future and hide this; evaluating strictly forward in time shows it. How long a detector stays useful then depends on what can be done after deployment: whether it can be retrained, on which labels, how late those labels arrive, how many an analyst can afford, and whether anything tells the operator when to retrain.

## 2.2 Concepts used in this report

- **Concept drift**: a change over time in the relation between inputs and the label the detector predicts (gama2014survey [verify: not yet in references.bib; see REFERENCES_TODO.md]).
- **Time-aware evaluation**: train on earlier data, test on strictly later data, in fixed time slots; the TESSERACT constraints C1 (train older than test), C2 (test slots hold data from their own time window) and C3 (test slots at the target malware ratio) make this concrete (pendlebury2019tesseract).
- **AUT**: area under the F1-versus-time curve over successive test slots; **A-AUT**: its average over rolling windows (ADR-0006).
- **Label delay**: the time between a sample being scored and its true label becoming known; in the simulator, `d` whole slots after the next one (chapter 6).
- **Analyst budget**: the number of samples whose true label can be obtained per slot.
- **Conformal drift monitor**: a score computed from how unusual a sample or batch is compared with calibration data, used to flag drift without waiting for labels (chapters 5 and, when implemented, 8 and 9).

## 2.3 Why Android and Windows PE

Android and Windows PE are the two platforms with open, time-stamped, pre-extracted feature datasets large enough for rolling-window evaluation and for which the same protocol can be applied without handling any binary. The study uses feature files only; no application or executable is opened, run or redistributed (hard rule 1, docs/ETHICS.md).

The platforms differ in ways that matter for the question asked here, and chapters 3 and 4 will have to say so with project data:

- **Time resolution.** LAMDA slots are calendar months; BODMAS slots are two weeks. Delay is therefore reported in months for LAMDA and in slots and days for BODMAS (PROTOCOL.md D2).
- **Time coverage.** LAMDA has a long, gappy timeline (CLAIMS W-01: usable months fall into 10 runs, the longest 62 months); BODMAS covers about thirteen months in two usable runs (CLAIMS W-02).
- **Feature type.** LAMDA features are sparse integer counts (CLAIMS D-02); BODMAS features are dense floats (CLAIMS D-07).
- **Timestamps.** LAMDA months come from the AndroZoo `added` field (CLAIMS D-03). The LAMDA paper says only "submission dates" and `year_month`, and its README says the year is when the APK "was added to AndroZoo repository"; neither names the AndroZoo CSV column, so the field is [verify] (checked 2026-10-20). BODMAS benign samples carry batch or placeholder dates, which the slicer excludes (CLAIMS D-08, D-14; ADR-0004).

## 2.4 The datasets

| Dataset | Platform | Size and classes | Source of the numbers | Licence |
|---|---|---|---|---|
| LAMDA | Android | 1,008,381 apps; 369,906 malware; 638,475 benign (Baseline subset) | CLAIMS D-01 | MIT |
| BODMAS | Windows PE | 134,435 samples; 57,293 malware; 77,142 benign | CLAIMS D-07 | BSD-2 (code repository; no dataset licence is stated on the project page, checked 2026-10-20) |
| EMBER2024 (optional, Tier 3) | Windows PE and other formats | not used in Phase 5 | arXiv 2506.05074, accessed 2026-10-13 [verify] | Apache-2.0 (confirmed on the dataset card, 2026-10-20) |

LAMDA is described by its authors as a longitudinal Android malware benchmark built to study concept drift, with about a dozen years of samples and no 2015 data (haque2025lamda; summary of 2026-10-13 [verify]). BODMAS is described as Windows PE malware and benign feature vectors collected over roughly thirteen months with curated family labels (yang2021bodmas). Both have duplicates and class-ratio properties that the slicer's constraints and the duplicate counts handle (CLAIMS D-05 for LAMDA).

## 2.5 What the datasets cannot tell us

- **They are not a measurement of label delay.** Neither dataset records when an analyst or a scanner first knew a label; the delay in this study is a simulated parameter, not an observed one. How realistic the range `d` in {0, 1, 2, 3} slots is, is a question for the discussion chapter [verify against Botacin and Gomes, botacin2025labeldelays].
- **They are not the population.** LAMDA's labels come from an existing aggregation of scanner verdicts, and BODMAS from a security company's database [verify: read each dataset's own account of labelling].
- **They are not adversarial.** The study measures decay under natural drift; it does not generate or evaluate evasion (hard rule 12).

## 2.6 Threat-landscape context

This section is intentionally left to the researcher. Statements such as "the number of new Android malware samples per year" or "the share of detections that rely on machine learning" need a retrieved source and an access date each. Candidates to retrieve and read: the platforms' own annual security reports, and the datasets' papers for their collection statistics. Nothing is quoted from memory [verify].
