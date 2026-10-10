# ADR-0004: Slot definition, minimum-size gate and gap handling

**Status:** ACCEPTED (by the researcher, 10 Oct 2026)
**Date:** 2026-10-10
**Deciders:** Yathindra (researcher, approves); Claude Code (engineering lead, proposes)
**Phase:** 2

This ADR fixes the open value "slot length per dataset, minimum-size gate, gap handling" in PROTOCOL §5. It uses only the data inventory: occupancy, timestamps, gaps and duplicates. No model has been trained and no result has been seen. Values left to Phase 3 (nT, nE, stride, the C3 sensitivity ratio) are named, not decided. The text reflects the leakage review of 10 Oct 2026 (cache v2).

## Context
Evidence, all from `reports/data_inventory.md`, its tables in `reports/tables/`, and `reports/data_inventory_notes.md` (cache v2, 10 Oct 2026):

**Timestamps**
- **LAMDA.** The slotting time is AndroZoo `added` (the date the APK entered AndroZoo), at second resolution, for all 1,008,381 apps. `year_month` agrees with it for every row.
- **BODMAS malware.** First-seen instants from 2019-08-29 to 2020-09-30.
- **BODMAS benign.** Benign rows are dated by day in collection batches:
  - 85.8% are date-only;
  - in the study window the median is 150 rows per day and the regular maximum is 599;
  - outlier round dates: 2020-01-01 (5,877 rows), 2015-01-01, 2018-02-01 and 2018-03-19;
  - 13,514 rows fall before the first malware week.

**Occupancy (gate M as defined in option 3)**
- **LAMDA months.**
  - The span 2013-06 to 2025-01 has 140 slots: 20 empty, 97 passing M = 50.
  - The longest passing run is **62 months, 2018-11 to 2023-12**; its weakest month has 114 malware and 933 benign.
  - Month sizes range from a few hundred to 55,000 apps.
- **LAMDA quarters.** 48 slots: 5 empty, 6 partly empty, 34 passing M = 50. The longest run is **29 quarters, 2017Q4 to 2024Q4**.
- **BODMAS, study window 2019-W35 to 2020-W40 (58 ISO weeks, no empty week):**

  | Length | Slots | Fail M = 50 | Also fail without the 2020-01-01 placeholder rows |
  |---|---|---|---|
  | 1 week | 58 | 9 | +1 (2019-12-30) |
  | 2 weeks | 29 | 2 (2020-01-13 and 2020-01-27: 27 and 14 benign) | +1 (2019-12-30: 6,200 benign, 5,877 of them placeholders) |
  | 4 weeks | 15 | 2 (2020-01-13; 2020-09-21, which is partly empty because the data ends) | none |

**Gaps**
- LAMDA has 17 consecutive empty months from 2014-09 to 2016-01 (the "2015 gap"), plus 2013-07, 2013-08 and 2017-06.
- BODMAS has no empty week in the window.

**Duplicates**
- **LAMDA.** 23.7% of rows (238,576) repeat a feature vector seen in an earlier month. 2,177 vectors carry both labels (54,835 rows).
- **BODMAS.** 4 rows repeat an earlier week's vector.

**Label-revealing metadata.** `family`, `vt_count` and `category` each separate the classes perfectly, and so does BODMAS time of day (benign dates are midnight; malware times are not).

**Rules in force**
- C1–C3 (PROTOCOL §2, §4).
- Hard rule 4: selectors, policies and monitors never see labels.
- `.claude/rules/data.md`: rolling windows never span a data gap; slots that fail the gate are skipped and logged.
- Delay d ∈ {0, 1, 2, 3} slots and retraining every 3 slots (PROTOCOL §2).
- Mismatch D2: delay is promised "per month" but measured in slots.

## Options considered

