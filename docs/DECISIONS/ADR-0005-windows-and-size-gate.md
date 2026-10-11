# ADR-0005: Window parameters (nT, nE, stride), size gate and ratio policy

**Status:** PROPOSED
**Date:** 2026-10-11
**Deciders:** Yathindra (researcher, approves); Claude Code (engineering lead, proposes)
**Phase:** 3

This ADR fixes the open values "nT, nE, stride per dataset; size-gate numbers; ratio policy incl. the sensitivity ratio" in PROTOCOL §5, and records the C3 policy the researcher chose on 10 Oct 2026. It uses only slot counts (ADR-0004 slots, `reports/window_options.md`). No model has been trained and no AUT has been seen on real data. The real-data canary is deliberately not run until this ADR is accepted.

## Context
- **Slots (ADR-0004, accepted).** LAMDA calendar months; BODMAS 2-week slots from 2019-08-26; M = 50; gaps, partial slots and gate-failing slots are never bridged; BODMAS placeholder-dated benign rows are excluded.
- **Protocol (PROTOCOL §2, D1).** Train on the first K = 3 to 4 slots, then step through the rest; A-AUT needs rolling windows (`nT = K`, `nE`, `stride`). Retraining every 3 slots; delay d ∈ {0, 1, 2, 3} slots.
- **C3 (guide §3, §6).** "Subsample malware to a fixed ratio: start with 10%, plus one sensitivity check at another ratio" (D4: the second ratio is not given).
- **What the data allows (`reports/window_options.md`, `reports/slicing_run.md`):**

  | Dataset | Usable runs at 10%, M = 50 | Slots below 10% in those runs |
  |---|---|---|
  | LAMDA | 62 months (2018-11..2023-12), 12 (2013-09..2014-08), 7 (2017-10..2018-04), 4, 3, 3, 2, 2, 1, 1 | 31 of the 62; 36 of 97 in all |
  | BODMAS | 9 slots (2019-08-26..2019-12-16), 17 slots (2020-02-10..2020-09-21) | 0 of 26 |

- **C3 cannot be reached by dropping malware alone in a slot whose raw share is already below the target.** In LAMDA's headline run 31 of 62 months have less than 10% malware (down to about 2.6%).

## Options considered

