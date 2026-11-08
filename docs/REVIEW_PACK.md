# Reviewer pack: reading the report and paper line by line

For the researcher. Generated on 8 Nov 2026 from `report/` and `docs/CLAIMS.md`. The report and the paper were drafted with an AI assistant and checked only by other AI instances (self-review), so no person has yet read them. Reading them is the one check no script can do. Plan about 3 to 4 hours. Mark each box as you go; when everything is ticked, tell Claude (or edit `report/ch08_discussion.md` section 8.7, item 1) so the review-status limit can be changed truthfully.

## How to read a chapter
1. Read the whole chapter once for sense before checking anything.
2. For every bracketed id such as `[E-30]`, open the row in `docs/CLAIMS.md` (the table below gives the first words of each row) and confirm the sentence says no more than the row: same number, same interval, same dataset and model, same delay and budget, 'descriptive' versus 'registered'.
3. Flag any sentence that says or implies: a cause, practical importance, priority ('first'), or a result that is not in the ledger.
4. Rewrite anything you would not defend in front of an examiner. The text is yours to change; `uv run python scripts/claims_audit.py` tells you if a number lost its id.

## Sign-off sheet

| Item | Read | Claims checked | Wording changed or accepted | Initials, date |
|---|---|---|---|---|
| ch00_front_matter | [ ] | [ ] | [ ] | |
| ch01_introduction | [ ] | [ ] | [ ] | |
| ch02_landscape | [ ] | [ ] | [ ] | |
| ch03_analysis | [ ] | [ ] | [ ] | |
| ch04_latest_techniques | [ ] | [ ] | [ ] | |
| ch05_related_work | [ ] | [ ] | [ ] | |
| ch06_method | [ ] | [ ] | [ ] | |
| ch07_experiments | [ ] | [ ] | [ ] | |
| ch08_discussion | [ ] | [ ] | [ ] | |
| ch09_conclusion | [ ] | [ ] | [ ] | |
| paper/main.tex | [ ] | [ ] | [ ] | |
| README.md | [ ] | [ ] | [ ] | |
| section 8.7 open items | [ ] | [ ] | [ ] | |

## ch00_front_matter.md

