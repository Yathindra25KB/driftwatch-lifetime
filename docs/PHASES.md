# DriftWatch phase ledger

Status, evidence, commit and the hours the researcher reports, for every phase and gate. The `phase-closeout` skill updates this file at the end of each phase. Status values: NOT STARTED, IN PROGRESS, DONE, CUT. Gates are decided by the researcher from the gate card in plan §7; the evidence file decides, not mood.

## Phases

| # | Phase | Weeks (dates) | Planned h | Status | Evidence | Commit | Hours (actual) | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Foundations and governance | 1-2 (12-25 Oct 2026) | 8 | IN PROGRESS | | | | Started 10 Oct 2026 (before week 1); prompt rev 1.2 |
| 2 | Data ingestion and data cards | 1-2 (12-25 Oct 2026) | 10 | NOT STARTED | | | | Peak-memory cap to be proposed for 8 GB machine (rev 1.2) |
| 3 | Time slicer, C1-C3, leakage canary | 3 (26 Oct-1 Nov 2026) | 8 | NOT STARTED | | | | Never compress (plan §7) |
| 4 | Models, AUT/A-AUT, E0 baselines | 3-4 (26 Oct-8 Nov 2026) | 10 | NOT STARTED | | | | Never compress (plan §7) |
| 5 | Delay and budget simulator, E1 | 5-8 (9 Nov-6 Dec 2026) | 32 | NOT STARTED | | | | |
| 6 | Tier 1 grid (E2) and statistics | 9-11 (7-27 Dec 2026) | 24 | NOT STARTED | | | | prereg-v1 tag before first grid result |
| 7 | Tier 1 write-up and reproduction | 13-14 (4-17 Jan 2027) | 18 | NOT STARTED | | | | Week 12 is buffer |
| 8 | Conformal layer and selection (E3) | 15-17 (18 Jan-7 Feb 2027) | 23 | NOT STARTED | | | | prereg-v2 |
| 9 | Drift monitors and scoring (E4) | 18-19 (8-21 Feb 2027) | 18 | NOT STARTED | | | | prereg-v3 |
| 10 | Tier 3: cross-platform (E5), EMBER2024 (E6) | 20-21 (22 Feb-7 Mar 2027) | 0 (10 opt.) | NOT STARTED | | | | Optional; go/no-go Mon 22 Feb 2027; week 20 is buffer |
| 11 | Paper and capstone completion | 21-24 (1-28 Mar 2027) | 24 | NOT STARTED | | | | |
| 12 | Release, deployment, maintenance | 21-24 (1-28 Mar 2027) | 12 | NOT STARTED | | | | Irreversible steps need explicit go |

## Gates

| Gate | Decide on | Pass criteria (plan §7, summarised) | Status | Evidence | Commit | Notes |
|---|---|---|---|---|---|---|
| G1 | Sun 8 Nov 2026 (end wk 4) | Time-aware AUT(F1) below random-split F1 by the PREREG band on at least one dataset; real-data canary moves AUT toward random; constraint, AUT and canary tests green; no fit over 60 s or a shrink plan; reports/G1.md PASS | NOT DECIDED | | | Fail: fix the slicer; no simulator |
| G2 | Sun 6 Dec 2026 (end wk 8) | Simulator end to end on at least one dataset; test_queue_delay and spy test pass; regression fixture holds; E1 figure regenerates; pool ADR accepted; reports/G2.md PASS | NOT DECIDED | | | Fail: cut to one dataset and one model |
| Tier 1 results | Sun 27 Dec 2026 (end wk 11) | E2 complete; prereg-v1 predates results; tables and figures regenerate with no fits; stats-reviewer findings resolved | NOT DECIDED | | | Fail: use buffer week 12, no Tier 2 work in it |
| G3 | Sun 17 Jan 2027 (end wk 14) | Tier 1 results and core chapters exist; reproduce table1 matches on a clean machine; claims audit clean; reports/G3.md PASS | NOT DECIDED | | | Fail: cancel Tier 2 and Tier 3, finish the report |
| G4 | Sun 21 Feb 2027 (end wk 19) | E3 and E4 complete or honestly reported; prereg-v2/v3 predate results; reports/G4.md written | NOT DECIDED | | | Fail: rest is future work; no Tier 3 |
| Tier 3 go/no-go | Mon 22 Feb 2027 (wk 20) | G4 passed; cumulative hours at or under plan (151 h at end of wk 19); average at least 9 h/week over the last four weeks; capstone deadline not before end of wk 24 | NOT DECIDED | | | Fail: Phase 10 in polish mode or skipped |
| Release | Sun 28 Mar 2027 (end wk 24) | Paper at 8 pages or fewer, check_bib.py clean; chapters 1-9 complete; TestPyPI rehearsal passed; docs strict build clean; licence and ethics audit clean; researcher said go for PyPI and DOI | NOT DECIDED | | | Fail: smaller release; never rush irreversible steps |
| Hour check | Every week | Average at least 5 h/week over the last four weeks | OK | Weekly hours log | | Fail: single dataset; two-dataset comparison becomes future work |

