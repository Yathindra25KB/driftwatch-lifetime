PHASE 7 | Tier 1 write-up and reproduction | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Make Tier 1 capstone-safe and publicly presentable on its own: a one-command reproduction of Table 1, a README, the core report chapters and a claims audit. No new experiments. Decide Gate G3 with evidence.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/PREREG.md
- docs/CLAIMS.md
- reports/tables/e2_aaut.csv
- reports/G2.md
- scripts/make_tables.py
- scripts/make_figures.py
- report/ch02_landscape.md
- report/ch03_analysis.md
- report/ch05_related_work.md
- report/ch06_method.md
- report/ch07_experiments.md
- README.md

## DELIVERABLES
1. A single reproduction command, driftwatch reproduce table1: from a clean machine it fetches data through the manifest (with the documented manual path if a download fails), runs the BODMAS Table 1 in the locked environment and compares the output with the stored table within a stated tolerance. A smoke mode on the synthetic fixture runs in CI in a few minutes.
2. README: what DriftWatch is and is not, quickstart, headline Tier 1 results with their limits, ethics statement (feature files only; describes how detectors decay, not how to evade them), citation.
3. Report chapters in report/ as Markdown with a bibliography: ch01 introduction, ch05 related work, ch06 method, ch07 experiments (E0 to E2), ch08 discussion and limitations (partial), plus a first draft of ch04 latest techniques and attacks from current, dated sources. Integrate and polish ch02, ch03, ch05 to ch07. Page targets from the guide: 5, 15, 12, 12, 8, 12, 15, 6 (compress ch02 to ch04 first if time is short). Write for a final-year student audience; define every term at first use.
4. docs/related_work_addendum.md: the newer neighbours listed in Appendix G of the plan PDF, each read at least in abstract and placed against label delay, analyst budget and conformal monitoring. Never claim "first". Use the guide's suggested contribution statement.
5. A claims audit: map every number and every sentence of consequence in the chapters and README to docs/CLAIMS.md (file and commit); list what the results do not show.
6. reports/G3.md: PASS or FAIL against the criteria below.

## CONSTRAINTS
- No new experiments, no changed analysis. If a result looks odd, open an issue in the repo and report it; do not rerun until it looks better.
- Every statistic about the threat landscape (chapters 2 to 4) must carry a source and an access date, or be marked [verify]. Do not invent figures.
- The chapters are drafts for me to rewrite in my own words and verify; mark paragraphs that still need my verification.

## ACCEPTANCE (show evidence)
- Clean-clone reproduction of Table 1 on BODMAS matches the stored table within tolerance; runtime recorded. CI runs smoke mode.
- No claim in README or chapters 1, 5 to 8 lacks a CLAIMS.md entry. Search shows no use of the word first as a contribution claim.
- leakage-reviewer and stats-reviewer have re-checked the final text and tables; findings resolved.
- reports/G3.md states PASS or FAIL against: Tier 1 results exist, core chapters exist, reproduction works.

## STOP RULE (guide, week 14)
If Tier 1 results and the core chapters do not exist at the end of week 14, cancel Tier 2 and Tier 3 completely and finish the report.

## WORKING METHOD
Plan mode first; propose the chapter outline with page budgets before drafting. Ask me only for decisions that are mine (what to cut, G3).

## RE-ENTRY
- update: apply CHANGE_REQUEST (new section, new result, corrections). Update CLAIMS.md first, then text; rerun the claims audit.
- maintain: rerun reproduce table1 in a clean environment; check links and references; report drift.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- src/driftwatch/cli.py
- scripts/reproduce_table1.py
- README.md
- report/ch01_introduction.md
- report/ch04_latest_techniques.md
- report/ch08_discussion.md
- docs/related_work_addendum.md
- reports/G3.md
