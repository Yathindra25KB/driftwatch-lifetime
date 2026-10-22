# Claims audit

Files audited: README.md, report\ch01_introduction.md, report\ch02_landscape.md, report\ch03_analysis.md, report\ch04_latest_techniques.md, report\ch05_related_work.md, report\ch06_method.md, report\ch07_experiments.md, report\ch08_discussion.md, report\ch09_conclusion.md.
Paragraphs and tables with numbers: 107; with a resolving claim id: 102; marked [verify]: 5; uncovered: 0.
Claim ids cited: 110. Unresolved ids: 0. Cited rows lacking a source file or commit: 0. 'first' used as a contribution claim: 0.
**Result: PASS**

## Uncovered paragraphs (a number with no resolving claim id)
- none

## Unresolved claim ids
- none

## Cited rows without source file or commit
- none

## 'first' as a contribution claim
- none

## Pending (marked [verify]; to be checked by the researcher)
- report\ch01_introduction.md:3: > Status: draft written by Claude Code for the researcher to rewrite in their own words and defend; updated 22 Oct 2026 for the finished Tie...
- report\ch03_analysis.md:41: The two stages count within-window variation twice, so the interval is wider than a plain standard error would give: about the square root o...
- report\ch06_method.md:3: > Status: draft written by Claude Code in Phase 5 for the researcher to rewrite and defend. Sections 6.1 to 6.5 describe code that exists an...
- report\ch06_method.md:85: - **Short windows on BODMAS.** With six evaluation slots and a retraining period of three, a window has one useful retraining event (before ...
- report\ch07_experiments.md:3: > Status: draft written by Claude Code in Phase 6 for the researcher to rewrite, verify and defend. Every number carries a claim id from `do...

## What the results do not show
- That the gap between random-split F1 and time-aware AUT is *caused* by temporal leakage: the per-slot comparator reaches a lower malware ratio than the time-aware series on LAMDA, and the E0 and per-slot comparators disagree about the 0.05 band on LAMDA (P-14, E-19).
- A delay curve on BODMAS: with nE = 6 and retraining every third slot there is one useful refit per window, and periodic equals never at a delay of three by construction (P-12).
- Independent replication on LAMDA: its 16 rolling windows are about four independent 12-month blocks, and logistic regression is deterministic given its pool, so seeds are draws of the C3 subsample and of the selection, not replicates of the model (P-12).
- That more labels do not help when a flat result appears at the smallest budget: retraining changed 0.2% to 2.1% of decisions in the earlier diagnostic (P-13).
- That conformal credibility adds anything over probability-based uncertainty (E3 does not separate them), or that a drift monitor beats periodic retraining: in E4 none did at a budget of 1% (E-59, E-60).
- Anything about other platforms or EMBER2024: E5 and E6 (Tier 3) have not been run.
- Anything about evasion or adversarial examples: the study describes decay, not defeat (docs/ETHICS.md).
- Results on another machine: every cell was run on one laptop; numeric drift elsewhere is reported, not corrected (docs/GRID.md).
