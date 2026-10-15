# Chapter 4: Recent techniques and attacks (first draft)

> Status: first draft written by Claude Code in Phase 7 for the researcher to rewrite, verify and defend. Every source below was reached on **2026-10-15**, by reading an arXiv abstract page or a search result summary; **none of the full papers was read**. Statistics are quoted as the abstract states them and carry the source and the access date; every paragraph with a number is marked **[verify]** until the paper itself is read. The chapter is written from the defender's side: it says what kinds of techniques exist and what they imply for evaluation, and it contains no recipe for building evasive malware (hard rule 12; `docs/ETHICS.md`). Target length: about 12 pages; this draft is shorter on purpose.

## 4.1 Why this chapter exists

The study measures how long a detector stays useful when labels arrive late. That question sits inside a larger and fast-moving field. This chapter lists what has been published recently on the three things that decide a detector's lifetime: how drift is handled, how an adversary can shorten the lifetime on purpose, and what language models bring to the analyst's side of the loop. It exists so that chapter 5 and the discussion in chapter 8 can say which of these the study does not address.

## 4.2 Handling drift: training, adaptation and detection

Three families appear in the 2024 to 2026 abstracts read for this draft.

**Training for stability.** TIF (Zheng et al., arXiv 2502.05098, submitted 7 Feb 2025, accessed 2026-10-15) groups training data into environments by the date an app was observed and combines contrastive learning with invariant gradient alignment, so that features that matter in every period are preferred over features that matter only in one. The abstract reports gains over earlier methods on a decade-long dataset, "especially in early deployment stages" **[verify]**. The idea attacks decay at its source and is complementary to buying labels.

**Adaptation without, or with few, true labels.** ADAPT (Alam, Piplai, Rastogi, arXiv 2507.08597, 11 Jul 2025, accessed 2026-10-15) uses pseudo-labels from unlabeled data, on five datasets across Android, Windows and PDF **[verify]**. LFreeDA (Li and Bertino, arXiv 2511.14963, 18 Nov 2025, accessed 2026-10-15) adapts a Windows detector with pseudo-labels from unsupervised domain adaptation and reports being near methods given 300 true labels **[verify]**. MADCAT (Roh et al., arXiv 2505.18734, 24 May 2025, accessed 2026-10-15) adapts at test time using a small balanced sample of test data **[verify]**. These methods spend no analyst time, which makes them a natural zero-budget reference for the budget axis of this study.

**Selecting what to label and detecting drift.** Chen, Ding and Wagner (USENIX Security 2023) combine contrastive learning with active learning to choose samples for analysts; DREAM (He et al., arXiv 2405.04095, 7 May 2024, accessed 2026-10-15) detects drifting samples in a contrastive autoencoder and reports matching the best existing method on a Drebin classifier with 76.6% fewer newly labelled samples **[verify]**. Minnei et al. (arXiv 2603.28396, 30 Mar 2026, accessed 2026-10-15) combine active and semi-supervised learning on Android and Windows and report annotation cost cut by up to 90% at performance near full-label retraining **[verify]**. Structure-based drift measures from decision-tree rulesets are studied on EMBER2024 by Kalny et al. (arXiv 2604.22629, 24 Apr 2026, accessed 2026-10-15), who find that fixed two-month windows with feature-level correlation worked most reliably and that no single method dominates **[verify]**.

What these abstracts do not say is how late the labels are or what a fixed per-period budget costs; the delay and the budget enter the study as parameters.

## 4.3 Evaluation: benchmarks and the evaluation trap

LAMDA, the Android benchmark used here, was accepted at ICLR 2026 and spans 2013 to 2025 without 2015, with more than one million samples, about 37% malware and 1,380 families, according to its arXiv page and ICLR poster page (arXiv 2505.18551, accessed 2026-10-15) **[verify: figures match CLAIMS D-01 and D-02, but the page was read through a search summary]**. McNdroid (Kamol et al., arXiv 2605.06894, 7 May 2026, accessed 2026-10-15) covers the same years with static, dynamic and call-graph features and reports degradation over growing train-test gaps **[verify]**. For Windows PE, the datasets used here are BODMAS and, later, EMBER2024.

Two evaluation points recur. First, results depend strongly on how time is cut: the extended TESSERACT paper and Chow et al. (arXiv 2506.23814, discussed in chapter 5) identify factors that move reported performance even with temporal splits. Second, confidence is not free: Aurora (Herzog, Eusebi, Cavallaro, arXiv 2505.22843, 28 May 2025, revised 21 Jan 2026, accessed 2026-10-15) asks whether the confidence estimates that selective and active methods rely on are trustworthy, and reports that current approaches are fragile across datasets with different drift **[verify]**. That is a caution for any uncertainty- or credibility-based selector, including those of RQ3.

## 4.4 Adversaries

An adversary does not wait for drift. In the problem space, an attacker modifies a malicious file so that it keeps its behaviour but changes what the classifier sees; in the feature space, the change is applied to the features directly, which is easier to study and usually less realistic. Surveys organise the literature by attack domain and generation technique (Aryal et al., "A Survey on Adversarial Attacks for Malware Analysis", arXiv 2111.08223, published in IEEE Access, December 2024 according to a search summary read on 2026-10-15) and by the assumptions, attacks and defenses of the "arms race" (Li, Li, Ye and Xu, arXiv 2005.11671, 2020) **[verify: both read through search summaries]**. One finding of the latter is that the effectiveness of practical evasion depends largely on how much freedom the attacker has in the problem space, and that adversarial training depends on the defender's ability to find the strongest attack **[verify]**.

What this means for the study: all datasets here are benign-process data from natural time evolution; the study measures decay from drift only and does not model an adaptive adversary. A detector that looks durable here is not thereby robust to evasion. The repository contains no attack code (`docs/ETHICS.md`).

## 4.5 Language models on the analyst's side

Recent papers evaluate large language models for malicious-code analysis. Examples found through a search on 2026-10-15 and read only as summaries: a benchmark of 13 language models on 4,070 PyPI packages, 370 of them malicious, reporting that models do better at coarse detection than at pinpointing individual malicious signals (arXiv 2602.16304); a study that decompiles Windows executables with Ghidra and classifies them with language models and concludes that standard models are not yet robust enough to replace traditional anti-virus software (arXiv 2601.09035); and a retrieval-augmented system for JAR files reporting roughly 97% mean detection accuracy on a 3,839-executable benchmark (arXiv 2510.15567) **[verify: all three from search summaries]**. For this study the relevance is on the label side: if language models shorten the time an analyst needs to label a sample, the delay parameter shrinks and the budget grows. The grid is built to read exactly that trade-off, but no language model is used here.

## 4.6 What to verify before this chapter is used

1. Open each arXiv paper named above and check the quoted statistic against the paper, not the abstract summary.
2. Replace the search-summary sources in 4.4 and 4.5 with the papers themselves, or drop them.
3. Add a 2025 or 2026 survey on problem-space attacks and defenses if one exists; the search of 2026-10-15 found none.
4. Decide whether this chapter should be shortened to a page for the VISTAS report (the guide allows compressing chapters 2 to 4 first).
