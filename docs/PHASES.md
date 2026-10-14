# DriftWatch phase ledger

Status, evidence, commit and the hours the researcher reports, for every phase and gate. The `phase-closeout` skill updates this file at the end of each phase. Status values: NOT STARTED, IN PROGRESS, DONE, CUT. Gates are decided by the researcher from the gate card in plan §7; the evidence file decides, not mood.

## Phases

| # | Phase | Weeks (dates) | Planned h | Status | Evidence | Commit | Hours (actual) | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | Foundations and governance | 1-2 (12-25 Oct 2026) | 8 | DONE | [CI run 38028624827](https://github.com/Yathindra25KB/Driftwatch-/actions/runs/38028624827) (Linux + Windows green, 258 tests, 45/45 guardrail scenarios each); [guardrail review](reviews/guardrail-review.md); [ADR-0001](DECISIONS/ADR-0001-tooling-and-guardrails.md); [PROTOCOL](PROTOCOL.md) | d634836 | 3 | Done 10 Oct 2026, before week 1; prompt rev 1.2. See "Phase 1 closeout" below |
| 2 | Data ingestion and data cards | 1-2 (12-25 Oct 2026) | 10 | DONE | [inventory](../reports/data_inventory.md); [notes, Q1-Q7, leakage review](../reports/data_inventory_notes.md); [LAMDA card](data_cards/lamda.md); [BODMAS card](data_cards/bodmas.md); [ADR-0004](DECISIONS/ADR-0004-slot-definition.md) (ACCEPTED); [CLAIMS D-01..D-14](CLAIMS.md); `data/manifest.json` | 14da248 | 2 | Done 10 Oct 2026, before week 1. Cap 1.5 GB approved; LAMDA peak 0.87 GB (rebuild 0.93), BODMAS 0.56 GB. Guard allowlist widened (ADR-0001). Cache v2 after leakage review. See "Phase 2 closeout" below |
| 3 | Time slicer, C1-C3, leakage canary | 3 (26 Oct-1 Nov 2026) | 8 | DONE | [slicer review, 2 passes](reviews/slicer-review.md); [mutation matrix 15/15](../reports/mutation_matrix.md); [slicing run](../reports/slicing_run.md); [window options](../reports/window_options.md); [ADR-0005](DECISIONS/ADR-0005-windows-and-size-gate.md) (ACCEPTED); [ADR-0004 addendum 1](DECISIONS/ADR-0004-slot-definition.md); [CLAIMS W-01..W-07](CLAIMS.md) | 9b8e958 | 3 | Done 11 Oct 2026, before week 3. Canary tested on seeded drift, not the signal-free fixture; real-data canary left to Phase 4 by design. See "Phase 3 closeout" below |
| 4 | Models, AUT/A-AUT, E0 baselines | 3-4 (26 Oct-8 Nov 2026) | 10 | DONE | [G1 evidence](../reports/G1.md); [E0 report](../reports/e0_baselines.md); [tables](../reports/tables/e0_baselines.csv); [fit times](../reports/tables/fit_times.csv); [ADR-0006](DECISIONS/ADR-0006-metrics-threshold-scaling.md) (PROPOSED); [CLAIMS E-01..E-12, M-01, M-02, B-01..B-05, T-01](CLAIMS.md) | 57e2003 | 2 (reported as under 3) | Done 11 Oct 2026, before week 3. G1 criteria met on LAMDA; BODMAS AUT above 0.90 left as an open alarm; ADR-0006 awaits acceptance; guide sanity band `[verify]`. See "Phase 4 closeout" below |
| 5 | Delay and budget simulator, E1 | 5-8 (9 Nov-6 Dec 2026) | 32 | DONE | [G2 evidence](../reports/G2.md); [ADR-0007](DECISIONS/ADR-0007-pool-composition-and-budget.md) (PROPOSED); [E1 figure](../reports/figures/e1_random_vs_time.png); [E1 tables](../reports/tables/e1_summary.csv); [label influence](../reports/tables/label_influence_lamda.csv); [chapters 2, 5, 6](../report/ch06_method.md); [CLAIMS S-01..S-06, E-13..E-21](CLAIMS.md) | a5c8604 | 3 to 6 (reported) | Done 13 Oct 2026, before week 5. G2 criteria met except: ADR-0007 not accepted (researcher), second leakage-review pass did not complete (usage limit). Open: which comparator carries RQ1; parallel runs do not fit the 1.5 GiB cap. See "Phase 5 closeout" below |
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
| G1 | Sun 8 Nov 2026 (end wk 4) | Time-aware AUT(F1) below random-split F1 by the PREREG band on at least one dataset; real-data canary moves AUT toward random; constraint, AUT and canary tests green; no fit over 60 s or a shrink plan; reports/G1.md PASS | NOT DECIDED (evidence ready) | [reports/G1.md](../reports/G1.md): criteria met on LAMDA (gap 0.14 to 0.15, canary PASS, tests green, fits under 9 s, reruns identical); BODMAS alarm open | 57e2003 | Researcher decides. Fail: fix the slicer; no simulator |
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
| 0 | 10-11 Oct 2026 (before week 1) | 10 | 10 | | Phase 1 (3 h), Phase 2 (2 h), Phase 3 (3 h) and Phase 4 (2 h, reported as under 3), researcher-reported |
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
| Phase 1 plan: restart after step E | No restart needed | Hooks went live through the settings file watcher (verified live, ADR-0001) |
| Phase 1 plan: GitHub repo creation | Existing private repo `Driftwatch-` (created 6 Oct 2026) used as `origin` | Researcher supplied it |
| Guard download allowlist | `json.schemastore.org` added | Validating settings against the docs-linked schema (a schema-rejected settings file disables the guardrails) |
| phase-closeout skill | Authored with skill-creator guidance; its LLM eval/viewer loop was not run | Deterministic helper scripts are unit-tested; the prompt runs the checklist by hand in Phase 1 |