## Weekly hours log

The researcher fills this in weekly (about 20 minutes, plan §5.1 step 9). Compare cumulative hours with plan Table 4.1. Planning assumption: about 8.5 h per working week (confirmed by the researcher on 10 Oct 2026).

| Week | Dates | Hours | Cumulative | 4-week average | Notes |
|---|---|---|---|---|---|
| 1 | 12 Oct - 18 Oct 2026 | | | | |
| 2 | 19 Oct - 25 Oct 2026 | | | | |
| 3 | 26 Oct - 01 Nov 2026 | | | | |
| 4 | 02 Nov - 08 Nov 2026 | | | | G1 |
| 5 | 09 Nov - 15 Nov 2026 | | | | |
| 6 | 16 Nov - 22 Nov 2026 | | | | |
| 7 | 23 Nov - 29 Nov 2026 | | | | |
| 8 | 30 Nov - 06 Dec 2026 | | | | G2 |
| 9 | 07 Dec - 13 Dec 2026 | | | | |
| 10 | 14 Dec - 20 Dec 2026 | | | | |
| 11 | 21 Dec - 27 Dec 2026 | | | | Tier 1 results |
| 12 | 28 Dec - 03 Jan 2027 | | | | Buffer |
| 13 | 04 Jan - 10 Jan 2027 | | | | |
| 14 | 11 Jan - 17 Jan 2027 | | | | G3 |
| 15 | 18 Jan - 24 Jan 2027 | | | | |
| 16 | 25 Jan - 31 Jan 2027 | | | | |
| 17 | 01 Feb - 07 Feb 2027 | | | | |
| 18 | 08 Feb - 14 Feb 2027 | | | | |
| 19 | 15 Feb - 21 Feb 2027 | | | | G4 |
| 20 | 22 Feb - 28 Feb 2027 | | | | Buffer; Tier 3 go/no-go |
| 21 | 01 Mar - 07 Mar 2027 | | | | |
| 22 | 08 Mar - 14 Mar 2027 | | | | |
| 23 | 15 Mar - 21 Mar 2027 | | | | |
| 24 | 22 Mar - 28 Mar 2027 | | | | Release |

## Revision 1.2: memory overrides (8 GB laptop, 7.2 GB usable)

The Phase 1 prompt (rev 1.2, 10 Oct 2026) states the real hardware and says it wins over any source document that assumes more memory. Places that assume more:

