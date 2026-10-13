# Chapter 5: Related work (draft)

> Status: draft written by Claude Code in Phase 5 for the researcher to rewrite, verify and defend. Sources were retrieved on **2026-10-13**. Abstract pages of arXiv 2506.23814 and arXiv 2402.01359 were fetched and read that day. Every other description below comes from a search-result summary or an abstract and is marked [verify: read the paper] until the researcher has read it. No result number from this project appears here. Citation keys refer to paper/references.bib; items without a key are listed in paper/REFERENCES_TODO.md and must not be cited until their identifiers are checked.

The aim of this chapter is to say what each neighbour measured, so that the measurement made here (a single time-aware protocol with label delay, a fixed analyst budget and conformal drift monitoring, reported with A-AUT) can be placed beside them. It does not claim that any combination is new.

## 5.1 Time-aware evaluation of malware detectors

- **TESSERACT** (pendlebury2019tesseract; USENIX Security 2019). Identifies spatial and temporal experimental bias in Android malware classification, proposes three constraints for experiment design (C1 to C3 in this report) and a time-aware robustness metric, AUT, and releases an open-source evaluation framework. Accessed 2026-10-13 [verify: read the paper; the arXiv v4 correction to Eq. (4) is noted in paper/references.bib].
- **TESSERACT, extended version** (arXiv 2402.01359; Kan, McFadden, Arp, Pendlebury, Jordaney, Kinder, Pierazzi, Cavallaro; v1 2 Feb 2024, v2 9 Apr 2025). The abstract page, read on 2026-10-13, says it introduces "a set of constraints for fair experiment design" and "a new metric, AUT, for classifier robustness in real-world settings", and widens the evaluation to more methods and to Windows PE and PDF case studies. This is the form of AUT used here (ADR-0006) [verify: the exact formula against the version used]. Not yet in paper/references.bib.
- **Beyond the TESSERACT** (chow2025beyond; arXiv 2506.23814; v1 30 Jun 2025, v2 23 Mar 2026). Read on 2026-10-13: it identifies five factors that cause performance discrepancies in learning-based Android malware detectors even when temporal splits and realistic class ratios are used, and offers recommendations and a methodology for curating trustworthy datasets. The window geometry and size gate of ADR-0005 follow its stride discussion (PROTOCOL.md D18). The page does not mention label delay [verify].
- **What this study adds to the line.** The protocol above is applied to two platforms with the same code; the question is not the evaluation bias itself but how long a detector stays useful once retraining is allowed under delayed labels and a budget.

## 5.2 Concept drift

- **Survey.** Gama, Zliobaite, Bifet, Pechenizkiy and Bouchachia, "A Survey on Concept Drift Adaptation", ACM Computing Surveys 46(4), article 44, 2014, DOI 10.1145/2523813 (bibliographic data confirmed from search results of 2026-10-13). The survey treats concept drift as a change in the relation between inputs and target in online supervised learning, and covers adaptive learning, strategies, algorithms, evaluation and applications [verify: read; not yet in references.bib].
- **Stream framing in security.** "Machine Learning (In) Security: A Stream of Problems" (arXiv 2010.16045) frames malware detection as a data-stream problem and discusses label availability and delay [verify: authors, venue and claims; not yet in references.bib].

## 5.3 Detecting drift with conformal methods

- **Transcend** (Jordaney et al., USENIX Security 2017). Introduces a conformal evaluator for detecting drifting, untrustworthy predictions in malware classification, with a rejection mechanism so that uncertain examples are quarantined for expert analysis [verify: read; not yet in references.bib].
- **Transcendent** (barbero2022transcending; IEEE S&P 2022). Revisits Transcend with a formal treatment, adds two further conformal evaluators that match or surpass the original at lower computational cost, and evaluates on a five-year dataset without the original's experimental bias [verify: read].
- **CADE** (Yang et al., USENIX Security 2021, pp. 2327 to 2344 per the USENIX listing). Detects and explains drifting samples through a contrastive autoencoder and a distance-based explanation; evaluated on Android malware and network intrusion data [verify: read; not yet in references.bib].
- **Conformal prediction.** Shafer and Vovk, "A Tutorial on Conformal Prediction", JMLR 9:371 to 421, 2008: a method that returns a set of candidate labels containing the true label with probability 1 - epsilon under exchangeability [verify: not yet in references.bib]. This is the guarantee that drift monitors weaken or lose when the stream is not exchangeable, which is the situation studied in Phases 8 and 9.
- **FIRCE** (barrett2026firce). A framework for intrusion response and conformal evaluation [verify: abstract only].

