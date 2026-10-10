# ADR-0004: Slot definition, minimum-size gate and gap handling

**Status:** PROPOSED
**Date:** 2026-10-10
**Deciders:** Yathindra (researcher, approves); Claude Code (engineering lead, proposes)
**Phase:** 2

This ADR fixes the open value "slot length per dataset, minimum-size gate, gap handling" in PROTOCOL §5. It uses only the data inventory: occupancy, timestamps, gaps and duplicates. No model has been trained and no result has been seen. Values left to Phase 3 (nT, nE, stride, the C3 sensitivity ratio) are named, not decided.

## Context
Evidence, all from `reports/data_inventory.md`, its tables in `reports/tables/`, and `reports/data_inventory_notes.md` (commit `ade5116`, 10 Oct 2026):

**Timestamps**
- **LAMDA.** The slotting time is AndroZoo `added` (the date the APK entered AndroZoo), at second resolution, for all 1,008,381 apps. `year_month` agrees with it for every row.
- **BODMAS.** Malware first-seen times run 2019-08-29 to 2020-09-30, at second resolution. Benign timestamps:
  - are mostly date-only (85.8% at midnight);
  - include 5,877 at `2020-01-01 00:00:00`;
  - include 13,514 before the first malware week, going back to 2007.

**Occupancy**
- **LAMDA months.**
  - The span 2013-06 to 2025-01 has 140 slots: 20 empty and 120 populated.
  - At M = 50 (defined below), 97 months pass. The longest unbroken passing run is **62 months, 2018-11 to 2023-12**; its weakest month has 114 malware and 933 benign.
  - Month sizes range from a few hundred to 55,000 apps.
- **LAMDA quarters.** 48 slots: 5 empty, 39 passing at M = 50. The longest run is **29 quarters, 2017Q4 to 2024Q4**.
- **BODMAS, dense period 2019-W35 to 2020-W40 (58 ISO weeks, no empty week):**

  | Length | Slots | Fail M = 50 | Passing segments at M = 50 |
  |---|---|---|---|
  | 1 week | 58 | 9 | longest run 25 weeks |
  | 2 weeks | 29 | 2 (2020-01-13, 2020-01-27; 27 and 14 benign) | 2019-08-26 to 2020-01-12 (10 slots); 2020-02-10 to 2020-10-04 (17 slots) |
  | 4 weeks | 15 | 1 | longest run 9 |

**Gaps**
- LAMDA has 17 consecutive empty months from 2014-09 to 2016-01 (the "2015 gap"), plus 2013-07, 2013-08 and 2017-06.
- BODMAS has no empty week in the dense period.

**Duplicates**
- **LAMDA.** 23.7% of rows (238,576) repeat a feature vector seen in an earlier month. 2,177 vectors carry both labels (54,835 rows).
- **BODMAS.** 4 rows repeat an earlier week's vector.

**Rules in force**
- C1–C3 (PROTOCOL §2, §4).
- `.claude/rules/data.md`: rolling windows never span a data gap; slots that fail the minimum-size gate are skipped and logged.
- Delay d ∈ {0, 1, 2, 3} slots and retraining every 3 slots (PROTOCOL §2).
- Mismatch D2: delay is promised "per month" but measured in slots.

## Options considered

### 1. LAMDA slot length
- **A. Month.**
  - Pros:
    - The delay unit equals the guide's "per month" promise, which resolves D2 for Android.
    - The longest passing run of 62 slots gives many rolling windows for A-AUT.
    - Finer than quarters, so drops are dated more precisely.
  - Cons: many small or unbalanced months outside 2018-11 to 2023-12, and per-slot F1 is noisier.
- **B. Quarter.**
  - Pros: smoother counts, and the run reaches 2024Q4.
  - Cons:
    - Only 29 slots in the longest run.
    - d = 3 means 9 months of delay, beyond the 1–3 months the guide motivates.
    - Retraining every 3 slots means once every 9 months.