| Source | Location | Assumption | Status under rev 1.2 |
|---|---|---|---|
| Implementation plan | p. 1, "Scope you chose" box | "Hardware 16 GB RAM laptop"; verdict condition "LAMDA cached inside 16 GB in Phase 2" | Superseded: 8 GB (7.2 GB usable) |
| Implementation plan | p. 9, Table 4.5 | "LAMDA, dense float32 … 18.4 GB, Impossible on 16 GB"; "LAMDA, dense int8 … 4.60 GB, Possible but wasteful"; "keep peak memory under 6 GB" | Dense int8 (4.6 GB) is no longer safely possible; the 6 GB cap is replaced by a cap the researcher approves in Phase 2 |
| Implementation plan | p. 9, verdict table | "Memory (16 GB) PASS if LAMDA is streamed" | To re-test in Phase 2 against the approved cap |
| Implementation plan | p. 10, condition 3 | "LAMDA is cached inside 16 GB in Phase 2" | Superseded by the Phase 2 cap |
| Implementation plan | p. 16, Phase 2 description | LAMDA memory hazard sized against a 16 GB machine | Superseded |
| Implementation plan | p. 17, Phase 2 prompt and acceptance | "Peak memory must stay under 6 GB … because I have a 16 GB laptop"; "Measured peak memory … is below 6 GB" | Prompt text replaced in docs/prompts/phase-02.md (see below); acceptance uses the approved cap |
| Implementation plan | p. 18, Phase 2 fallback | "LAMDA cannot be cached inside 16 GB" | Read as "inside the approved cap" |
| Implementation plan | p. 43, answered questions and Q3 | "Hardware 16 GB RAM laptop"; Q3 default "8 threads, 16 GB RAM, 50 GB free [estimate]" | Measured 10 Oct 2026: Ryzen 7 6800H, 8 cores / 16 threads, 7.25 GB RAM visible, E: 121 GB free, C: 5.4 GB free |
| DriftWatch_Phase_Prompts.md | line 97 (Phase 2, deliverable 2) | "Peak memory must stay under 6 GB … 16 GB laptop" | Replaced in docs/prompts/phase-02.md |
| Build guide | (none found) | The guide states dataset sizes only, no laptop RAM | n/a |

## Prompt edits

| Date | File | Edit | Authority |
|---|---|---|---|
| 10 Oct 2026 | docs/prompts/phase-01.md | Verbatim rev 1.2 prompt; supersedes the Phase 1 text inside docs/source/DriftWatch_Phase_Prompts.md (byte-compared with the pasted prompt) | Phase 1 prompt rev 1.2 |
| 10 Oct 2026 | docs/prompts/phase-02.md | Replaced "Peak memory must stay under 6 GB (record the measured peak) because I have a 16 GB laptop." with "I have an 8 GB laptop (7.2 GB usable). Before building, measure free memory and propose a peak-memory cap for me to approve, then record the measured peak against it." | Phase 1 prompt rev 1.2, deliverable 5 |
| 10 Oct 2026 | docs/prompts/phase-03.md … phase-12.md | Split unchanged from docs/source/DriftWatch_Phase_Prompts.md (each byte-compared with its source block) | Phase 1 prompt rev 1.2 |

## VISTAS capstone rules

Answer given 10 Oct 2026: all unknown. The plan defaults stay in force until verified: deadline not before end of week 24; Markdown sources converted to DOCX/PDF; AI assistance disclosed; no demo.

| Rule | Status |
|---|---|
| Capstone deadline | unknown, to verify (if earlier than Sun 28 Mar 2027, Tier 3 and Phase 10 are removed and Phases 11-12 compressed) |
| Report template (Word or LaTeX) | unknown, to verify |
| Page rules | unknown, to verify |
| AI-assistance disclosure policy | unknown, to verify (see docs/ETHICS.md) |
| Demo expected | unknown, to verify |

## Phase 1 decisions (10 Oct 2026)

OS Windows-native (Git Bash + PowerShell tools); repository github.com/Yathindra25KB/Driftwatch- (private until G3, public by Phase 12); licence MIT (ADR-0002); PyPI distribution `driftwatch-lifetime`, import `driftwatch` (ADR-0003); one long session; branch protection with required CI on main once pushed; about 8.5 h per week.

## Deviations from source documents

| Item | Deviation | Reason |
|---|---|---|
| `cli` | Module `src/driftwatch/cli.py`, not a `cli/` package | Phases 7 and 12 name `src/driftwatch/cli.py` (PROTOCOL D11) |
| Plan Appendix B | MultiEdit dropped; PowerShell covered; hook paths anchored on `$CLAUDE_PROJECT_DIR`; no Bash deny rules | Current Claude Code docs (ADR-0001) |

## Relief levers used

None.
