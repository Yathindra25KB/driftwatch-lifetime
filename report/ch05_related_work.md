# Chapter 5: Related work (draft)

> Status: draft written by Claude Code for the researcher to rewrite, verify and defend. Fact-checked on **22 Oct 2026**: each description below was compared with the abstract of the source (arXiv abstract text, a proceedings page, a publisher page or a Crossref record) and carries a literature claim id (docs/CLAIMS.md, rows L-01 to L-31). **No full paper was read**, so each sentence says what an abstract says. No result number from this project appears here. Citation keys refer to `paper/references.bib`; every entry there is re-resolved by `scripts/check_bib.py`. Transcend (2017) and CADE (2021) have no DOI or arXiv record and are cited by their USENIX pages [L-12, L-13].

The aim of this chapter is to say what each neighbour measured, so that the measurement made here (a single time-aware protocol with label delay, a fixed analyst budget and conformal drift monitoring, reported with A-AUT) can be placed beside them. It does not claim that any combination is new.

## 5.1 Time-aware evaluation of malware detectors

- **TESSERACT** (pendlebury2019tesseract; USENIX Security 2019). Identifies spatial and temporal experimental bias in Android malware classification, proposes three constraints for experiment design (C1 to C3 in this report) and a time-aware robustness metric, AUT, and releases an open-source evaluation framework. The arXiv v4 correction to Eq. (4) is noted in `paper/references.bib` and in CLAIMS M-02.
- **TESSERACT, extended version** (kan2024tesseractext; arXiv 2402.01359; v1 2 Feb 2024, v2 9 Apr 2025). Its abstract introduces "a set of constraints for fair experiment design" and "a new metric, AUT, for classifier robustness in real-world settings", evaluates published works on an Android dataset of 259,230 samples over five years, and adds case studies in Windows PE and PDF [L-22]. This is the form of AUT used here (ADR-0006, CLAIMS M-02).
- **Beyond the TESSERACT** (chow2025beyond; arXiv 2506.23814; v1 30 Jun 2025, v2 23 Mar 2026). It identifies five factors that cause performance discrepancies in learning-based Android malware detectors even when temporal splits and realistic class ratios are used, and recommends a methodology for curating trustworthy datasets [L-23]. The window geometry and size gate of ADR-0005 follow its stride discussion (PROTOCOL.md D18). The abstract does not mention label delay.
- **What this study adds to the line.** The protocol above is applied to two platforms with the same code; the question is not the evaluation bias itself but how long a detector stays useful once retraining is allowed under delayed labels and a budget.

## 5.2 Concept drift

- **Survey.** Gama, Zliobaite, Bifet, Pechenizkiy and Bouchachia, "A Survey on Concept Drift Adaptation", ACM Computing Surveys 46(4), 2014, DOI 10.1145/2523813 (gama2014survey). It treats concept drift as a change in the relation between the input data and the target variable in online supervised learning [L-16].
- **Stream framing in security.** Ceschin, Botacin, Bifet, Pfahringer, Oliveira, Gomes and Grégio, "Machine Learning (In) Security: A Stream of Problems" (ceschin2023stream; arXiv 2010.16045; Digital Threats 2023), evaluates how concept drift, evolution, delayed labels and adversarial machine learning affect existing security solutions [L-17].

## 5.3 Detecting drift with conformal methods

- **Transcend** (Jordaney et al., USENIX Security 2017, pp. 625 to 642) [L-12]. Introduces a conformal evaluator for detecting concept drift in malware classification models.
- **Transcendent** (barbero2022transcending; IEEE S&P 2022). Revisits Transcend with a formal treatment, adds two further conformal evaluators that match or surpass the original at lower computational cost, and evaluates on a five-year dataset without the original's experimental bias [L-14].
- **CADE** (Yang et al., "Detecting and Explaining Concept Drift Samples for Security Applications", USENIX Security 2021, pp. 2327 to 2344) [L-13]. Detects drifting samples with a contrastive autoencoder and explains them; the abstract names security applications in general.
- **Conformal prediction.** Shafer and Vovk, "A Tutorial on Conformal Prediction", JMLR 9:371 to 421, 2008 (shafer2008tutorial): for an error probability epsilon the method returns a set of labels that contains the true label with probability 1 - epsilon when successive examples are sampled independently from the same distribution [L-15]. This is the guarantee that drift monitors weaken or lose when the stream is not exchangeable, which is the situation studied in E3 and E4.
- **FIRCE** (barrett2026firce). Applies conformal-evaluation drift detection to network intrusion detection on an IoT testbed and two public intrusion datasets; it concerns network traffic, not malware files [L-21].

## 5.4 Retraining under a labelling budget