- **C. Year** (the guide's fallback). Not needed: the 1.5 GB cap held, the timestamps are usable, and 12 yearly slots with a 2015 hole would leave almost no rolling windows.

### 2. BODMAS slot length (within the dense period)
- **A. 1 week.** 58 slots, but 9 fail the gate, and the longest run is 25.
- **B. 2 weeks.** 29 slots, of which only the 2 Jan 2020 slots fail. Two segments of 10 and 17 slots. d = 3 means 6 weeks of delay.
- **C. 4 weeks.** 15 slots and one failure, which leaves runs too short for an initial K = 3–4 window plus a meaningful evaluation tail.

### 3. Minimum-size gate
A slot passes when C3 subsampling to 10% malware keeps at least M malware, that is n_malware ≥ M and n_benign ≥ 9M.
- **M = 30.** The most slots pass, but per-slot F1 rests on 30 positives.
- **M = 50.** The longest runs barely change from M = 30 (LAMDA months 62 vs 66), and each slot holds at least 500 samples after C3.
- **M = 100.** It costs BODMAS 1-week slots heavily but changes nothing for 2-week slots or for LAMDA's longest monthly run.

### 4. Gaps and failing slots
- **A.** Empty slots and gate-failing slots both count as **gaps**: a rolling window (training slots plus evaluation slots) never contains or bridges one. Windows are placed only inside passing segments.
- **B.** Skip failing slots but let windows bridge them. This contradicts the data rule and would hide C2 problems (for example, BODMAS Jan 2020 has about 1,000 malware against 14 to 27 benign per slot).

### 5. Duplicate feature vectors
- **A.** Keep all rows as published. Report, for every evaluation slot, the share of rows whose vector appeared in any earlier slot (the inventory already computes this). Run one pre-declared sensitivity in Phase 4 (E0) with those rows removed from evaluation.
- **B.** Drop cross-slot duplicates everywhere. This changes the population the detector faces and departs from TESSERACT practice.
- **C.** Ignore them. The guardrails forbid this (`.claude/rules/data.md`).

## Decision (proposed; the researcher decides)
1. **LAMDA: monthly slots (option 1A).** Months are calendar months in UTC, keyed by the AndroZoo `added` time. Quarters stay available in the cache for a sensitivity check, not for the headline.
2. **BODMAS: 2-week slots (option 2B)** within the study window, which starts at **2019-08-26 (Monday of ISO week 2019-W35, the first week with malware)** and ends at 2020-10-04. The slots are anchored at 2019-08-26; the cache's anchor at the first populated week (2007-01-01) is 660 weeks earlier, so the two alignments coincide. The 13,514 benign rows dated before the window are outside the study. They stay in the cache, and the data card reports them.
3. **Gate M = 50** for both datasets, recomputed after C3 subsampling at whatever ratio Phase 3 fixes (the sensitivity ratio may change which slots pass, and that is logged).
4. **Gaps (option 4A).** Empty and gate-failing slots are gaps. Windows never span them, and every skipped slot is logged with its counts. This produces:

   | Dataset | Passing segments (M = 50) |
   |---|---|
   | LAMDA months | 2018-11 to 2023-12 (62); 2013-09 to 2014-08 (12); 2017-10 to 2018-04 (7); 2017-01 to 2017-04 (4); shorter ones listed in the inventory |
   | BODMAS 2-week | 2019-08-26 to 2020-01-12 (10); 2020-02-10 to 2020-10-04 (17) |

   Phase 3 (ADR-0005) chooses nT, nE and the stride, and therefore which segments are long enough. The headline LAMDA window lies in 2018-11 to 2023-12. 2015 is never interpolated or bridged.
5. **Duplicates (option 5A).** Keep the rows. Report the seen-before share per evaluation slot. Run the E0 sensitivity with cross-slot duplicates removed from evaluation (declared now, before any result). Label-conflicting vectors stay as published and are counted in the data card.
6. **Delay units (D2).** LAMDA delay is reported in months (1 slot = 1 month). BODMAS delay is reported in slots and in days (1 slot = 14 days), so the "per month" statement applies to LAMDA only, unless Phase 6 converts with stated assumptions.

## Consequences
- **Easier.** Phase 3 gets unambiguous slot IDs (`month:YYYY-MM`, `2w:YYYY-MM-DD`). Loaders already exist for both, and every gate decision traces back to a CSV row.
- **Harder or riskier.**
  - The LAMDA headline excludes 2013–2018 and 2024–2025. Early drift is studied only in shorter segments or in the quarterly sensitivity check.
  - BODMAS offers two short segments, so its A-AUT will rest on few windows.
  - The BODMAS benign timestamp semantics (Q2) remain a threat to validity for C1 on Windows.
- **Revisit when:** the researcher rejects a choice; Phase 3 fixes nT/nE or the C3 sensitivity ratio (re-run the gate tables); the LAMDA or BODMAS authors answer Q1 or Q2; or a new dataset version arrives (a new manifest entry, then rerun the inventory and update this ADR by addendum).

## Evidence and references
- `reports/data_inventory.md`; `reports/tables/data_lamda_slots_month.csv`, `data_lamda_slots_quarter.csv`, `data_bodmas_slots_{1w,2w,4w}.csv`, `data_*_duplicates_per_slot.csv`; `reports/data_inventory_notes.md` (Q1–Q7).
- `data/manifest.json` (LAMDA HF commit `ad9614bd…`, BODMAS Drive file IDs, all hashes).
- Clean rebuild: 1,088 cache files byte-identical; `driftwatch data verify` OK (inventory notes §7).
- PROTOCOL §2, §5, D2, D9, D10, D13, D14; `.claude/rules/data.md`.
- LAMDA paper arXiv 2505.18551 (accessed 10 Oct 2026); BODMAS page https://whyisyoung.github.io/BODMAS/ (accessed 10 Oct 2026).
