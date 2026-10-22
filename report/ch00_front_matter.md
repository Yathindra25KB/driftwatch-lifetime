# How Long Does a Malware Detector Last? Label Delay, Analyst Budget and Conformal Monitoring in One Time-Aware Protocol

Yathindra K B, VISTAS. Capstone report, due 10 Dec 2026. Source: the repository `Yathindra25KB/Driftwatch-` (MIT licence); every number in this report has a row in `docs/CLAIMS.md`.

> Status: draft written by Claude Code for the researcher to rewrite and defend; the title is the researcher's choice recorded in `docs/PHASES.md`. Items in square brackets are for the researcher.

## Abstract

A malware detector is trained on samples up to a date and used on samples that arrive later; as malware and benign software change, it stays useful for a limited time. How long depends on what can be done after deployment: whether it can be retrained, on which labels, how late those labels arrive, how many an analyst can afford, and whether anything tells the operator when to retrain. This report measures that in one time-aware protocol: training data strictly older than test data, test slots from their own time window, a fixed malware share, and the area under the F1-versus-time curve averaged over rolling windows (A-AUT). It uses two pre-extracted feature datasets, LAMDA for Android and BODMAS for Windows PE, and two detectors, logistic regression and LightGBM, and never opens or runs a malware sample.

Four experiments were pre-registered before their first result and run to completion; one extension of the number of seeds, decided after reading earlier rows, is disclosed in chapter 8. (1) A random split overstates the time-aware score by an amount that depends on how the comparison is built, and the gap is not attributed to temporal leakage alone. (2) On LAMDA, retraining on bought labels helps by hundredths of A-AUT and a delay of three slots (three months) costs about as much; on BODMAS the effects are smaller and the design allows one refit per window. (3) Choosing samples by uncertainty or conformal credibility was above random choice at equal labels, and the advantage was smaller after a delay, but it is not separated from a change in class mix, and F1 at a fixed threshold also moves with the share of malware in a slot. (4) No drift monitor beat retraining every third slot at the same labels spent. At this budget the whole difference between never retraining and retraining every third slot is itself about a hundredth of A-AUT, and the monitors alarmed in most slots, so this is a result about these settings and not about drift monitoring in general. The numbers, intervals and the limits that bound each reading are in chapters 7 and 8 and in the claims ledger [E-30, E-35, E-42, E-59].

"Lifetime" is read through A-AUT and the per-slot F1 curves; no single figure of months until a stated fall in F1 is reported. LAMDA's labels come from antivirus detection counts with an unpublished scan date and discard ambiguous apps, so detection here may look easier than in operation [D-15, D-16]. The contribution is the protocol, the open code and the pre-registered grid, with every number traceable to a result file and a commit, and a set of small or null effects under stated settings. A negative result is reported as one. Cross-platform replication and EMBER2024 were not run.

## Reading guide

| If you want | Read |
|---|---|
| The question and the claim | Chapter 1 |
| Why the numbers are what they are and how far to trust them | Chapter 3, then chapter 8 |
| What was built | Chapter 6 |
| What was found | Chapter 7, summarised in chapter 9 |
| How it fits the literature | Chapters 4 and 5 |

Terms are defined where first used. A glossary of the terms used throughout: **concept drift**, a change over time in the relation between a sample's features and its label; **lifetime**, how long a detector stays useful before it must be retrained; **AUT**, the normalised area under the F1-versus-time curve; **A-AUT**, its mean and standard deviation over rolling windows; **label delay**, the number of slots between a sample being queried and its label becoming usable; **analyst budget**, the number of samples whose true label can be obtained per slot; **conformal p-value**, a score saying how unusual a sample is compared with labelled calibration samples; **drift monitor**, a test that raises an alarm when a slot looks unlike a reference.

## How this report was produced, and what an examiner can check

[Researcher: the faculty's policy on disclosing AI assistance is not known (`docs/PHASES.md`). Replace this paragraph with the wording the policy requires.] The report and the code were produced with Claude Code (Anthropic), working as the engineering lead under the researcher's direction, with the researcher deciding every scope, pre-registration, gate and publication step. The researcher rewrites and defends the text. Everything that could be checked mechanically is: the claims audit (`scripts/claims_audit.py`) refuses a number without a ledger row, the bibliography check (`scripts/check_bib.py`) resolves every reference against Crossref or arXiv, the tables regenerate from stored predictions, and reviews (leakage, statistics, a simulated hostile review) are saved under `docs/reviews/` and `reports/`. Those reviews were written by separate instances of the same model family that wrote the code and the drafts, so they are self-review, not independent review. [Researcher: say here what you wrote and what you checked yourself, and add any review by a person.]

<!-- length-table:start -->
## Length against the guide's page budget

Counted from the chapter files on 22 Oct 2026 [T-02]. The chapters are shorter than the guide's budget in several places; they were not padded, and each row says why.

| Chapter | Words [T-02] | Pages at 400 words (estimate) | Guide's budget (pages) | Why this length |
|---|---|---|---|---|
| 1 | 1155 | 2.9 | 5 | The question, the claim and the scope fit in this length; no result is stated here. |
| 2 | 1099 | 2.7 | 15 | Kept to what the study uses. No survey of the threat landscape: one sourced figure only (section 2.6), because threat statistics date quickly and none is used in the analysis. |
| 3 | 2277 | 5.7 | 12 | Covers the registered analysis for E0 to E4; a longer chapter would repeat the registrations. |
| 4 | 1526 | 3.8 | 12 | Abstract-level by design (no full paper was read); a longer chapter would need the papers themselves. |
| 5 | 1572 | 3.9 | 8 | Abstract-level; the researcher's reading of the closest papers is what would lengthen it. |
| 6 | 3369 | 8.4 | 12 | Complete for the simulator, the conformal layer and the monitors. |
| 7 | 4829 | 12.1 | 15 | Tables are in the repository (`reports/tables/`) and the ledger; the chapter reports the registered contrasts and their limits. |
| 8 | 2875 | 7.2 | 6 | Longer than the budget because the limits are listed in full. |
| 9 | 1251 | 3.1 | - | No budget in the guide. |
| All, with the front matter | 21178 | | 85 or so | Well under the guide's total. Which chapters to lengthen, and whether the faculty has a page limit, are the researcher's decisions. |
<!-- length-table:end -->

## Acknowledgements

[Researcher: to be written.]
