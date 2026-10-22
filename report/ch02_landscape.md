# Chapter 2: Landscape (draft)

> Status: draft written by Claude Code for the researcher to rewrite, verify and defend. Fact-checked on **22 Oct 2026**: project facts carry a CLAIMS id (docs/CLAIMS.md) and every external statistic carries a literature row (L-nn) with its source and access date. Source descriptions are at abstract level (the full papers were not read). Items still open are marked [verify].

## 2.1 The problem in one paragraph

A learned malware detector is trained on samples seen up to a date and used on samples that arrive later. Both the malware and the benign software change, so the relation the detector learned (concept drift) holds less well as time passes. Random train/test splits mix past and future and hide this; evaluating strictly forward in time shows it. How long a detector stays useful then depends on what can be done after deployment: whether it can be retrained, on which labels, how late those labels arrive, how many an analyst can afford, and whether anything tells the operator when to retrain.

## 2.2 Concepts used in this report

- **Concept drift**: a change over time in the relation between inputs and the label the detector predicts (Gama et al., 2014; gama2014survey) [L-16].
- **Time-aware evaluation**: train on earlier data, test on strictly later data, in fixed time slots; the TESSERACT constraints C1 (train older than test), C2 (test slots hold data from their own time window) and C3 (test slots at the target malware ratio) make this concrete (pendlebury2019tesseract).
- **AUT**: area under the F1-versus-time curve over successive test slots; **A-AUT**: its average over rolling windows (ADR-0006).
- **Label delay**: the time between a sample being scored and its true label becoming known; in the simulator, `d` whole slots after the next one (chapter 6).
- **Analyst budget**: the number of samples whose true label can be obtained per slot.
- **Conformal drift monitor**: a score computed from how unusual a sample or batch is compared with calibration data, used to flag drift without waiting for labels (the literature in chapter 5, section 5.3; the four monitors of this study in chapter 6, section 6.12).

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
| EMBER2024 (Tier 3, not run) | Windows PE and other formats | not used | arXiv 2506.05074 [L-30] | Apache-2.0 (confirmed on the dataset card, 2026-10-20) [L-30] |

LAMDA is described by its authors as a longitudinal Android malware benchmark built to study concept drift, spanning 12 years (2013 to 2025, no 2015) [L-08] (haque2025lamda). BODMAS is described as Windows PE malware and benign feature vectors collected over roughly thirteen months with curated family labels (yang2021bodmas; CLAIMS D-07, D-08). Both have duplicates and class-ratio properties that the slicer's constraints and the duplicate counts handle (CLAIMS D-05 for LAMDA).

## 2.5 What the datasets cannot tell us

- **They are not a measurement of label delay.** Neither dataset records when an analyst or a scanner first knew a label; the delay in this study is a simulated parameter, not an observed one. Botacin and Gomes study delays caused by limited analysis queues (botacin2025labeldelays) [L-18]; this study does not take its range of `d` in {0, 1, 2, 3} slots from their data, and how realistic that range is, is a question for the discussion chapter.
- **They are not the population, and their labels are not ground truth.** LAMDA's labels come from VirusTotal detection counts: zero detections is benign, four or more is malware, and apps with one to three are discarded [D-15]. The dataset card calls the labelling AV-centric, and the scan date is not published, so a label may reflect knowledge later than the collection date [D-16]. This is a form of label leakage that the study cannot remove; chapter 8 lists it as a threat. BODMAS's own project page does not describe how its labels were produced [D-17] [verify: read the BODMAS paper].
- **They are not adversarial.** The study measures decay under natural drift; it does not generate or evaluate evasion (hard rule 12).

## 2.6 Threat-landscape context

Threat statistics date quickly and measure different things, so this study uses none of them in its analysis. One figure is given for scale. The AV-TEST Institute states on its malware statistics page that it registers "over 450,000 new malicious programs (malware)" each day, counting malware and potentially unwanted applications together; the page carries no data date and its per-year and per-platform charts are images, so no further figure is quoted [L-32]. A daily volume of that size is why a detector cannot be assumed to see only what it was trained on, and why the question of this report is about how long a detector stays useful, not whether it will meet unfamiliar samples. **[researcher: decide whether to add a platform-specific source for Android or Windows; none was retrieved.]**