### 1. LAMDA slot length
- **A. Month.**
  - Pros:
    - The delay unit equals the guide's "per month" promise, which resolves D2 for Android.
    - The longest passing run of 62 slots gives many rolling windows for A-AUT.
    - Drops are dated more precisely.
  - Cons: many small or unbalanced months outside 2018-11 to 2023-12, and per-slot F1 is noisier.
- **B. Quarter.**
  - Pros: smoother counts.
  - Cons:
    - Only 29 slots in the longest run.
    - d = 3 means 9 months of delay, beyond the 1–3 months the guide motivates.
    - Retraining every 3 slots means once every 9 months.
- **C. Year** (the guide's fallback). Not needed: the 1.5 GB cap held (peak 0.93 GB at most), the timestamps are usable, and 12 yearly slots with a 2015 hole would leave almost no rolling windows.

### 2. BODMAS slot length (within the study window)
- **A. 1 week.** 58 slots, but 9 or 10 fail and the longest run is 25.
- **B. 2 weeks.** 29 slots. 2 fail, or 3 without the placeholder rows. d = 3 means 6 weeks of delay.
- **C. 4 weeks.** 15 slots, 2 failing, which leaves runs too short for an initial K = 3–4 window plus a meaningful evaluation tail.

### 3. Minimum-size gate
A slot passes when C3 subsampling to 10% malware keeps at least M malware (n_malware ≥ M and n_benign ≥ 9M), and the slot has no empty base unit.
- **M = 30.** The most slots pass, but per-slot F1 rests on 30 positives.
- **M = 50.** The LAMDA monthly run barely changes from M = 30 (62 vs 66), and each slot holds at least 500 samples after C3.
- **M = 100.** It costs BODMAS 1-week slots heavily and changes nothing for 2-week slots or LAMDA's longest monthly run.

### 4. Gaps, failing and partly empty slots
- **A.** Empty, gate-failing and partly empty slots are all **gaps**. A rolling window (training plus evaluation slots) never contains or bridges one.
- **B.** Let windows bridge failing slots. This contradicts the data rule and hides C2 problems.

### 5. BODMAS placeholder-dated rows
- **A. Keep them.** Then `2w:2019-12-30` passes, but most of its benign rows carry no meaningful date (C1 and C2 risk).
- **B. Exclude benign rows** whose date-only timestamp is shared by at least 1,000 rows. That rule flags 2020-01-01, 2015-01-01, 2018-02-01 and 2018-03-19, and only 2020-01-01 lies in the window. The rows stay in the cache, flagged; Phase 3's slicer drops them, and `2w:2019-12-30` becomes a failing slot.

### 6. Duplicate feature vectors
- **A. Keep all rows**, report the per-slot share seen in earlier slots, and run one pre-declared E0 sensitivity that removes from evaluation the rows whose vector appeared in the actual training pool (past only).
- **B. Drop cross-slot duplicates everywhere.** This changes the population the detector faces.
- **C. Ignore them.** The guardrails forbid this.

## Decision (accepted by the researcher, 10 Oct 2026)
The researcher chose: LAMDA month; BODMAS 2 weeks from 2019-08-26; M = 50 with strict gaps; exclude placeholder-dated benign rows; and the remaining items as written (answers recorded in the Phase 2 session, 10 Oct 2026).

1. **LAMDA: monthly slots (option 1A).** Calendar months in UTC, keyed by AndroZoo `added`. Quarters stay available for a sensitivity check, not for the headline.
2. **BODMAS: 2-week slots (option 2B)** in the study window from **2019-08-26** (Monday of ISO week 2019-W35, the first week with malware) to 2020-10-04.
   - The slots are anchored explicitly at 2019-08-26 (`build_slots(..., anchor=...)`), so slot ids do not move when early rows are dropped.
   - The 13,514 benign rows dated before the window are outside the study. They stay in the cache and are reported in the data card.
3. **Gate M = 50** for both datasets, recomputed after C3 subsampling at whatever ratio Phase 3 fixes (logged when it changes which slots pass).
4. **Gaps (option 4A).** Empty, gate-failing and partly empty slots are gaps. Windows never span them, and every skipped slot is logged with its counts. This produces:

   | Dataset | Passing segments (M = 50) |
   |---|---|
   | LAMDA months | 2018-11 to 2023-12 (62); 2013-09 to 2014-08 (12); 2017-10 to 2018-04 (7); 2017-01 to 2017-04 (4); shorter ones in the inventory |
   | BODMAS 2-week, with decision 5 | 2019-08-26 to 2019-12-29 (9); 2020-02-10 to 2020-10-04 (17) |

   Phase 3 (ADR-0005) chooses nT, nE and the stride, and therefore which segments are long enough. The headline LAMDA window lies in 2018-11 to 2023-12. 2015 is never interpolated or bridged.
5. **Placeholder dates (option 5B).** Exclude benign rows whose date-only timestamp is shared by at least 1,000 rows (`ts_date_only` and `ts_tie_count` in the cache). The 1,000 threshold sits above every regular batch day in the window (maximum 599).
6. **Duplicates (option 6A).**
   - Keep the rows and report the seen-before share per evaluation slot.
   - The E0 sensitivity removes evaluation rows whose vector appears in that window's training pool (past only, never "appears in several slots").
   - Label-conflicting vectors stay as published and are counted.
7. **Label-free view.** Selectors, policies and monitors receive only `SlotData.public()` (features and row ids). `meta`, which includes `ts`, `family`, `vt_count` and `category`, and `y` reach only the label queue and the metrics. Phase 5 adds the spy test.
8. **Hold-outs.** Any time-ordered hold-out (calibration, early stopping) is cut at slot boundaries, never by row position inside a slot. Within a BODMAS slot, row order is linked to class through midnight benign dates.
9. **Delay units (D2).** LAMDA delay is reported in months (1 slot = 1 month). BODMAS delay is reported in slots and in days (1 slot = 14 days), so the "per month" statement applies to LAMDA only, unless Phase 6 converts with stated assumptions.

## Consequences
- **Easier.**
  - Phase 3 gets unambiguous slot IDs (`month:YYYY-MM`, `2w:YYYY-MM-DD`) from loaders that already exist.
  - Every gate decision traces back to a CSV row, and the exclusions are per-row flags rather than edits to the data.
- **Harder or riskier.**
  - The LAMDA headline excludes 2013–2018 and 2024–2025. Early drift is studied only in shorter segments or in the quarterly sensitivity check.
  - BODMAS offers two short segments (9 and 17 slots), so its A-AUT will rest on few windows.
  - The BODMAS benign timestamp semantics (Q2) remain a threat to validity for C1 on Windows.
- **Revisit when:** the researcher rejects a choice; Phase 3 fixes nT/nE or the C3 sensitivity ratio (re-run the gate tables); the LAMDA or BODMAS authors answer Q1 or Q2; or a new dataset version arrives (a new manifest entry, then rerun the inventory and update this ADR by addendum).

## Evidence and references
- `reports/data_inventory.md`.
- Tables: `reports/tables/data_lamda_slots_{month,quarter}.csv`, `data_bodmas_slots_{1w,2w,4w}.csv`, `data_bodmas_benign_days.csv`, `data_*_duplicates_per_slot.csv`.
- `reports/data_inventory_notes.md` (Q1–Q7, leakage review).
- `data/manifest.json`: LAMDA HF commit `ad9614bd…`, BODMAS Drive file IDs, all hashes, archived cache v1.
- Clean rebuild of cache v2: 1,088 files byte-identical; `driftwatch data verify` OK.
- PROTOCOL §2, §5, D2, D9, D10, D13, D14; `.claude/rules/data.md`; CLAUDE.md hard rule 4.
- LAMDA paper arXiv 2505.18551 (accessed 10 Oct 2026); BODMAS page https://whyisyoung.github.io/BODMAS/ (accessed 10 Oct 2026).