- **Continuous learning** (chen2023continuous; USENIX Security 2023). Combines contrastive learning with active learning for Android malware drift. It reports that F1 fell from 0.99 to 0.76 after six months without updates and that selection lowered the false negative rate from 14% to 9% and the false positive rate from 0.86% to 0.48% against the best baseline [L-11]. It is the closest neighbour on budgeted retraining; the full paper would have to be read for the budgets used and for how labels were assumed to arrive.
- **ActDroid** (muzaffar2024actdroid; arXiv 2401.16982; Muzaffar, Ragab Hassen, Zantout and Lones, v1 30 Jan 2024). An active online learning framework for Android malware that treats detection as a streaming problem and compensates for concept drift between an app's release and its labelling; it reports accuracy up to 96% with as little as 24% of the training data labelled [L-19]. The relation of the journal version to the arXiv version is open in `paper/REFERENCES_TODO.md`.
- **SEED** (amalapuram2026seed; arXiv 2605.24903, 24 May 2026). Semi-supervised continual detection "on a budget"; with 20% labelled data on seen tasks it reports average AUT improvements of 40% on BODMAS and 14% on AndroZoo against HCL*, and introduces a "delayed buffer update strategy" to limit label-noise propagation during replay; the abstract does not state the unit of that delay [L-20].
- **Label-efficient training updates** (minnei2026labelefficient; arXiv 2603.28396). Active and semi-supervised learning, alone and combined, on Android and Windows, with annotation cost cut by up to 90% at performance comparable to full-label retraining [L-06].
- **DRMD** (mcfadden2026drmd; AAAI 2026). Deep reinforcement learning that jointly classifies and rejects samples for manual labelling, with average AUT improvements of 8.66 and 10.90 over standard classification [L-24].

## 5.5 Label delay

- **Botacin and Gomes** (botacin2025labeldelays; Computers and Security 148:104122, 2025). Studies the impact of label delays on malware detection pipelines. The abstract introduces an exposure metric and reports that delayed labels from limited analysis-queue sizes leave up to 75% more attack opportunity than experiments suggest, and that pseudo-labels reduce the detection loss to about 30% of its original value [L-18]. These figures are theirs, from their setting; none is reused here.
- **ADAPT** (alam2025adapt; arXiv 2507.08597). Addresses the cost of the ground-truth labels that frequent retraining needs, with a model-agnostic pseudo-labelling algorithm; the abstract does not mention manual analysis queues [L-02].

This study differs in what it holds fixed: the same windows, constraints and metric are applied to both platforms, label delay and analyst budget are crossed, and drift monitors are evaluated as a retraining trigger on the same stream. It does not propose a new detector.

## 5.6 Datasets

- **LAMDA** (haque2025lamda; arXiv 2505.18551; ICLR 2026 poster). A longitudinal Android malware benchmark of over one million samples across 2013 to 2025 excluding 2015, built for concept drift analysis [L-08]. Size and class counts as used here are in docs/CLAIMS.md D-01.
- **BODMAS** (yang2021bodmas). Windows PE malware and benign feature vectors collected from August 2019 to September 2020 with curated family labels. Counts as used here: CLAIMS D-07. Benign timestamps are daily batches with placeholder dates (CLAIMS D-08, D-14), which the slicer excludes (ADR-0004).
- **EMBER** (anderson2018ember; arXiv 1804.04637; Anderson and Roth, 2018) and **EMBER2024** (joyce2025ember2024; arXiv 2506.05074; Joyce et al., 2025): static PE feature datasets; EMBER2024 holds more than 3.2 million files from six formats with a challenge set of evasive files [L-30]. EMBER2024 was not used (Tier 3 was not run).
- **McNdroid** (kamol2026mcndroid; arXiv 2605.06894). A multimodal Android benchmark over the same years as LAMDA [L-09]; not used here.

## 5.7 Newer neighbours at abstract level

The table lists work that combines some of this study's axes, as its abstract says. "Not in the abstract" is not "no": the papers were not read. Sources: `docs/related_work_addendum.md` and the claim rows named.

| Work | Delay | Budget | Conformal or monitor | Row |
|---|---|---|---|---|
| Chen, Ding, Wagner (chen2023continuous) | not in the abstract | active-learning selection | similarity-based uncertainty | L-11 |
| Botacin and Gomes (botacin2025labeldelays) | yes, the subject | analysis-queue size | not in the abstract | L-18 |
| ActDroid (muzaffar2024actdroid) | labelling lag between release and label | fraction labelled | not in the abstract | L-19 |
| SEED (amalapuram2026seed) | a "delayed buffer update", not label delay | 20% labelled | uncertainty by cosine distance | L-20 |
| Minnei et al. (minnei2026labelefficient) | not in the abstract | up to 90% less annotation | not in the abstract | L-06 |
| Transcendent (barbero2022transcending) | not in the abstract | rejection for analysis | yes, conformal | L-14 |
| Aurora (herzog2025aurora) | no | active-learning budgets, as a consequence of unreliable confidence | confidence quality | L-10 |

Against this table, the combination studied here is: label delay as a parameter, a fixed per-slot analyst budget, conformal credibility selection and four drift monitors as a retraining trigger, under one time-aware protocol on two platforms, reported with A-AUT. That is a statement about what this study measured, and about what the abstracts above say; it is not a claim that nothing else does it.
