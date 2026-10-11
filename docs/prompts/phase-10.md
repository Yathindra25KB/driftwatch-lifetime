PHASE 10 | Tier 3: cross-platform (E5), EMBER2024 (E6) | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Two modes in one prompt. MODE A (Tier 3) runs E5 (and, only if I say so, E6). MODE B (polish) hardens what exists. Choose the mode from the go checklist, record the decision, and stop if the checklist says no.

MODE: A or B (I will state it in CHANGE_REQUEST)

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/PREREG.md
- docs/prereg/addendum-v3.md
- docs/CLAIMS.md
- reports/G4.md
- scripts/run_grid.py
- scripts/make_tables.py
- scripts/make_figures.py
- src/driftwatch/data/loaders.py
- configs/e3_bodmas.yaml
- configs/e3_lamda.yaml
- configs/e4_bodmas.yaml
- configs/e4_lamda.yaml

## GO CHECKLIST (evaluate first, write the result to reports/G5-tier3-decision.md)
- Gate G4 passed, and reports/G4.md says Tier 2 is complete or honestly reported.
- Cumulative hours are within plan and my average over the last four weeks is at least 9 hours per week (I will tell you the numbers).
- My department's capstone deadline is not earlier than the end of week 24.
If any item fails, switch to MODE B without discussion.

## MODE A DELIVERABLES
1. E5 (RQ5): repeat the Tier 2 headline contrasts (E3 selection, E4 monitors) on whichever of LAMDA or BODMAS they have not yet been run on, using the existing configs. Pre-register in docs/prereg/addendum-v4.md first (comparison of directions and magnitudes across platforms, how disagreement will be judged), I approve, then tag prereg-v4.
2. E6, only if I explicitly ask and there are at least two spare weeks: an EMBER2024 Win32 subset by week through the official tooling or the Hugging Face files (read the current dataset card first and stop if the schema differs from what the guide describes), the challenge set as motivation for the delay range, and per-family Mondrian. Optionally flip a small share of returned labels as a noise-sensitivity check. Treat all of it as appendix material.
3. Tables and figures regenerated from stored predictions; claims ledger updated.

## MODE B DELIVERABLES
1. Review test coverage and fix gaps in constraint, queue, conformal and monitor tests. 2. Remove dead code and unreproducible scripts. 3. Make every config in configs/ runnable or delete it. 4. Speed up CI. 5. Audit results/ for stale outputs (produced by superseded code) and list them. 6. Documentation clean-up for a first-time reader.

## CONSTRAINTS
- Same slicer, simulator, pool design, metric and statistics as before. No tuning. No new modelling ideas.
- EMBER2024 files are large: never load more than the Win32 weekly subset; stream, cache per week, record disk and memory use.
- Anything not finished by the end of week 22 becomes future work, stated as such.

## ACCEPTANCE (show evidence)
- Go checklist result recorded with the numbers I gave you.
- Mode A: addendum tagged before any cell runs; outputs regenerate with no fits. Mode B: lint and coverage clean; no orphan scripts.
- Every number added anywhere is in docs/CLAIMS.md.

## WORKING METHOD
Plan mode first; start by evaluating the checklist and ask me for the numbers it needs.

## RE-ENTRY
- update: apply CHANGE_REQUEST (for example add E6 after all). Re-evaluate the checklist, then continue.
- maintain: rerun E5 smoke cells and the coverage report on updated dependencies.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- docs/prereg/addendum-v4.md
- configs/e5_cross_platform.yaml
- reports/tables/e5_cross_platform.csv
- reports/G5-tier3-decision.md