## Relief levers used

None.

## Phase 1 closeout (10 Oct 2026)

Checklist run by hand, as the prompt requires for the phase that creates the skill.

| Check | Result |
|---|---|
| Clean clone of `phase-01-foundations` at `180368d`: `uv sync --frozen && uv run pytest -q && uv run ruff check . && uv run ruff format --check .` | 258 passed; All checks passed!; 60 files already formatted |
| `uv run python scripts/check_guardrails.py` (local, Windows) | 45/45 scenarios passed; latency median: guard 189 ms, reviewer guard 176 ms, formatter 346 ms, re-injection 181 ms, Stop gate 803 ms (runs the tests: justified) |
| CI run 38028624827 on `0d2b8ca` | lint-test (ubuntu) success: 258 passed, 45/45; windows-smoke success: 258 passed, 45/45. `d634836` only loosens scenario 44 to stop expecting Phase 1 to be IN PROGRESS (local: 258 passed, 45/45); CI reruns on the ledger push |
| Live checks in Claude Code | Guard blocked real Bash and PowerShell force pushes and an unlisted download; permissions denied a `docs/source/` write and a `.env` read; formatter, scoped rules and skill discovery observed; `/memory` lists CLAUDE.md and the rules, and approval prompts appeared for guardrail edits (researcher check) |
| `.claude/settings.json` vs https://json.schemastore.org/claude-code-settings.json | ok -- validation done |
| CITATION.cff (`cffconvert --validate`) and `.github/workflows/ci.yml` (`check-jsonschema` vendor.github-workflows) | valid; valid |
| HANDOFF check (`check_handoff.py 1`) | 35 items, all exist |
| Adversarial review | 21 findings: 20 fixed with regression tests (`6cdb589`), 1 accepted fail-closed ([review](reviews/guardrail-review.md)); residual risks in ADR-0001 |
| ADRs | ADR-0001 ACCEPTED (researcher), ADR-0002 ACCEPTED (MIT), ADR-0003 ACCEPTED (`driftwatch-lifetime`) |
| GitHub | `main` and `phase-01-foundations` pushed to the private repo; `main` protected (required check `lint-test`, strict; PR required with 0 approvals; enforced for admins; no force pushes or deletions) |
| Low-priority items | `report/ch01_introduction.md` skeleton; `paper/references.bib` with 13 identifier-verified entries; unverified items in `paper/REFERENCES_TODO.md` |

### Phase 1 config hashes

| File | SHA-256 |
|---|---|
| uv.lock | `ef115bb63578ddd01a6826c68eb6a52d275cdfe05084e59faa63ac8b8b705d22` |