## 5.4 Retraining under a labelling budget

- **Continuous learning** (chen2023continuous; USENIX Security 2023). Combines contrastive learning with active learning for Android malware drift. The abstract-level summary reports a drop in F1 after months of deployment without updates and improvements in false negative and false positive rates from the proposed selection; it is the closest neighbour on budgeted retraining [verify: read the paper for the budgets used and how labels were assumed to arrive].
- **ActDroid** (muzaffar2024actdroid; arXiv 2401.16982). An active-learning framework for Android malware detection that reports the effect of labelling delay on online learning models [verify: read; the journal version's relation to the arXiv version is open in REFERENCES_TODO.md].
- **SEED** (amalapuram2026seed). Semi-supervised continual detection "on a budget"; delays adding newly observed samples to its replay buffer by fixed numbers of months [verify: read].
- **Label-efficient training updates** (minnei2026labelefficient) and **DRMD** (mcfadden2026drmd; AAAI 2026, reinforcement learning under drift) [verify: read both].

## 5.5 Label delay

- **Botacin and Gomes** (botacin2025labeldelays; Computers and Security 148:104122). Studies the impact of label delays on malware detection pipelines. The search-result summary describes an exposure metric and a finding that analysis-queue-induced delay is a significant challenge, with pseudo-labels reducing the loss [verify: read; the numbers in the summary are not copied here].
- **ADAPT** (arXiv 2507.08597). Identifies the manual analysis bottleneck and combats drift with pseudo-labelling [verify: read; not yet in references.bib].

This study differs in what it holds fixed: the same windows, constraints and metric are applied to both platforms, label delay and analyst budget are crossed, and drift monitors are evaluated as a retraining trigger on the same stream. It does not propose a new detector.

## 5.6 Datasets

- **LAMDA** (haque2025lamda; arXiv 2505.18551; ICLR 2026 poster). A longitudinal Android malware benchmark of over one million samples across 2013 to 2025 excluding 2015, built for concept drift analysis (search-result summary, 2026-10-13). Size and class counts as used here are in docs/CLAIMS.md D-01 [verified against Table 2 of the paper at that time].
- **BODMAS** (yang2021bodmas). Windows PE malware and benign feature vectors collected from August 2019 to September 2020 with curated family labels. Counts as used here: CLAIMS D-07. Benign timestamps are daily batches with placeholder dates (CLAIMS D-08, D-14), which the slicer excludes (ADR-0004).
- **EMBER** (arXiv 1804.04637; Anderson and Roth, 2018) and **EMBER2024** (arXiv 2506.05074; Joyce et al., 2025): static PE feature datasets; EMBER2024 is optional Tier 3 here [verify: authors and venues; neither is yet in references.bib; see REFERENCES_TODO.md].

## 5.7 Positioning table (for the researcher to complete after reading)

| Question | TESSERACT line | Conformal drift detection | Active and continual learning | Label delay | This study |
|---|---|---|---|---|---|
| Time-aware constraints C1 to C3 | yes (defines them) | [verify] | [verify] | [verify] | applied and asserted in code |
| Retraining allowed | no (fixed model) | no | yes | partly [verify] | yes, policy never or periodic; monitor-triggered in Phase 9 |
| Label delay varied | no | no | [verify] | yes [verify] | yes, `d` in {0, 1, 2, 3} slots |
| Analyst budget varied | no | no | yes [verify] | [verify] | yes, 0.5 to 5 percent per slot |
| Conformal monitor as trigger | no | yes (detection) | [verify] | [verify] | Phase 9 |
| Two platforms, one protocol | one (extended: PE and PDF case studies) | [verify] | Android | [verify] | LAMDA and BODMAS |

Cells marked [verify] are not claims; they are questions for the reading list.