### 1. Ratio policy for slots already below the target
- **A. Cap and flag (researcher's choice, 10 Oct 2026).** Malware-only seeded subsampling; a below-target slot keeps every row, is marked `below_target`, and its achieved ratio is logged per slot. C3 raises if a benign row is dropped, the ratio ends above target, a reachable slot misses target, or malware is dropped needlessly.
- **B. Strict.** Below-target slots fail the gate. LAMDA's 62-month run splits into runs of at most 9 months; A-AUT on LAMDA is then essentially impossible.
- **C. Also thin benign.** Exact 10% everywhere, but it departs from "subsample malware" in the guide and discards benign data.

### 2. Sensitivity ratio
Counts at M = 50 (cap and flag):

| Ratio | LAMDA usable slots | LAMDA below target | LAMDA longest run | BODMAS usable | BODMAS below target |
|---|---|---|---|---|---|
| 5% | 95 | 8 | 47 (run 2018-11..2019-12 splits: 14 + 47) | 26 | 0 |
| 10% (headline) | 97 | 36 | 62 | 26 | 0 |
| 20% | 97 | 50 | 62 | 27 | 1 |

- **5%.** A genuinely different ratio is reached in 87 of 95 LAMDA slots and in every BODMAS slot. It costs LAMDA two gate failures (2016-06 has 457 benign and 2020-01 has 933, so 5% allows 24 and 49 malware) and splits the longest run at 2020-01.
- **20%.** Mostly meaningless on LAMDA: 50 of 97 slots keep all their malware and sit below 20%.

### 3. Window shape (nT, nE, stride)
Design constraints, all from the guide and the inventory: K = 3 to 4; nE must cover several retrain periods (3 slots) and the delay (up to 3 slots, labels usable from t+1+d); a window must fit a usable run. Candidates are in `reports/window_options.md` (windows, distinct evaluation slots, evaluation reuse).

| Dataset | Candidate | Windows | Distinct eval slots | Eval reuse |
|---|---|---|---|---|
| LAMDA | nT 4, nE 12, stride 3 | 16 | 57 | 3.4 |
| LAMDA | nT 4, nE 12, stride 6 | 8 | 54 | 1.8 |
| LAMDA | nT 3, nE 6, stride 3 | 20 | 66 | 1.8 |
| BODMAS | nT 3, nE 6, stride 2 | 6 | 20 | 1.8 |
| BODMAS | nT 3, nE 6, stride 3 | 4 | 18 | 1.3 |
| BODMAS | nT 4, nE 8, stride 2 | 3 | 12 | 2.0 |

A BODMAS window needs `nT + nE <= 9` to use the first (9-slot) run at all; `3 + 6` fits exactly.

## Decision (proposed)
1. **Ratio policy: cap and flag (option 1A).** Headline target 10%, **sensitivity ratio 5%**. A below-target slot is a valid evaluation slot with its achieved ratio reported; the gate is "at least M malware kept after C3". Every table that reports AUT also reports the per-slot achieved ratio.
2. **Size gate: M = 50** for both datasets (as ADR-0004), recomputed at each ratio. Training slots use the same gate (the rule is per slot; their rows are not subsampled).
3. **LAMDA: nT = 4, nE = 12, stride = 3** (months). Sixteen windows in the 62-month run, each with four retrain periods; stride 3 keeps every window's retrain phase aligned with the 3-slot retraining period (D7).
4. **BODMAS: nT = 3, nE = 6, stride = 2** (2-week slots). Six windows: one in the 9-slot run and five in the 17-slot run. Retraining every 3 slots gives two events per window, and a delay of 3 slots (6 weeks) leaves only the first evaluation slots influenced by delayed labels, which is a stated limit of this dataset.
5. **Single-run protocol.** `nE = None` (train on the first nT slots of a run, evaluate the rest) is available for the E0 never-retrain baseline; rolling windows are used for A-AUT.
6. **Seeds.** The malware draw depends on `(seed, slot id)`, so a slot's subsample is identical in every window and grid cell (paired comparisons), and the 5% draw is nested in the 10% draw.

## Consequences
- **Easier.** The slicer, the manifests and the canary read these numbers from one `WindowSpec`. Window counts are fixed before any result is seen.
- **Harder or riskier.**
  - **Prevalence varies by slot in LAMDA** (about 2.6% to 10%; 31 of 62 headline months are below 10%). F1 depends on prevalence, so part of any AUT movement on LAMDA can come from the ratio, not the detector. The report must show the per-slot achieved ratio, the 5% check, and a plot of F1 against achieved ratio.
  - **Overlapping windows** (reuse 3.4 on LAMDA, 1.8 on BODMAS): A-AUT's standard deviation understates uncertainty. Report effect sizes with bootstrap intervals over slots, as the guide requires.
  - **BODMAS has few windows** (6) and short delay coverage; claims on BODMAS are limited accordingly.
  - **At 5% the LAMDA headline run splits** (14 + 47 slots): the 5% check uses windows planned at 5%, not the 10% windows.
  - **C3 deviates in spirit** from "reaches the target ratio" for below-target slots; this is recorded here rather than hidden.
- **Revisit when:** the researcher rejects a value; ADR-0006 fixes the metric and threshold; the Phase 4 real-data canary does not pass; or a dataset version changes the counts (rerun `scripts/window_options.py`).

## Evidence and references
- `reports/window_options.md`, `reports/tables/window_segments_*.csv`, `reports/tables/window_options_*.csv` (commit 4ce5cba).
- `reports/slicing_run.md` (full-dataset slicing at commit 4ce5cba).
- `reports/mutation_matrix.md` (14 of 14 deliberate breakages caught).
- `docs/reviews/slicer-review.md` (first pass: no C1-C3 violation; interface findings fixed or carried to Phase 5).
- ADR-0004; PROTOCOL §2, §4, §5, D1, D4, D7; Build Guide §3, §6, §8.
