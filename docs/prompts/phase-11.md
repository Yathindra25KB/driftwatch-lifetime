PHASE 11 | Paper and capstone completion | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Turn the evidence into two documents that share one claims ledger: an 8-page workshop-style paper and the complete capstone report (chapters 1 to 9). Build verification into the writing so nothing unverified, invented or over-claimed survives.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/PREREG.md
- docs/CLAIMS.md
- docs/related_work_addendum.md
- reports/G3.md
- reports/G4.md
- report/ch01_introduction.md
- report/ch02_landscape.md
- report/ch03_analysis.md
- report/ch04_latest_techniques.md
- report/ch05_related_work.md
- report/ch06_method.md
- report/ch07_experiments.md
- report/ch08_discussion.md
- reports/tables/e2_aaut.csv
- reports/tables/e3_selection.csv
- reports/tables/e4_monitors.csv

## DELIVERABLES
1. paper/main.tex: 8 pages or fewer, two-column ACM-style template as a working assumption until I choose a venue. Content: problem and motivation, the protocol (C1-C3, slots, delay, budget, policies, selectors, monitors, metrics), results for E0 to E4 from the ledger only, limitations (timestamp type, label noise and the VirusTotal threshold, temporal luck, simulated delay, simulated perfect analyst, dataset mix), ethics statement, artifact appendix pointing to the release. Use exactly the contribution statement from the guide's section 4 ("We study ... in a single time-aware protocol, reported with A-AUT, on Android and Windows PE data") and position against the neighbours in docs/related_work_addendum.md. Never claim first.
2. Complete the report in report/: ch07 results (E0 to E4, plus a Tier 3 appendix if it was run), ch08 discussion and limitations, ch09 conclusion and future work; a fact-check pass over ch02 to ch04 so every statistic carries a source and access date or is removed.
3. scripts/check_bib.py: resolve every reference in the paper and the report against Crossref or arXiv by identifier and compare title, authors and year; fail on any mismatch or unresolved entry.
4. An independent simulated review: use a fresh subagent that has not seen the drafts' history to write a hostile workshop review (soundness, novelty, reproducibility, ethics); save reports/simulated_review.md; answer each point in the text or in the limitations.
5. docs/submission_checklist.md: venue candidates with current deadlines and page limits retrieved now (mark [verify]), anonymisation needs, artifact requirements, licence and ethics statements.

## CONSTRAINTS
- Every number and claim of consequence comes from docs/CLAIMS.md. If a number is missing, run no experiment: mark the gap and ask me.
- The text you produce is a draft for me to rewrite and defend; keep sentences plain, define terms at first use, and flag paragraphs I must verify.
- No invented references, statistics or quotations. If you cannot verify a source, say so.
- Respect the guide's honesty rules: contribution is the protocol plus open code, a negative result is a result, no word first.

## ACCEPTANCE (show evidence)
- The paper compiles at 8 pages or fewer; every number is traceable in docs/CLAIMS.md.
- check_bib.py passes with zero unresolved or mismatched entries.
- A text search shows no use of first as a contribution claim; limitations cover the five threats listed above.
- reports/simulated_review.md exists and each point has a response.
- Chapters 1 to 9 are complete, consistent with the paper's numbers, and within the guide's page budgets or a stated reason.

## WORKING METHOD
Plan mode first. Show me the section-by-section outline with page budgets for both documents. Ask me only for decisions that are mine (venue, what to cut).

## RE-ENTRY
- update: apply CHANGE_REQUEST (reviewer comments, a new result, a venue switch). Update CLAIMS.md first, then text; rerun check_bib.py and the claims audit.
- maintain: re-check links, references and any statistic older than six months (threat-landscape facts expire).

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- paper/main.tex
- paper/references.bib
- report/ch09_conclusion.md
- scripts/check_bib.py
- reports/simulated_review.md
- docs/submission_checklist.md