(no configs/*.yaml yet)

### Phase 2 prerequisites
- Disk: E: has 121 GB free (allow about 30 GB for raw files and caches [estimate]). C: has only 5.4 GB free and holds the uv cache and the uv-managed Pythons. Moving `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR` to E: before Phase 2 is recommended (researcher's machine setting).
- Start the LAMDA download early in week 1. `huggingface.co` and the BODMAS host must be added to the guard's download allowlist by a Phase 2 CHANGE_REQUEST.
- RAM: 7.25 GB visible, about 0.6 GB free at the 10 Oct check. Phase 2 measures free memory and proposes a peak-memory cap for approval.

## Phase 2 closeout (10 Oct 2026)

| Check | Result |
|---|---|
| `uv run pytest -q`; `ruff check .`; `ruff format --check .` | 322 passed; All checks passed!; 82 files already formatted |
| `uv run python scripts/check_guardrails.py` | 45/45 scenarios passed |
| `uv run driftwatch data verify` (data/ and the clean-rebuild root data/rebuild_check/) | OK, 0 problems on both; 1,088 cache files byte-identical between them (cache v2) |
| Builds under the approved 1.5 GB cap | LAMDA 1,008,381 rows, 120 monthly units, peak 0.87 GB (rebuild 0.93), 93.1 s, 119.7 MB; BODMAS 134,435 rows, 424 weekly units, peak 0.56 GB, 23.4 s, 1,231.2 MB |
| HANDOFF check (`check_handoff.py 2`) | 8 items, all exist |
| Leakage review (leakage-reviewer subagent) | 13 findings (2 high, 4 medium, 7 low). 11 were fixed with tests in `bba2692` (cache v2). 2 are carried to the Phase 3, 4 and 8 ADRs (slot-boundary hold-outs; past-only duplicate sensitivity) and recorded in ADR-0004 |
| ADRs | ADR-0004 ACCEPTED by the researcher (LAMDA month; BODMAS 2 weeks from 2019-08-26; M = 50, strict gaps; placeholder-dated benign rows excluded). ADR-0001 change request (download allowlist) approved |
| Sources | LAMDA HF commit `ad9614bdd5556767f97ced2fce797c2f06408ebf`; BODMAS Google Drive file IDs in data/manifest.json. The BODMAS download worked without a quota error |

Deviations and notes:
- LAMDA timestamps come from the root `metadata.csv` (`added`, AndroZoo's collection date), which the README does not describe. `year_month` matches it for every row.
- The BODMAS dataset licence is not stated by its authors (the code is BSD-2-Clause): open question Q5.
- Cache v1 (the first build) is archived in the manifest. Its files under `data/cache/*/v1/` and the rebuild root `data/rebuild_check/` can be deleted by the researcher; the guard blocks recursive deletes outside temp folders.
- The Phase 2 prompt's CHANGE_REQUEST was "none". The allowlist change was approved at plan time as the CHANGE_REQUEST noted in "Phase 2 prerequisites".

### Phase 2 config hashes

| File | SHA-256 |
|---|---|
| uv.lock | `1c7380afb87669761538e9cc8fec08f100a1b94d5e5bf719ca9b61b26745afd0` |

(no configs/*.yaml yet)

## Phase 3 closeout (11 Oct 2026)

| Check | Result |
|---|---|
| `uv run pytest -q`; `ruff check .`; `ruff format --check .` | 481 passed; All checks passed!; 112 files already formatted |
| `uv run python scripts/check_guardrails.py` | 45/45 scenarios passed |
| HANDOFF check (`check_handoff.py 03`) | 7 items, all exist |
| Constraints | C1, C2, C3 raise `ConstraintViolation` subclasses (never warnings); tests implement the guide's definitions literally; property tests run against an independent integer-arithmetic oracle |
| Mutation checks | 15 of 15 deliberate breakages killed by the real suites, baseline 120 tests green ([matrix](../reports/mutation_matrix.md), CLAIMS W-07) |
| Canary | Planted drift: AUT 0.76-0.79 (true timestamps) to 0.96-0.98 (shuffled), random-split F1 0.96-0.98, 4 seeds. No drift: `NO_GAP`. Leak caught by C2/C1, and by the canary when both are disabled. Limit pinned: leaking 1 of 10 evaluation slots is not seen by the canary alone |
| Full-dataset slicing | LAMDA 47 windows / 564 evaluation slots, 28.6 s, peak 0.40 GB; BODMAS 2 windows / 24 evaluation slots, 2.9 s, peak 0.69 GB; 0 densified; no C1-C3 violation (CLAIMS W-04) |
| Leakage review (leakage-reviewer subagent) | Pass 1: 14 findings (0 blocker, 3 major, 11 minor); pass 2: 9 findings (1 major latent, 7 minor, 1 informational). No C1-C3 violation in either pass. All fixed except two carried to Phase 5 (Window object reaches held-back labels; per-row seen-before mask for E0) and one documented as accident-proofing |
| ADRs | ADR-0005 ACCEPTED by the researcher (LAMDA nT 4, nE 12, stride 3; BODMAS nT 3, nE 6, stride 2; M = 50; cap and flag; sensitivity ratio 5%). ADR-0004 addendum 1 amends item 7 (selectors get only `EvalSlot.public()`) |

Deviations and notes:
- The committed synthetic fixture has features independent of labels, so the canary movement is tested on seeded in-memory timelines with planted drift (`driftwatch.data.synthetic`). The fixture caches and a built drifting BODMAS-format cache prove the script end to end.
- The real-data canary was deliberately not run: windows must not be chosen after seeing real AUT. Phase 4 runs `scripts/leakage_canary.py` with the ADR-0005 windows (gate G1).
- C3 follows the researcher's "cap and flag" choice: slots already below the target ratio keep all rows and are flagged. 31 of the 62 LAMDA headline months are below 10% malware; the ADR states the prevalence spread as a threat to validity.
- Carried to Phase 5: selectors, policies and monitors take only `OpaqueSlot` and `TrainWindow`, never `Window` or `EvalSlot`; the spy test lands with the first selector; the E0 duplicate mask is built from the simulator's real training pool.
- Branch `phase-03-time-slicer` is stacked on the unmerged `phase-02-data-ingestion` and `phase-01-foundations`; nothing has been pushed.

### Phase 3 config hashes

| File | SHA-256 |
|---|---|
| uv.lock | `1c7380afb87669761538e9cc8fec08f100a1b94d5e5bf719ca9b61b26745afd0` |

(no configs/*.yaml yet; window specs carry their own digest in every slicing manifest)

## Phase 4 closeout (11 Oct 2026)

| Check | Result |
|---|---|
| `uv run pytest -q`; `ruff check .`; `ruff format --check .` | 669 passed; All checks passed!; 133 files already formatted |
| `uv run python scripts/check_guardrails.py` | 45/45 scenarios passed |
| HANDOFF check (`check_handoff.py 04`) | 10 items, all exist |
| E0 evidence runs (clean commit cd72d83, `--require-clean`, five seeds) | BODMAS 180 window rows, 3,185,890 predictions, 965.7 s, peak 1.40 GiB; LAMDA 420 window rows, 23,210,920 predictions, 2,200.3 s, peak 0.90 GiB ([E-01](CLAIMS.md)) |
| Reproducibility | Seed 0 of every variant rerun on the same commit: 16 of 16 cell prediction hashes equal, 120 of 120 window rows equal incl. comparator columns ([E-11](CLAIMS.md)) |
| Fit time | Slowest fit 8.6 s (LightGBM default, BODMAS); configured models 1.2 to 3.5 s; the 60 s limit holds, no shrink needed ([B-05](CLAIMS.md)) |
| Leakage review (leakage-reviewer subagent) | No temporal leak. 1 major (comparator class prior confounded with time) and 7 minor findings: fixed with tests in `92018af`, except the recovery-time caveat, which is documented in ADR-0006. 4 informational: the bench docstring and LightGBM seed-sensitivity are fixed; the `window_id` join note is in the table builder; sealed labels inside the runner are by convention only, so Phase 5 must give selectors only `OpaqueSlot` and add the spy test |
| Stats review (stats-reviewer subagent) | 5 major, 5 minor, 1 informational: iid bootstrap replaced by moving-block bootstrap, unsupported "gap understated" sentence removed, comparator caveats added, training-prior range and slot denominators corrected, LAMDA reproducibility run and E-rows written before the report was committed. Applied in `2010858`, `2e1702a`, `57e2003` |
| Gate G1 | Evidence in [reports/G1.md](../reports/G1.md): criteria met on LAMDA; BODMAS AUT above 0.90 left open. **Not decided by Claude** |
| ADRs | ADR-0006 PROPOSED (values frozen 11 Oct 2026 under the researcher's delegation, before any E0 result); acceptance is the researcher's |

Deviations and notes:
- **Runner location.** `driftwatch.sim.{config,results,runner}`, not new top-level modules: `tests/test_smoke.py` pins the package map to guide section 8. `driftwatch run <config.yaml>` is in `cli.py`.
- **First E0 run discarded unread.** Started at commit 5893df7, stopped after the leakage review found the comparator confound and missing comparator counts; replaced by the run of the amended code (ADR-0006, process note). Its partial output `results/e0/00420e5e86baa4ea/` is not used and can be deleted by the researcher (the guard blocks recursive deletes outside temp folders).
- **LR max_iter 300 to 1000** after a convergence-only probe on a training window (no scores printed): LAMDA converges at 325 iterations.
- **Memory.** Dense LR keeps float32 and the random-split step frees its pooled copy; the BODMAS full run peaked at 1.40 GiB, 7% under the 1.5 GiB cap. Phase 5 pools will be larger: re-measure before adding labels to the training pool.
- **Comparator.** Headline comparator is prior-matched on training class counts but not per slot (global malware cap), so RQ1's attribution to leakage in the random split is not tested by E0.
- **Not done.** The guide's sanity band (`[verify]`: PDF not decodable here, values not supplied); a per-slot-matched comparator; any investigation of the BODMAS alarm.
- **Branch.** `phase-04-models-e0` is cut from `origin/main` after the Phase 3 PR merged; nothing has been pushed.

### Phase 4 config hashes

| File | SHA-256 |
|---|---|
| configs/e0_bodmas.yaml | `36bc82c2a4c11421cc926dcb5781961ca42cfac63ea407df0f1eefbf565ca0d5` |
| configs/e0_lamda.yaml | `114dd2337c82dea1fadfdad7c180396dbb4912c833526aeefbe1fdac456954d2` |
| uv.lock | `2c5a7dfa5000f370ed1b4c1bba4c86c689a18a5bcce570be8b996fddddbca00e` |

Run config hashes (code version, config and lock file): BODMAS `608f15e1a6628732eb71e3e2fc1bac3ede1c704f874649b320fd1f9abc9b7957`, LAMDA `613c0f98e507a8ad9d2ea70d340da5107aeb3820c773d46083d4ba167395341f`.

## Phase 5 closeout (13 Oct 2026)

| Check | Result |
|---|---|
| `uv run pytest -q`; `ruff check .`; `ruff format --check .` | 815 passed, 1 deselected, 84 s; All checks passed!; 160 files already formatted |
| `uv run python scripts/check_guardrails.py` | 45/45 scenarios passed |
| HANDOFF check (`check_handoff.py 5`) | 14 items, all exist |
| Queue, spy, regression, determinism, resume | [S-01..S-06](CLAIMS.md): d in {0,1,2,3} with property tests; spy at component and runner level; fixture ordering; three deliberate breakages caught; a BODMAS arm killed at 3 of 18 units resumed to the identical predictions hash |
| Evidence runs (clean commit 2bd12d6, `--require-clean`) | Label influence: LAMDA and BODMAS, never / 0.5% / 5%, 3 seeds; E1: both datasets, five seeds, per-slot matched comparator ([E-13..E-19](CLAIMS.md)). Longest refit 9.9 s |
| Memory | BODMAS E1 peak 1.47 GiB (98.2% of the 1.5 GiB cap); two BODMAS arms in two threads crossed the cap ([E-20](CLAIMS.md)) |
| Leakage review (leakage-reviewer subagent) | Pass 1: no temporal leak; 2 major (latent cache-key hazard, ADR-0007 not yet written), 5 minor, 6 informational. Fixed with tests in `0117287` and later, except three carried (feature-vector hashes through queue and pool; calibration share not yet consumed; `code_version` ignores untracked files). **Pass 2 did not complete (API usage limit); rerun on `b3ff456..HEAD`** |
| Stats review (stats-reviewer subagent) | 1 blocker (comparator choice moves the RQ1 verdict), 5 major, 4 minor, 2 informational: achieved-ratio, decomposition and spread columns added, class split and per-arm denominators added, "modest" wording removed, run log and CLAIMS rows written |
| Gate G2 | Evidence in [reports/G2.md](../reports/G2.md). **Not decided by Claude** |
| ADRs | ADR-0007 PROPOSED; new-label weight 1 and no truncation are the researcher's choices (11 Oct 2026), the other rules await acceptance |

Deviations and notes:
- **Branch.** `phase-05-simulator-e1` is cut from `phase-04-models-e0` (Phase 4 is not merged); nothing has been pushed.
- **E0 path moved onto the sealed door.** The E0 loop now scores through `SealedSlot`; E0 predictions are unchanged (E-16 reproduces the A-AUT of E-02 and E-03 to four decimals, and E0's window-level gap is reproduced from the E1 window table).
- **Config schema.** `selector`, `delay`, `budget_pct`, `pool` and `policy: periodic` are open; `nonconf`, `monitors` and monitor-triggered retraining stay refused. Weight other than 1 and any truncation are refused by ADR-0007. E0 configs hash as before.
- **Store.** Per-unit checkpoints with `--resume` (needs a clean tree); predictions carry `series`, `policy`, `selector`, `delay`, `budget_pct`.
- **Parallelism.** `run_many` and `--workers` exist and are tested; at the approved cap they cannot be used on BODMAS (G2, Open decision B).
- **Failed and superseded runs.** Three BODMAS diagnostic runs at 716608f failed on the memory cap; three at fa614c3 were superseded after leakage-review code changes and give an identical table; listed in ADR-0007 and [E-21](CLAIMS.md). Directories under `results/li/` and `results/resume_check/` can be deleted by the researcher.
- **Chapters.** Drafts of chapters 2, 5 and 6; sources retrieved 13 Oct 2026; descriptions from search summaries are marked `[verify]`; new references are listed in the chapters, not added to `paper/references.bib`.
- **Not done.** Uncertainty and credibility selectors, conformal layer, monitors (Phases 8 and 9); a stratified within-slot comparator; a noise-floor arm for the label-influence diagnostic; a seen-before mask from the real pool.
- **Environment.** `C:` was at 100% during the closeout and 291 tests errored once on temporary files; a rerun on the same tree passed. Free space on `C:` before the next long run.

### Phase 5 config hashes

| File | SHA-256 |
|---|---|
| configs/e0_bodmas.yaml | `36bc82c2a4c11421cc926dcb5781961ca42cfac63ea407df0f1eefbf565ca0d5` |
| configs/e0_lamda.yaml | `114dd2337c82dea1fadfdad7c180396dbb4912c833526aeefbe1fdac456954d2` |
| configs/e1_bodmas.yaml | `a1677b3162b1f3070bfedd52621f0837131ea1183855cd86a3c403644d72bce5` |
| configs/e1_lamda.yaml | `f55e605dd645c625b0e62caacf675f8d142bb030ab214520a2de8ddf6015476d` |
| configs/li_bodmas_b0.5.yaml | `ca077fd06a0332232da946ff41915183f7d4a99f77308c5a9f33caf1da6def20` |
| configs/li_bodmas_b5.yaml | `79e2a06f22082633d6324ec09bfee8dcd8c7e05ebee2331ff2eacf2761c0b24f` |
| configs/li_bodmas_never.yaml | `12592db8311419b049284352ffcceae0731368e24460e732e1d6a09c6c74da36` |
| configs/li_lamda_b0.5.yaml | `f1e2ce49c04fb1ee8b106e50d5eb92c8befb283f19d0e787a18957fce69749db` |
| configs/li_lamda_b5.yaml | `cae058f1d6eddcd619b88b8923f8f65f67a14f0bcf30f79f34816674e5b6d2ef` |
| configs/li_lamda_never.yaml | `3b94e93bb5b95eafdf07b033d6270d1bfb92a3088d37017ffc0cbf7e7945dc44` |
| uv.lock | `2c5a7dfa5000f370ed1b4c1bba4c86c689a18a5bcce570be8b996fddddbca00e` |

Run config hashes (code version, config and lock file; commit 2bd12d6): E1 BODMAS `45ea4054625ca8253d5d27f51a40f36c5057348c20ac5c15b4c5c1070a25b122`, E1 LAMDA `df138cc96fa9162219b70318b7179da382baf257d3e253a4b536b3b15de44e42`; label influence BODMAS never `ed348555adec05b60a97e5066b3ea149fd8ae44a42e3915d2c7df91509cf1636`, 0.5% `8076e24d690b20ad…` (see CLAIMS E-13, E-14 for the 16-digit run directories).
