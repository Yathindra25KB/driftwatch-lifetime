# Chapter 1: Introduction (skeleton)

> Status: skeleton from Phase 1. The researcher writes this chapter in their own words in Phase 7. Target length: about 5 pages (build guide §13 [verify the page rules against VISTAS's template]). Numbers may enter only through docs/CLAIMS.md; none are used here.

## 1.1 Motivation
- Malware classifiers look strong on random train/test splits, then decay as malware and benign software change (concept drift).
- Analysts receive true labels late and can label only a small number of samples per period.
- Sources to cite: pendlebury2019tesseract, chow2025beyond, botacin2025labeldelays (paper/references.bib).

## 1.2 Problem statement
- How long does a detector stay useful under one time-aware protocol (C1–C3; AUT and A-AUT) when labels arrive late and the labelling budget is fixed, and can drift monitors tell when to retrain?

## 1.3 Research questions
- RQ1 to RQ5 exactly as registered in docs/PREREG.md (copy the wording after the prereg-v1 tag).

## 1.4 Contribution
- Use the build guide's statement (§4): "We study malware detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring in a single time-aware protocol, reported with A-AUT, on Android and Windows PE data."
- Never describe the work as "first"; state what was measured. Position against the neighbours in docs/related_work_addendum.md (Phase 7).

## 1.5 Scope, data and ethics
- Pre-extracted feature files only (LAMDA, BODMAS); no malware is executed or redistributed (docs/ETHICS.md).
- Tier 1, Tier 2 and optional Tier 3 scope, as finally delivered (from docs/PHASES.md).

## 1.6 Report outline
- One line per chapter, 2 to 9, written once the chapters exist.