1,343 words, 8 distinct claim ids. Sections: Malware Detector Lifetime Under Delayed Labels: Small Effects and Null Monitors in a Pre-Registered Time-Aware Study on Android and Windows PE Data; Abstract; Reading guide; How this report was produced, and what an examiner can check; Length against the guide's page budget; Acknowledgements

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| D-15 | LAMDA label rule: an app with vt_detection 0 is benign, one with vt_detection of 4 or mor... | rule holds for every row of the cache (0 conflicts) | [verified] against the paper; conflict ... |
| D-16 | LAMDA labels are AV-centric (the dataset card says they are "biased toward highly detecte... | stated limitation | [verified] against the dataset card |
| E-30 | E2 LAMDA, registered primary contrasts (periodic, random selection), 10 seeds, A-AUT diff... | lr C-D1 0.0032 [-0.0011, 0.0077] equivalent = 0.0011 [-0.0004, 0.0026... | [measured] |
| E-35 | RQ1 as registered (prereg-v1): gap between random-split F1 and time-aware AUT, mean over ... | lamda lgbm per-slot matched 0.0403 [0.0240, 0.0481] point at or above... | [measured] |
| E-42 | E3 LAMDA, registered primary interaction I_S(B) = adv_S(d=0,B) minus adv_S(d=3,B), 10 see... | lamda lr uncertainty B=1%: 0.0118 [0.0043, 0.0178] detected, 43.6 lab... | [measured] |
| E-59 | Supersedes E-52 (stats review E4 applied). E4 lamda, registered contrast M-P = monitor-tr... | lgbm ks d=0: -0.0026 [-0.0050, -0.0003] reversed_within_margin, refit... | [measured] |
| E-68 | EXPLORATORY, not registered, computed from the committed per-slot table `reports/tables/e... | LAMDA, never retrained: LightGBM 0.783 at slot 1, 0.770 at slot 12, f... | [measured] |
| T-02 | Word counts of the report chapters at the Phase 11 hand-in draft, counted with `wc -w` eq... | ch1 1170; ch2 1099; ch3 2277; ch4 1501; ch5 1572; ch6 3369; ch7 5129;... | [measured] |

## ch01_introduction.md

1,177 words, 3 distinct claim ids. Sections: Chapter 1: Introduction (draft); 1.1 Motivation; 1.2 Problem statement; 1.3 Research questions; 1.4 Contribution; 1.5 Scope, data and ethics; 1.6 Report outline

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| D-01 | LAMDA size and class counts (Baseline subset, HF commit ad9614bd) | 1,008,381 apps; 369,906 malware; 638,475 benign | [verified] (matches arXiv 2505.18551 Ta... |
| D-07 | BODMAS size and features | 134,435 samples (57,293 malware, 77,142 benign); 2,381 float32 featur... | [verified] against the BODMAS page; den... |
| E-68 | EXPLORATORY, not registered, computed from the committed per-slot table `reports/tables/e... | LAMDA, never retrained: LightGBM 0.783 at slot 1, 0.770 at slot 12, f... | [measured] |

## ch02_landscape.md

1,192 words, 20 distinct claim ids. Sections: Chapter 2: Landscape (draft); 2.1 The problem in one paragraph; 2.2 Concepts used in this report; 2.3 Why Android and Windows PE; 2.4 The datasets; 2.5 What the datasets cannot tell us; 2.6 Threat-landscape context

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| D-01 | LAMDA size and class counts (Baseline subset, HF commit ad9614bd) | 1,008,381 apps; 369,906 malware; 638,475 benign | [verified] (matches arXiv 2505.18551 Ta... |
| D-02 | LAMDA feature count, storage and density | 4,561 int8 features (values 0-17); 1.63% non-zero | [measured] |
| D-03 | LAMDA slotting timestamp | AndroZoo `added` (seconds) for 100% of rows; `year_month` equals its ... | [measured]; the meaning of `added` is s... |
| D-05 | LAMDA duplicate feature vectors | 679,423 distinct vectors; 238,576 rows (23.7%) repeat a vector from a... | [measured] |
| D-07 | BODMAS size and features | 134,435 samples (57,293 malware, 77,142 benign); 2,381 float32 featur... | [verified] against the BODMAS page; den... |
| D-08 | BODMAS timestamps by class | malware 2019-08-29..2020-09-30 (second resolution); benign 2007-01-01... | [measured] |
| D-14 | BODMAS benign timestamps are daily batches | 66,167 benign rows date-only; study-window median 150 rows/day (regul... | [measured] |
| D-15 | LAMDA label rule: an app with vt_detection 0 is benign, one with vt_detection of 4 or mor... | rule holds for every row of the cache (0 conflicts) | [verified] against the paper; conflict ... |
| D-16 | LAMDA labels are AV-centric (the dataset card says they are "biased toward highly detecte... | stated limitation | [verified] against the dataset card |
| D-17 | BODMAS: the project page and the repository README do not describe how the labels were pr... | superseded by D-18 | [verify] |
| D-19 | LAMDA timestamp provenance, read on 8 Nov 2026: the dataset card (huggingface.co/datasets... | see claim | [verified] (what the pages say, read th... |
| L-08 | LAMDA (Haque et al., arXiv 2505.18551): spans 12 years (2013 to 2025, excluding 2015), ov... | 12 years; over 1 million; 37%; 1,380 families | [verified] at abstract level; the full ... |
| L-16 | Gama, Zliobaite, Bifet, Pechenizkiy, Bouchachia, A survey on concept drift adaptation, AC... | 5 authors | [verified] at abstract level; the full ... |
| L-18 | Botacin and Gomes, Towards more realistic evaluations: the impact of label delays in malw... | up to 75%; about 30% | [verified] at abstract level; the full ... |
| L-30 | EMBER2024 (Joyce et al., arXiv 2506.05074; DOI 10.1145/3711896.3737431 per the arXiv reco... | over 3.2 million files; 6 formats | [verified] at abstract level; the full ... |
| L-32 | AV-TEST Institute malware statistics page: the institute registers "over 450,000 new mali... | over 450,000 per day | [verified] as quoted; the figure is the... |
| L-36 | Kaspersky (Securelist), mobile threat report 2025, dated 4 Mar 2026: "815,735 new unique ... | 815,735 packages | [verified] at the page by summary; the ... |
| L-37 | AV-TEST Security Report 2019/2020: new Android malware samples in 2019 were 3,170,140, th... | 3,170,140; over 78 percent | [verified] at the page by summary; the ... |
| W-01 | LAMDA usable runs at 10%, M = 50 (cap and flag) | 97 usable months in 10 runs; longest 62 (2018-11..2023-12), of which ... | [measured] (slot counts only) |
| W-02 | BODMAS usable runs at 10%, M = 50, placeholder rows excluded | 26 usable 2-week slots in 2 runs (9 and 17); none below 10% | [measured] (slot counts only) |

## ch03_analysis.md

2,330 words, 17 distinct claim ids. Sections: Chapter 3: How the results are analysed (draft); 3.1 What is being compared; 3.2 The quantities; 3.3 What the contrasts are; 3.4 Uncertainty: why windows come first; 3.5 Effect sizes in plain units; 3.6 The decision rule, and the equivalence margin; 3.7 What these statistics cannot show; 3.8 Analysis of E3 and E4; 3.9 Reading chapter 7

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| L-34 | Hierarchical bootstrap references added to the bibliography: Davison and Hinkley, Bootstr... | see claim | [verified] bibliographic data and the R... |
| P-01 | Evaluation slots and their C3 draws depend on seed and slot only, so arms of a contrast s... | per-slot draw keyed by (seed, slot id); same rows in every grid cell | [verified] code reading and tests |
| P-02 | Rolling windows (nT, nE, stride) | LAMDA 4, 12, 3; BODMAS 3, 6, 2 | [verified] |
| P-03 | Fixed decision threshold | 0.5, malware when P > 0.5 | [verified] |
| P-04 | AUT and A-AUT definitions | AUT = 1/(N-1) sum (f_k + f_{k+1})/2; A-AUT = mean and sample std (ddo... | [verified] |
| P-05 | Budget as a percentage of the evaluated slot after C3, count floor(pct/100 * n + 1/2); gr... | as stated | [verified] |
| P-06 | Recovery time definition | F1 back to 90% of the pre-drop level; drop = fall of at least 0.05 be... | [verified] |
| P-07 | Primary contrasts C-D1, C-D2, C-P, C-B per dataset and model | as in the PREREG RQ2 row | [verified] |
| P-08 | Two-stage bootstrap: moving blocks of windows of length ceil(nE/stride) (LAMDA 4, BODMAS ... | as stated | [verified] |
| P-09 | Effect-size units | AUT lost per slot of delay (contrast / 3, and OLS slope over d = 0..3... | [verified] |
| P-10 | Decision rule and equivalence margin | detected when the 95% interval excludes 0 in the hypothesised directi... | [estimate] margin and band |
| P-11 | Smallest two-sided exact Wilcoxon p-value with n paired seeds | 0.0625 for 5 pairs; 2/1024 = 0.00195 for 10 pairs | [verified] |
| P-12 | Known limits written before the results: BODMAS one useful refit per window and periodic ... | as stated | [verified] |
| P-13 | Share of scored rows whose 0.5 decision changed after retraining, at 0.5% and 5% of the s... | 0.2% to 2.1% across datasets and models (E-13 and E-14 give each valu... | [measured] |
| P-14 | The per-slot comparator reaches a lower malware ratio than the time-aware series on LAMDA | mean achieved ratio 0.075 against 0.084 (E-18) | [measured] |
| P-17 | E4 design registered before any E4 result (addendum v3, tag prereg-v3 on 1d302ea, 20 Oct ... | alpha 0.01 per slot for every monitor; 500 rows per side (MMD 200); K... | [verified] |
| P-18 | Smallest Holm-adjusted Wilcoxon p in an E4 family: 32 contrasts, 10 paired seeds, smalles... | 0.0625 | [verified] |

## ch04_latest_techniques.md

1,501 words, 23 distinct claim ids. Sections: Chapter 4: Recent techniques and attacks (draft); 4.1 Why this chapter exists; 4.2 Handling drift: training, adaptation and detection; 4.3 Evaluation: benchmarks and the evaluation trap; 4.4 Adversaries; 4.5 Language models on the analyst's side; 4.6 What remains open in this chapter

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| D-01 | LAMDA size and class counts (Baseline subset, HF commit ad9614bd) | 1,008,381 apps; 369,906 malware; 638,475 benign | [verified] (matches arXiv 2505.18551 Ta... |
| D-02 | LAMDA feature count, storage and density | 4,561 int8 features (values 0-17); 1.63% non-zero | [measured] |
| E-43 | E3 lamda, per-delay advantage adv_S(d,B) of the selector over random at equal labels spen... | lamda lr uncertainty B=1% d=0: 0.0145 [0.0071, 0.0173] detected; lamd... | [measured] |
| L-01 | TIF (Zheng et al., arXiv 2502.05098): groups training data into environments by applicati... | abstract-level description | [verified] at abstract level; the full ... |
| L-02 | ADAPT (Alam, Piplai, Rastogi, arXiv 2507.08597): model-agnostic pseudo-labelling semi-sup... | 5 datasets | [verified] at abstract level; the full ... |
| L-03 | LFreeDA (Li and Bertino, arXiv 2511.14963), Windows, MB-24+ dataset: improves accuracy by... | 12.6%, 11.1%, 4%, 3.4%, 300 samples | [verified] at abstract level; the full ... |
| L-04 | MADCAT (Roh et al., arXiv 2505.18734): test-time training of the encoder on a small, bala... | abstract-level description | [verified] at abstract level; the full ... |
| L-05 | DREAM (He et al., arXiv 2405.04095; accepted to ACM CCS 2025 per the arXiv comment): upda... | 76.6% | [verified] at abstract level; the full ... |
| L-06 | Minnei et al. (arXiv 2603.28396), Android and Windows: combined active and semi-supervise... | up to 90% | [verified] at abstract level; the full ... |
| L-07 | Kalny, Jurecek, Stamp (arXiv 2604.22629), EMBER2024, six malware families: fixed two-mont... | 6 families, 2-month windows | [verified] at abstract level; the full ... |
| L-08 | LAMDA (Haque et al., arXiv 2505.18551): spans 12 years (2013 to 2025, excluding 2015), ov... | 12 years; over 1 million; 37%; 1,380 families | [verified] at abstract level; the full ... |
| L-09 | McNdroid (Kamol et al., arXiv 2605.06894): Android benchmark spanning 2013 to 2025 exclud... | 3 modalities | [verified] at abstract level; the full ... |
| L-10 | Aurora (Herzog, Eusebi, Cavallaro, arXiv 2505.22843): evaluates the confidence quality an... | abstract-level description | [verified] at abstract level; the full ... |
| L-11 | Chen, Ding, Wagner, Continuous Learning for Android Malware Detection (USENIX Security 20... | 0.99 to 0.76; 14% to 9%; 0.86% to 0.48% | [verified] at abstract level; the full ... |
| L-22 | TESSERACT extended version (Kan et al., arXiv 2402.01359; v1 2 Feb 2024, v2 9 Apr 2025): ... | 259,230 samples; 5 years | [verified] at abstract level; the full ... |
| L-23 | Beyond the TESSERACT (Chow et al., arXiv 2506.23814): identifies five factors that cause ... | 5 factors | [verified] at abstract level; the full ... |
| L-25 | Li, Li, Ye, Xu, Arms Race in Adversarial Malware Detection: A Survey (arXiv 2005.11671; A... | abstract-level findings | [verified] at abstract level; the full ... |
| L-26 | Aryal, Gupta, Abdelsalam, Kunwar, Thuraisingham, A Survey on Adversarial Attacks for Malw... | 5 authors; pp. 428-459 | [verified] at abstract level; the full ... |
| L-27 | Ryan et al. (arXiv 2602.16304): 13 language models on 4,070 PyPI packages (370 malicious,... | 13 models; 4,070 packages | [verified] at abstract level; the full ... |
| L-28 | Chawla and Prasad (arXiv 2601.09035): Windows executables decompiled with Ghidra and clas... | abstract-level findings | [verified] at abstract level; the full ... |
| L-29 | MalCVE (Cristea, Molnes, Li, arXiv 2510.15567): retrieval-augmented language-model pipeli... | 3,839 files; 97% | [verified] at abstract level; the full ... |
| L-30 | EMBER2024 (Joyce et al., arXiv 2506.05074; DOI 10.1145/3711896.3737431 per the arXiv reco... | over 3.2 million files; 6 formats | [verified] at abstract level; the full ... |
| L-31 | Cerqueira et al. (arXiv 2606.07789; KDD 2026 per the arXiv comment): benchmarks 14 drift ... | 14 methods; 7 datasets | [verified] at abstract level; the full ... |

## ch05_related_work.md

1,572 words, 27 distinct claim ids. Sections: Chapter 5: Related work (draft); 5.1 Time-aware evaluation of malware detectors; 5.2 Concept drift; 5.3 Detecting drift with conformal methods; 5.4 Retraining under a labelling budget; 5.5 Label delay; 5.6 Datasets; 5.7 Newer neighbours at abstract level

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| D-01 | LAMDA size and class counts (Baseline subset, HF commit ad9614bd) | 1,008,381 apps; 369,906 malware; 638,475 benign | [verified] (matches arXiv 2505.18551 Ta... |
| D-07 | BODMAS size and features | 134,435 samples (57,293 malware, 77,142 benign); 2,381 float32 featur... | [verified] against the BODMAS page; den... |
| D-08 | BODMAS timestamps by class | malware 2019-08-29..2020-09-30 (second resolution); benign 2007-01-01... | [measured] |
| D-14 | BODMAS benign timestamps are daily batches | 66,167 benign rows date-only; study-window median 150 rows/day (regul... | [measured] |
| L-01 | TIF (Zheng et al., arXiv 2502.05098): groups training data into environments by applicati... | abstract-level description | [verified] at abstract level; the full ... |
| L-02 | ADAPT (Alam, Piplai, Rastogi, arXiv 2507.08597): model-agnostic pseudo-labelling semi-sup... | 5 datasets | [verified] at abstract level; the full ... |
| L-06 | Minnei et al. (arXiv 2603.28396), Android and Windows: combined active and semi-supervise... | up to 90% | [verified] at abstract level; the full ... |
| L-08 | LAMDA (Haque et al., arXiv 2505.18551): spans 12 years (2013 to 2025, excluding 2015), ov... | 12 years; over 1 million; 37%; 1,380 families | [verified] at abstract level; the full ... |
| L-09 | McNdroid (Kamol et al., arXiv 2605.06894): Android benchmark spanning 2013 to 2025 exclud... | 3 modalities | [verified] at abstract level; the full ... |
| L-10 | Aurora (Herzog, Eusebi, Cavallaro, arXiv 2505.22843): evaluates the confidence quality an... | abstract-level description | [verified] at abstract level; the full ... |
| L-11 | Chen, Ding, Wagner, Continuous Learning for Android Malware Detection (USENIX Security 20... | 0.99 to 0.76; 14% to 9%; 0.86% to 0.48% | [verified] at abstract level; the full ... |
| L-12 | Transcend: Detecting Concept Drift in Malware Classification Models (Jordaney, Sharad, Da... | 7 authors; pp. 625-642 | [verified] at abstract level; the full ... |
| L-13 | CADE: Detecting and Explaining Concept Drift Samples for Security Applications (Yang, Guo... | 7 authors; pp. 2327-2344 | [verified] at abstract level; the full ... |
| L-14 | Transcendent (Barbero, Pendlebury, Pierazzi, Cavallaro, arXiv 2010.03856; IEEE S&P 2022, ... | 5 years; 2 evaluators | [verified] at abstract level; the full ... |
| L-15 | Shafer and Vovk, A tutorial on conformal prediction (arXiv 0706.3188; JMLR 9:371 to 421, ... | 1 - epsilon | [verified] at abstract level; the full ... |
| L-16 | Gama, Zliobaite, Bifet, Pechenizkiy, Bouchachia, A survey on concept drift adaptation, AC... | 5 authors | [verified] at abstract level; the full ... |
| L-17 | Ceschin et al., Machine Learning (In) Security: A Stream of Problems (arXiv 2010.16045; D... | 7 authors | [verified] at abstract level; the full ... |
| L-18 | Botacin and Gomes, Towards more realistic evaluations: the impact of label delays in malw... | up to 75%; about 30% | [verified] at abstract level; the full ... |
| L-19 | ActDroid (Muzaffar et al., arXiv 2401.16982): active online learning for Android malware;... | 96%; 24% | [verified] at abstract level; the full ... |
| L-20 | SEED (Amalapuram et al., arXiv 2605.24903): with 20% labelled data on seen tasks, average... | 40%; 14%; 20% labelled | [verified] at abstract level; the full ... |
| L-21 | FIRCE (Barrett et al., arXiv 2605.01962): conformal-evaluation drift detection for networ... | 10 devices; 2 benchmark datasets | [verified] at abstract level; the full ... |
| L-22 | TESSERACT extended version (Kan et al., arXiv 2402.01359; v1 2 Feb 2024, v2 9 Apr 2025): ... | 259,230 samples; 5 years | [verified] at abstract level; the full ... |
| L-23 | Beyond the TESSERACT (Chow et al., arXiv 2506.23814): identifies five factors that cause ... | 5 factors | [verified] at abstract level; the full ... |
| L-24 | DRMD (McFadden et al., arXiv 2508.18839; AAAI 2026, vol. 40, pp. 854 to 862): deep reinfo... | 8.66; 10.90 | [verified] at abstract level; the full ... |
| L-30 | EMBER2024 (Joyce et al., arXiv 2506.05074; DOI 10.1145/3711896.3737431 per the arXiv reco... | over 3.2 million files; 6 formats | [verified] at abstract level; the full ... |
| L-31 | Cerqueira et al. (arXiv 2606.07789; KDD 2026 per the arXiv comment): benchmarks 14 drift ... | 14 methods; 7 datasets | [verified] at abstract level; the full ... |
| M-02 | TESSERACT AUT normalisation | arXiv v4 comments: published Eq. (4) had an extra 1/N factor (typo); ... | [verified] (comment text); equivalence ... |

## ch06_method.md

3,369 words, 10 distinct claim ids. Sections: Chapter 6: Method (draft); 6.1 What the simulator is for; 6.2 Data flow; 6.3 The label queue and the delay rule; 6.4 Budget and selection; 6.5 Retraining and the training pool; 6.6 Runs, determinism and resumption; 6.7 Limits stated before results; 6.8 The E1 comparator; 6.9 Threats to validity of the instrument; 6.10 The grid, its ledger and the statistics; 6.11 The conformal layer and selection; 6.12 Drift monitors and monitor-triggered retraining

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| E-13 | Label-influence diagnostic, LAMDA (periodic every 3 slots, d = 0, random selection, weigh... | LR 0.88% / 2.11% (16,451 / 39,449 of 1,872,651 rows); LightGBM 0.71% ... | [measured] (counts decision changes onl... |
| E-15 | Changed decisions by true class at 5% of the slot (E-13, E-14 runs) and the spread over w... | LAMDA: malware rows 7.70% (LR) and 4.40% (LightGBM) against benign ro... | [measured] (no noise floor or placebo a... |
| P-02 | Rolling windows (nT, nE, stride) | LAMDA 4, 12, 3; BODMAS 3, 6, 2 | [verified] |
| P-05 | Budget as a percentage of the evaluated slot after C3, count floor(pct/100 * n + 1/2); gr... | as stated | [verified] |
| P-12 | Known limits written before the results: BODMAS one useful refit per window and periodic ... | as stated | [verified] |
| P-15 | The E2 grid expands to 27 runs per dataset: 16 periodic cells (4 delays x 4 budgets, seed... | 27 per dataset, 54 in all | [verified] |
| P-16 | Retrain events of the periodic policy: before evaluation slots 3, 6, 9, ... counted from ... | as stated | [verified] |
| P-17 | E4 design registered before any E4 result (addendum v3, tag prereg-v3 on 1d302ea, 20 Oct ... | alpha 0.01 per slot for every monitor; 500 rows per side (MMD 200); K... | [verified] |
| S-01 | Queue rule under test: a label queried in slot t is usable from slot t+1+d, released exac... | d in {0, 1, 2, 3}, parametrised and 150 property-based scenarios; 21 ... | [measured] (code-behaviour check, not e... |
| S-05 | Determinism and resume: same config and seed give identical predictions; a run killed aft... | predictions sha256 equal; 0 duplicate (seed, window, slot, row, model... | [measured] (code-behaviour check) |

## ch07_experiments.md

5,150 words, 50 distinct claim ids. Sections: Chapter 7: Experiments and results (draft); 7.1 What was run; 7.2 E0 and E1: the time-aware baseline and the random-split gap (RQ1); 7.3 E2: label delay and analyst budget (RQ2); 7.4 What E2 does not show; 7.5 E3: selection under delay (RQ3); 7.6 E4: drift monitors and retraining (RQ4); 7.7 An exploratory reading of "lifetime" from the stored E2 curves

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| E-02 | BODMAS headline, ADR-0005 windows (6), 10%, five seeds: A-AUT(F1) mean ± std over windows... | LR 0.912 ± 0.018; 0.940; 0.028; 0.000 to 0.057; 0.014 to 0.038. Light... | [measured] (windows overlap: descriptiv... |
| E-03 | LAMDA headline, ADR-0005 windows (16), 10%, five seeds (same columns as E-02) | LR 0.678 ± 0.058; 0.831; 0.152; 0.041 to 0.244; 0.100 to 0.175. Light... | [measured] (windows overlap: descriptiv... |
| E-09 | Real-data leakage canary (nearest-centroid, ADR-0005 windows) | LAMDA, 4 windows: AUT 0.446 (true timestamps), 0.632 (shuffled), rand... | [measured] |
| E-12 | Context numbers for the E0 report | BODMAS evaluates 20 distinct two-week slots (about nine months, two s... | slot count [verified]; pooling effect [... |
| E-16 | E1 time-aware series reproduces E0's A-AUT (same windows, five seeds, never retrained) | LAMDA LR 0.6785 (E0 0.678), LightGBM 0.7599 (0.760); BODMAS LR 0.9122... | [measured] |
| E-18 | Ratio actually reached by each series in E-17, and the gap on cells where both series rea... | LAMDA: mean achieved ratio 0.084 (time-aware) and 0.075 (random split... | [measured] (per-slot F1 differences, no... |
| E-19 | Why E0's gap and E-17's differ, from the E1 run (same fitted comparator model): E0-style ... | LAMDA LR: E0-style gap 0.152; random-split F1 pooled over evaluation ... | [measured]; the part due to held-out tr... |
| E-22 | Leakage canary re-run with the final analysis and simulator code, same windows as Phase 4... | LAMDA, 4 windows: AUT 0.446 (true timestamps), 0.632 (shuffled), rand... | [measured] |
| E-26 | E2 grid completeness (planned against completed against failed) | BODMAS: 27 of 27 cells complete, 0 failed, code version(s) ['c26aa5f'... | [measured] |
| E-27 | E2 BODMAS A-AUT(F1) per arm, five seeds, ADR-0005 windows (6 windows): mean over windows,... | lr never 0.912 (sd 0.018); lr periodic d=0 B=0.5% 0.912 (sd 0.019; 13... | [measured] |
| E-28 | E2 LAMDA A-AUT(F1) per arm, five seeds, ADR-0005 windows (16 windows): mean over windows,... | lr never 0.679 (sd 0.058); lr periodic d=0 B=0.5% 0.682 (sd 0.058; 21... | [measured] |
| E-29 | E2 BODMAS, registered primary contrasts (periodic, random selection), 10 seeds, A-AUT dif... | lr C-D1 0.0010 [-0.0001, 0.0023] equivalent = 0.0003 [-0.0000, 0.0008... | [measured] |
| E-30 | E2 LAMDA, registered primary contrasts (periodic, random selection), 10 seeds, A-AUT diff... | lr C-D1 0.0032 [-0.0011, 0.0077] equivalent = 0.0011 [-0.0004, 0.0026... | [measured] |
| E-31 | E2 supporting check: seed-level Wilcoxon signed-rank p (10 paired seeds, floor 0.00195) a... | bodmas lr: p C-D1 0.1309, C-D2 0.0020, C-P 0.0020, C-B 0.0020; Holm C... | [measured] |
| E-32 | E2 the same four contrasts on seeds 0 to 4 only (nested in the 10-seed set, so not a repl... | bodmas lr: C-D1 0.0011 [-0.0003, 0.0028] equivalent, C-D2 0.0030 [0.0... | [measured] |
| E-33 | E2 OLS slope of A-AUT over delay 0 to 3 at each budget (five seeds), as AUT lost per slot... | bodmas lr: AUT lost per slot of delay (positive = falls) B=0.5% 0.000... | [measured] |
| E-34 | E2 budget response at delay 0, 10 seeds: AUT gained per 100 extra labels per slot between... | bodmas lr: 0.5->1 0.0054 [0.0007, 0.0100], 1->2 0.0014 [-0.0031, 0.00... | [measured] |
| E-35 | RQ1 as registered (prereg-v1): gap between random-split F1 and time-aware AUT, mean over ... | lamda lgbm per-slot matched 0.0403 [0.0240, 0.0481] point at or above... | [measured] |
| E-36 | E2 secondary check at Chow's window stride (seeds 0 to 4): C-D1, C-D2 and C-P | bodmas lr (4 windows): C-D1 0.0008 [-0.0009, 0.0025] equivalent, C-D2... | [measured] |
| E-37 | E2 absolute label counts and pool facts (LR, five seeds) | bodmas: at B=5%, d=0 140.7 labels queried per slot, 844 per window, 7... | [measured] |
| E-38 | E2 drop events (fall of at least 0.05 below the trailing 3-slot mean) and recovery (F1 ba... | bodmas lr: drop events per window-seed series never 0.27 (recovered 0... | [measured] |
| E-40 | E3 grid completeness (planned against complete against failed) and equal labels spent | bodmas: 28 complete, 0 planned and not run, 0 failed; lamda: 28 compl... | [measured] |
| E-41 | E3 BODMAS, registered primary interaction I_S(B) = adv_S(d=0,B) minus adv_S(d=3,B), 10 se... | bodmas lr uncertainty B=1%: 0.0030 [0.0000, 0.0035] detected_within_m... | [measured] |
| E-42 | E3 LAMDA, registered primary interaction I_S(B) = adv_S(d=0,B) minus adv_S(d=3,B), 10 see... | lamda lr uncertainty B=1%: 0.0118 [0.0043, 0.0178] detected, 43.6 lab... | [measured] |
| E-43 | E3 lamda, per-delay advantage adv_S(d,B) of the selector over random at equal labels spen... | lamda lr uncertainty B=1% d=0: 0.0145 [0.0071, 0.0173] detected; lamd... | [measured] |
| E-44 | E3 bodmas, per-delay advantage adv_S(d,B) of the selector over random at equal labels spe... | bodmas lr uncertainty B=1% d=0: 0.0030 [0.0000, 0.0035] detected_with... | [measured] |
| E-45 | E3 reserved-slice ablation at d=0, B=2%, credibility selection, seeds 0 to 4: A-AUT advan... | lamda lgbm reserved share 0 (trap): advantage -0.0117 [-0.0136, -0.00... | [measured] |
| E-46 | E3 nonconformity-score comparison at d=0, B=2%, credibility selection, reserved share 0.2... | lamda lgbm probability: A-AUT 0.7806, set coverage 0.8801, mean set s... | [measured] |
| E-47 | E3 selection arms at d=0, B=2%, reserved share 0.20, probability score, seeds 0 to 4: cla... | lamda lr credibility: arrived malware share 0.193, set coverage 0.898... | [measured] |
| E-48 | E4 grid completeness, resources and registration order; every cell ran at code version 1d... | bodmas: 38 of 38 complete, 0 failed, peak memory 1.29 GB, longest fit... | [measured] |
| E-49 | E4 periodic cells reproduce the stored E3 random-arm predictions exactly (same prediction... | 8 of 8 pairs match | [measured] |
| E-50 | E4 lamda, A-AUT per arm (seeds 0-9, 16 windows, mean over windows) with mean actual refit... | lgbm matched-domain_clf d=0: A-AUT 0.7595, 4.31 refits per window; lg... | [measured] |
| E-51 | E4 bodmas, A-AUT per arm (seeds 0-9, 6 windows, mean over windows) with mean actual refit... | lgbm matched-domain_clf d=0: A-AUT 0.9695, 2.00 refits per window; lg... | [measured] |
| E-58 | E4, retrain events that found no newly arrived label (logged no-ops, not refits) per wind... | lamda lgbm monitor-domain_clf d=3: 1.62; lamda lgbm monitor-ks d=3: 0... | [measured] |
| E-59 | Supersedes E-52 (stats review E4 applied). E4 lamda, registered contrast M-P = monitor-tr... | lgbm ks d=0: -0.0026 [-0.0050, -0.0003] reversed_within_margin, refit... | [measured] |
| E-60 | Supersedes E-53 (stats review E4 applied). E4 bodmas, registered contrast M-P = monitor-t... | lgbm ks d=0: 0.0003 [-0.0008, 0.0014] equivalent, refits per window 1... | [measured] |
| E-61 | Supersedes E-54 (stats review E4 applied). E4 lamda, registered contrast M-C = monitor-tr... | lgbm ks d=0: -0.0000 [-0.0009, 0.0014] equivalent, refits per window ... | [measured] |
| E-62 | Supersedes E-55 (stats review E4 applied). E4 bodmas, registered contrast M-C = monitor-t... | lgbm ks d=0: -0.0000 [-0.0003, 0.0002] equivalent, refits per window ... | [measured] |
| E-63 | Supersedes E-56 (stats review E4 applied). E4 monitor quality observing the never arm (pr... | lamda lgbm ks: alarm rate 0.617, precision 0.462 [0.354, 0.546] (alwa... | [measured] |
| E-64 | Supersedes E-57 (stats review E4 applied). E4 monitor quality inside each monitor-trigger... | lamda lgbm ks d=0: alarm rate 0.242, precision 0.573 [0.353, 0.663] (... | [measured] |
| E-66 | EXPLORATORY, not registered, computed from the committed per-slot table (no experiment ru... | bodmas lgbm: Pearson r 0.49 over 20 slots, 0.00 of slots below the ta... | [measured] |
| E-68 | EXPLORATORY, not registered, computed from the committed per-slot table `reports/tables/e... | LAMDA, never retrained: LightGBM 0.783 at slot 1, 0.770 at slot 12, f... | [measured] |
| P-02 | Rolling windows (nT, nE, stride) | LAMDA 4, 12, 3; BODMAS 3, 6, 2 | [verified] |
| P-03 | Fixed decision threshold | 0.5, malware when P > 0.5 | [verified] |
| P-10 | Decision rule and equivalence margin | detected when the 95% interval excludes 0 in the hypothesised directi... | [estimate] margin and band |
| P-11 | Smallest two-sided exact Wilcoxon p-value with n paired seeds | 0.0625 for 5 pairs; 2/1024 = 0.00195 for 10 pairs | [verified] |
| P-12 | Known limits written before the results: BODMAS one useful refit per window and periodic ... | as stated | [verified] |
| P-14 | The per-slot comparator reaches a lower malware ratio than the time-aware series on LAMDA | mean achieved ratio 0.075 against 0.084 (E-18) | [measured] |
| P-17 | E4 design registered before any E4 result (addendum v3, tag prereg-v3 on 1d302ea, 20 Oct ... | alpha 0.01 per slot for every monitor; 500 rows per side (MMD 200); K... | [verified] |
| P-18 | Smallest Holm-adjusted Wilcoxon p in an E4 family: 32 contrasts, 10 paired seeds, smalles... | 0.0625 | [verified] |

## ch08_discussion.md

3,819 words, 47 distinct claim ids. Sections: Chapter 8: Discussion and limitations (partial draft); 8.1 What was measured; 8.2 What the results do not show; 8.3 Threats to validity; 8.4 Ethics and scope; 8.5 Status of the tiers; 8.6 Future work; 8.7 Open items

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| D-03 | LAMDA slotting timestamp | AndroZoo `added` (seconds) for 100% of rows; `year_month` equals its ... | [measured]; the meaning of `added` is s... |
| D-15 | LAMDA label rule: an app with vt_detection 0 is benign, one with vt_detection of 4 or mor... | rule holds for every row of the cache (0 conflicts) | [verified] against the paper; conflict ... |
| D-16 | LAMDA labels are AV-centric (the dataset card says they are "biased toward highly detecte... | stated limitation | [verified] against the dataset card |
| D-17 | BODMAS: the project page and the repository README do not describe how the labels were pr... | superseded by D-18 | [verify] |
| D-18 | BODMAS label provenance, read in the paper (Yang, Ciptadi, Laziuk, Ahmadzadeh, Wang, IEEE... | see claim | [verified] (what the paper says); [veri... |
| D-19 | LAMDA timestamp provenance, read on 8 Nov 2026: the dataset card (huggingface.co/datasets... | see claim | [verified] (what the pages say, read th... |
| E-08 | Operating point and prevalence (10%, ADR-0005 windows) | Mean FPR / FNR: LAMDA LR 0.036 / 0.291, LightGBM 0.020 / 0.269; BODMA... | [measured] |
| E-10 | Evaluated rows repeating a feature vector of their training window (rolling, LR, seed 0, ... | BODMAS 0 of 101,247; LAMDA 52,985 of 838,012 (6.3%) | [measured] |
| E-18 | Ratio actually reached by each series in E-17, and the gap on cells where both series rea... | LAMDA: mean achieved ratio 0.084 (time-aware) and 0.075 (random split... | [measured] (per-slot F1 differences, no... |
| E-19 | Why E0's gap and E-17's differ, from the E1 run (same fitted comparator model): E0-style ... | LAMDA LR: E0-style gap 0.152; random-split F1 pooled over evaluation ... | [measured]; the part due to held-out tr... |
| E-24 | Clean-clone reproduction of Table 1 on BODMAS (`driftwatch reproduce table1`): fresh clon... | MATCH on 8 rows: largest difference in the time-aware columns 0.0000 ... | [measured] |
| E-26 | E2 grid completeness (planned against completed against failed) | BODMAS: 27 of 27 cells complete, 0 failed, code version(s) ['c26aa5f'... | [measured] |
| E-28 | E2 LAMDA A-AUT(F1) per arm, five seeds, ADR-0005 windows (16 windows): mean over windows,... | lr never 0.679 (sd 0.058); lr periodic d=0 B=0.5% 0.682 (sd 0.058; 21... | [measured] |
| E-29 | E2 BODMAS, registered primary contrasts (periodic, random selection), 10 seeds, A-AUT dif... | lr C-D1 0.0010 [-0.0001, 0.0023] equivalent = 0.0003 [-0.0000, 0.0008... | [measured] |
| E-30 | E2 LAMDA, registered primary contrasts (periodic, random selection), 10 seeds, A-AUT diff... | lr C-D1 0.0032 [-0.0011, 0.0077] equivalent = 0.0011 [-0.0004, 0.0026... | [measured] |
| E-34 | E2 budget response at delay 0, 10 seeds: AUT gained per 100 extra labels per slot between... | bodmas lr: 0.5->1 0.0054 [0.0007, 0.0100], 1->2 0.0014 [-0.0031, 0.00... | [measured] |
| E-35 | RQ1 as registered (prereg-v1): gap between random-split F1 and time-aware AUT, mean over ... | lamda lgbm per-slot matched 0.0403 [0.0240, 0.0481] point at or above... | [measured] |
| E-40 | E3 grid completeness (planned against complete against failed) and equal labels spent | bodmas: 28 complete, 0 planned and not run, 0 failed; lamda: 28 compl... | [measured] |
| E-41 | E3 BODMAS, registered primary interaction I_S(B) = adv_S(d=0,B) minus adv_S(d=3,B), 10 se... | bodmas lr uncertainty B=1%: 0.0030 [0.0000, 0.0035] detected_within_m... | [measured] |
| E-42 | E3 LAMDA, registered primary interaction I_S(B) = adv_S(d=0,B) minus adv_S(d=3,B), 10 see... | lamda lr uncertainty B=1%: 0.0118 [0.0043, 0.0178] detected, 43.6 lab... | [measured] |
| E-43 | E3 lamda, per-delay advantage adv_S(d,B) of the selector over random at equal labels spen... | lamda lr uncertainty B=1% d=0: 0.0145 [0.0071, 0.0173] detected; lamd... | [measured] |
| E-45 | E3 reserved-slice ablation at d=0, B=2%, credibility selection, seeds 0 to 4: A-AUT advan... | lamda lgbm reserved share 0 (trap): advantage -0.0117 [-0.0136, -0.00... | [measured] |
| E-47 | E3 selection arms at d=0, B=2%, reserved share 0.20, probability score, seeds 0 to 4: cla... | lamda lr credibility: arrived malware share 0.193, set coverage 0.898... | [measured] |
| E-48 | E4 grid completeness, resources and registration order; every cell ran at code version 1d... | bodmas: 38 of 38 complete, 0 failed, peak memory 1.29 GB, longest fit... | [measured] |
| E-50 | E4 lamda, A-AUT per arm (seeds 0-9, 16 windows, mean over windows) with mean actual refit... | lgbm matched-domain_clf d=0: A-AUT 0.7595, 4.31 refits per window; lg... | [measured] |
| E-51 | E4 bodmas, A-AUT per arm (seeds 0-9, 6 windows, mean over windows) with mean actual refit... | lgbm matched-domain_clf d=0: A-AUT 0.9695, 2.00 refits per window; lg... | [measured] |
| E-59 | Supersedes E-52 (stats review E4 applied). E4 lamda, registered contrast M-P = monitor-tr... | lgbm ks d=0: -0.0026 [-0.0050, -0.0003] reversed_within_margin, refit... | [measured] |
| E-60 | Supersedes E-53 (stats review E4 applied). E4 bodmas, registered contrast M-P = monitor-t... | lgbm ks d=0: 0.0003 [-0.0008, 0.0014] equivalent, refits per window 1... | [measured] |
| E-61 | Supersedes E-54 (stats review E4 applied). E4 lamda, registered contrast M-C = monitor-tr... | lgbm ks d=0: -0.0000 [-0.0009, 0.0014] equivalent, refits per window ... | [measured] |
| E-63 | Supersedes E-56 (stats review E4 applied). E4 monitor quality observing the never arm (pr... | lamda lgbm ks: alarm rate 0.617, precision 0.462 [0.354, 0.546] (alwa... | [measured] |
| E-66 | EXPLORATORY, not registered, computed from the committed per-slot table (no experiment ru... | bodmas lgbm: Pearson r 0.49 over 20 slots, 0.00 of slots below the ta... | [measured] |
| E-69 | Hash manifest of the stored predictions of E0 to E4 and a private archive of the same fil... | 577 files, 7.20 GiB; every SHA-256 in `docs/predictions_manifest.csv`... | [measured] |
| E-88 | Independent AI review of the paper, chapters 7 to 9 and the README against this ledger, 8... | 0 blockers, 7 major and 16 minor findings. Major, all fixed: E3 and E... | [measured] (counts of findings); the re... |
| L-12 | Transcend: Detecting Concept Drift in Malware Classification Models (Jordaney, Sharad, Da... | 7 authors; pp. 625-642 | [verified] at abstract level; the full ... |
| L-14 | Transcendent (Barbero, Pendlebury, Pierazzi, Cavallaro, arXiv 2010.03856; IEEE S&P 2022, ... | 5 years; 2 evaluators | [verified] at abstract level; the full ... |
| L-18 | Botacin and Gomes, Towards more realistic evaluations: the impact of label delays in malw... | up to 75%; about 30% | [verified] at abstract level; the full ... |
| L-22 | TESSERACT extended version (Kan et al., arXiv 2402.01359; v1 2 Feb 2024, v2 9 Apr 2025): ... | 259,230 samples; 5 years | [verified] at abstract level; the full ... |
| L-33 | Li, Iyengar, Kundu, Bertino, Revisiting Concept Drift in Windows Malware Detection: Adapt... | NDSS 2025 | [verified] that the paper is NDSS 2025;... |
| L-34 | Hierarchical bootstrap references added to the bibliography: Davison and Hinkley, Bootstr... | see claim | [verified] bibliographic data and the R... |
| L-36 | Kaspersky (Securelist), mobile threat report 2025, dated 4 Mar 2026: "815,735 new unique ... | 815,735 packages | [verified] at the page by summary; the ... |
| L-37 | AV-TEST Security Report 2019/2020: new Android malware samples in 2019 were 3,170,140, th... | 3,170,140; over 78 percent | [verified] at the page by summary; the ... |
| L-39 | Final-version check of six 2026 references, 8 Nov 2026 (arXiv pages, conference programme... | see claim | [verified] through Crossref and the pro... |
| P-10 | Decision rule and equivalence margin | detected when the 95% interval excludes 0 in the hypothesised directi... | [estimate] margin and band |
| P-12 | Known limits written before the results: BODMAS one useful refit per window and periodic ... | as stated | [verified] |
| P-13 | Share of scored rows whose 0.5 decision changed after retraining, at 0.5% and 5% of the s... | 0.2% to 2.1% across datasets and models (E-13 and E-14 give each valu... | [measured] |
| P-14 | The per-slot comparator reaches a lower malware ratio than the time-aware series on LAMDA | mean achieved ratio 0.075 against 0.084 (E-18) | [measured] |
| P-17 | E4 design registered before any E4 result (addendum v3, tag prereg-v3 on 1d302ea, 20 Oct ... | alpha 0.01 per slot for every monitor; 500 rows per side (MMD 200); K... | [verified] |

## ch09_conclusion.md

1,360 words, 28 distinct claim ids. Sections: Chapter 9: Conclusion and future work (draft); 9.1 What was done; 9.2 What was found; 9.3 What the study contributes; 9.4 Limits that apply to every finding; 9.5 Future work; 9.6 Reproducibility and release status

| id | row (first words) | result (first words) | tag |
|---|---|---|---|
| D-15 | LAMDA label rule: an app with vt_detection 0 is benign, one with vt_detection of 4 or mor... | rule holds for every row of the cache (0 conflicts) | [verified] against the paper; conflict ... |
| D-16 | LAMDA labels are AV-centric (the dataset card says they are "biased toward highly detecte... | stated limitation | [verified] against the dataset card |
| E-18 | Ratio actually reached by each series in E-17, and the gap on cells where both series rea... | LAMDA: mean achieved ratio 0.084 (time-aware) and 0.075 (random split... | [measured] (per-slot F1 differences, no... |
| E-24 | Clean-clone reproduction of Table 1 on BODMAS (`driftwatch reproduce table1`): fresh clon... | MATCH on 8 rows: largest difference in the time-aware columns 0.0000 ... | [measured] |
| E-26 | E2 grid completeness (planned against completed against failed) | BODMAS: 27 of 27 cells complete, 0 failed, code version(s) ['c26aa5f'... | [measured] |
| E-28 | E2 LAMDA A-AUT(F1) per arm, five seeds, ADR-0005 windows (16 windows): mean over windows,... | lr never 0.679 (sd 0.058); lr periodic d=0 B=0.5% 0.682 (sd 0.058; 21... | [measured] |
| E-29 | E2 BODMAS, registered primary contrasts (periodic, random selection), 10 seeds, A-AUT dif... | lr C-D1 0.0010 [-0.0001, 0.0023] equivalent = 0.0003 [-0.0000, 0.0008... | [measured] |
| E-30 | E2 LAMDA, registered primary contrasts (periodic, random selection), 10 seeds, A-AUT diff... | lr C-D1 0.0032 [-0.0011, 0.0077] equivalent = 0.0011 [-0.0004, 0.0026... | [measured] |
| E-35 | RQ1 as registered (prereg-v1): gap between random-split F1 and time-aware AUT, mean over ... | lamda lgbm per-slot matched 0.0403 [0.0240, 0.0481] point at or above... | [measured] |
| E-40 | E3 grid completeness (planned against complete against failed) and equal labels spent | bodmas: 28 complete, 0 planned and not run, 0 failed; lamda: 28 compl... | [measured] |
| E-42 | E3 LAMDA, registered primary interaction I_S(B) = adv_S(d=0,B) minus adv_S(d=3,B), 10 see... | lamda lr uncertainty B=1%: 0.0118 [0.0043, 0.0178] detected, 43.6 lab... | [measured] |
| E-45 | E3 reserved-slice ablation at d=0, B=2%, credibility selection, seeds 0 to 4: A-AUT advan... | lamda lgbm reserved share 0 (trap): advantage -0.0117 [-0.0136, -0.00... | [measured] |
| E-47 | E3 selection arms at d=0, B=2%, reserved share 0.20, probability score, seeds 0 to 4: cla... | lamda lr credibility: arrived malware share 0.193, set coverage 0.898... | [measured] |
| E-48 | E4 grid completeness, resources and registration order; every cell ran at code version 1d... | bodmas: 38 of 38 complete, 0 failed, peak memory 1.29 GB, longest fit... | [measured] |
| E-50 | E4 lamda, A-AUT per arm (seeds 0-9, 16 windows, mean over windows) with mean actual refit... | lgbm matched-domain_clf d=0: A-AUT 0.7595, 4.31 refits per window; lg... | [measured] |
| E-59 | Supersedes E-52 (stats review E4 applied). E4 lamda, registered contrast M-P = monitor-tr... | lgbm ks d=0: -0.0026 [-0.0050, -0.0003] reversed_within_margin, refit... | [measured] |
| E-60 | Supersedes E-53 (stats review E4 applied). E4 bodmas, registered contrast M-P = monitor-t... | lgbm ks d=0: 0.0003 [-0.0008, 0.0014] equivalent, refits per window 1... | [measured] |
| E-61 | Supersedes E-54 (stats review E4 applied). E4 lamda, registered contrast M-C = monitor-tr... | lgbm ks d=0: -0.0000 [-0.0009, 0.0014] equivalent, refits per window ... | [measured] |
| E-62 | Supersedes E-55 (stats review E4 applied). E4 bodmas, registered contrast M-C = monitor-t... | lgbm ks d=0: -0.0000 [-0.0003, 0.0002] equivalent, refits per window ... | [measured] |
| E-63 | Supersedes E-56 (stats review E4 applied). E4 monitor quality observing the never arm (pr... | lamda lgbm ks: alarm rate 0.617, precision 0.462 [0.354, 0.546] (alwa... | [measured] |
| E-66 | EXPLORATORY, not registered, computed from the committed per-slot table (no experiment ru... | bodmas lgbm: Pearson r 0.49 over 20 slots, 0.00 of slots below the ta... | [measured] |
| E-68 | EXPLORATORY, not registered, computed from the committed per-slot table `reports/tables/e... | LAMDA, never retrained: LightGBM 0.783 at slot 1, 0.770 at slot 12, f... | [measured] |
| E-69 | Hash manifest of the stored predictions of E0 to E4 and a private archive of the same fil... | 577 files, 7.20 GiB; every SHA-256 in `docs/predictions_manifest.csv`... | [measured] |
| L-12 | Transcend: Detecting Concept Drift in Malware Classification Models (Jordaney, Sharad, Da... | 7 authors; pp. 625-642 | [verified] at abstract level; the full ... |
| L-14 | Transcendent (Barbero, Pendlebury, Pierazzi, Cavallaro, arXiv 2010.03856; IEEE S&P 2022, ... | 5 years; 2 evaluators | [verified] at abstract level; the full ... |
| L-18 | Botacin and Gomes, Towards more realistic evaluations: the impact of label delays in malw... | up to 75%; about 30% | [verified] at abstract level; the full ... |
| L-30 | EMBER2024 (Joyce et al., arXiv 2506.05074; DOI 10.1145/3711896.3737431 per the arXiv reco... | over 3.2 million files; 6 formats | [verified] at abstract level; the full ... |
| P-12 | Known limits written before the results: BODMAS one useful refit per window and periodic ... | as stated | [verified] |

## Limits of chapter 8 (section 8.3): tick each one you consider correct and complete

- [ ] 1. Time labels.
- [ ] 2. Class prior.
- [ ] 3. Repeated feature vectors.
- [ ] 4. The pool design.
- [ ] 5. Two models.
- [ ] 6. E3 calibration set-up.
- [ ] 7. Evaluation by one metric.
- [ ] 8. Label noise and the VirusTotal threshold.
- [ ] 9. Temporal luck.
- [ ] 10. Simulated delay.
- [ ] 11. A simulated perfect analyst.
- [ ] 12. Dataset mix.
- [ ] 13. One alarm level per monitor.
- [ ] 14. Class prior confounds the metric.
- [ ] 15. What the "conformal" monitor is.
- [ ] 16. A seed extension decided after reading.
- [ ] 17. The RQ1 comparator is not stable to the last digit.
- [ ] 18. Predictions are not public.
- [ ] 19. The dynamic results are mostly LAMDA results.

## Paper (paper/main.tex)

- [ ] Introduction
- [ ] Background
- [ ] Protocol
- [ ] Simulator and assurance
- [ ] Experiments and pre-registration
- [ ] Results
- [ ] Reading the results together
- [ ] Threats to validity and limits
- [ ] Ethics and availability
- [ ] Conclusion

Paper-specific checks: every `\clm{...}` id exists (the build check already confirms this); no sentence claims priority; the contribution statement is word for word the guide's; the limits in the paper match chapter 8; the anonymous build (`paper/main-anon.tex`) shows no identifying text before submission.

## Things only you can decide while reading

- Whether the AI-use wording is right for the venue (the paper draft has none; the venue may require one).
- Whether the effects, all of hundredths of A-AUT, deserve the emphasis the abstract gives them.
- Whether the null result on monitors is worded as strongly as you are willing to stand behind.
