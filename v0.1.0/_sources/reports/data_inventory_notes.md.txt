# Data inventory: interpretation and open questions (Phase 2)

Companion to the generated [data_inventory.md](data_inventory.md). Every number below comes from that file, its CSV tables, or `data/manifest.json` (cache v2, 10 Oct 2026). Tags: [measured] means this machine, [verified] means checked against a source, [verify] means still to check.

## Answers to the guide's week-1 [verify] questions

### 1. Timestamp type and granularity
**LAMDA.**
- **Timestamp.** The parquet files carry only `year_month` (YYYY-MM). The repository's root `metadata.csv` (not described in the README) carries `added` (`YYYY-MM-DD HH:MM:SS`) for all 1,008,381 apps. `year_month` equals the month of `added` for every row (0 mismatches) [measured].
- **What `added` means.** It is AndroZoo's "added" field: the date the APK entered AndroZoo. AndroZoo notes that an APK "could very well have existed for years before it was added" [verify: AndroZoo lists page as quoted by a search result, 10 Oct 2026; the direct fetch returned 404].
- **What the cache uses.** The cache uses `added` as the slotting timestamp `ts`, at second resolution. A per-row `ts_source` column records this: "added" for every real row.
- **C1 implication.** Time order is AndroZoo collection order. It is not first-seen in the wild, and it is not compile or dex time (PROTOCOL D13). "Never train on the future" therefore means "never train on apps collected later". This is a threat to validity for the report, not a leakage bug.

**BODMAS.** `bodmas_metadata.csv` has one `timestamp` per sample. The BODMAS page describes it as when the sample "first appeared". The two classes are timed differently [measured]:
- **Malware** (57,293 rows) spans 2019-08-29 to 2020-09-30, with second-level times. Only 2 malware timestamps are date-only.
- **Benign** (77,142 rows) spans 2007-01-01 to 2020-09-30. 66,167 benign rows (85.8%) are date-only (`00:00:00`) and arrive in **daily batches**:
  - In the study window the median is 150 rows per day and the regular maximum is 599; many days hold exactly 300 ([csv](tables/data_bodmas_benign_days.csv)).
  - Four days stand out: 2020-01-01 (5,877 rows), 2015-01-01 (1,563), 2018-02-01 (1,100) and 2018-03-19 (1,005). They are round dates and look like placeholders. The inventory flags date-only timestamps shared by at least 1,000 rows as placeholder candidates, 9,545 rows in all. Only 2020-01-01 lies inside the study window.
  - 13,514 benign rows predate the first malware week (2019-W35).
- **Offset.** 3,712 timestamps (all benign) carry no UTC offset; they are read as UTC.
- **Per-row flags.** The cache stores per-row flags `ts_date_only`, `ts_naive` and `ts_tie_count`, so later phases can exclude rows by rule (leakage review, finding 2).
- **C1 and C2 implication.** Benign "time" is mostly the day of a collection batch, while malware time is a first-seen instant. Where a C2 slot is wide enough to contain whole days, both classes come from the same window. The 2020-01-01 batch, however, carries no meaningful date. Weeks 2020-W02 to 2020-W07 hold 6 to 29 benign each against about 1,000 malware.
- **Ordering inside a slot.** Benign rows dated `00:00:00` sort first within each day, so row order inside a slot is linked to class. Any time-ordered hold-out must be cut at slot boundaries, never by row position (leakage review, finding 9; for the Phase 3 and Phase 8 ADRs).

### 2. Feature count, dtype, values
| | LAMDA | BODMAS |
|---|---|---|
| Features | 4,561 (`feat_0`…`feat_4560`, matches PROTOCOL D9) | 2,381 |
| Stored as | int8, CSR | float32, dense, unnormalised |
| Value range | 0 to 17: counts, not only 0/1 | as published; 0 NaN, 0 inf |
| Density (non-zero share) | 1.63% (75.1 M non-zeros) | 27.6% |

### 3. Size on disk and build cost
These are the cache v2 builds of 10 Oct 2026, with the 1.5 GB cap enforced by the watchdog.

| | LAMDA | BODMAS |
|---|---|---|
| Raw files | 340.5 MB (Baseline parquet + metadata.csv + README) | 265.5 MB |
| Cache | 119.7 MB | 1,231.2 MB (dense float32, memory-mappable) |
| Peak memory | **0.87 GB** (rebuild 0.93 GB) | 0.56 GB |
| Wall-clock | 93.1 s (rebuild 91.2 s) | 23.4 s (rebuild 20.8 s) |

- **How LAMDA stays small.** The build streams one 8,192-row batch at a time. Each source file is a single parquet row group, and a probe of 2013_train alone peaked at 0.53 GB.
- **Stop rule.** The cap held with at least 0.57 GB of headroom on every build, so the Phase 2 stop rule does not fire.
- **v1 cache.** The first build (cache v1: 0.85 GB, 93.1 s) is archived in the manifest under `previous_caches`.

### 4. Slot occupancy and the minimum-size gate
See the gate tables in the inventory. A slot passes gate M when it has at least M malware and 9M benign and is not **partly empty**.

- **LAMDA months (span 2013-06 to 2025-01, 140 slots).**
  - 20 months are empty, and 97 of 120 non-empty months pass M = 50.
  - The longest passing run is **62 months, 2018-11 to 2023-12**, at M = 50 or M = 100.
  - Failures cluster in 2016–2017 (almost no benign) and in 2024–2025 (almost no malware). 2025 holds January only.
- **LAMDA quarters (48 slots).**
  - 5 quarters are empty, and 6 are partly empty: 2013Q2, 2013Q3, 2014Q3, 2016Q1, 2017Q2 and 2025Q1.
  - 34 of 43 non-empty quarters pass M = 50, and the longest run is 29 quarters (2017Q4 to 2024Q4).
- **BODMAS, study window 2019-W35 to 2020-W40 (58 ISO weeks, none empty).** These counts are for the study window:

  | Length | Slots | Fail M = 50 | Also fail without the 2020-01-01 rows |
  |---|---|---|---|
  | 1 week | 58 | 9 | 2019-12-30 |
  | 2 weeks | 29 | 2 (2020-01-13, 2020-01-27) | 2019-12-30 (it passed only through 5,877 placeholder-dated benign) |
  | 4 weeks | 15 | 2 (2020-01-13; 2020-09-21, which is partly empty because the data ends) | none |

### 5. The 2015 gap and other gaps (LAMDA)
LAMDA has no 2015 folder and no `added` date in 2015. The empty run is longer than 2015: 2014-09 to 2016-01, 17 consecutive empty months. 2013-07, 2013-08 and 2017-06 are also empty. The paper gives two reasons for the missing year ("lacks valid entries"; "unavailability of hashes in the AndroZoo repository") [verified, arXiv 2505.18551, 10 Oct 2026]. The cache stores no rows for empty months. The slot schemes list them as gap slots, and partly empty slots fail the gate. `.claude/rules/data.md` forbids rolling windows that span either. The handling is in ADR-0004.

### 6. Duplicate feature vectors (leakage risk)
- **LAMDA.** 1,008,381 rows hold only 679,423 distinct feature vectors.
  - 238,576 rows (23.7%) carry a vector that already appeared in an earlier month; 196,556 rows (19.5%) do so for quarters.
  - The per-month share peaks at about 0.65 in early 2018 and settles at about 0.1 to 0.2 after 2020.
  - 2,177 vectors carry both labels, covering 54,835 rows.
  - No sha256 appears twice.
  - The feature hash uses int32 indices and int8 values, so it does not depend on batch size (tested).
- **BODMAS.** 7 vector pairs (14 rows), 4 of them across weeks: negligible.
- **For Phase 4 (finding 13).** Any duplicate-based exclusion must use only the past ("seen earlier", ideally relative to the actual training pool), never "appears in several slots", which also looks at the future.

### 7. Clean rebuild and verification (cache v2)
- **Rebuild.** Both datasets were rebuilt from the raw files into a fresh root, `data/rebuild_check/` (10 Oct 2026).
- **Byte-identical.** All 1,088 cache files (LAMDA 240, BODMAS 848) are byte-identical to those recorded in `data/manifest.json`, and the raw file hashes match.
- **Verify.** `driftwatch data verify` passes on both roots: 0 problems.
- **What verify now proves.** It recomputes every row's feature hash from X (X/meta alignment), checks LAMDA `year_month` against its unit, and checks that every file lies under the current cache version. Negative tests cover each content check.

## Other findings
- **LAMDA labels.** All checks are consistent: benign rows have vt_count 0, malware rows have vt_count of at least 4, and the parquet labels, vt_count and family agree with `metadata.csv`. 1,381 named AVClass2 families exist, 435 of them with at least 10 samples. 150,604 malware rows (40.7% of malware) carry an AVClass2 `singleton:<sha>` label.
- **Label-revealing metadata (finding 1).**
  - `family`, `vt_count` and `category` are labels in disguise, and so is BODMAS time of day. Each one separates the classes perfectly on this data.
  - The loader therefore offers `SlotData.public()`, which exposes only X and row ids, for selectors, policies and monitors. Phase 5 adds the spy test.
- **BODMAS identifiers.** 7 rows carry a `VirusShare_<md5>` identifier instead of a sha256. All 7 are labelled benign with timestamp 2020-01-01. VirusShare is a malware repository, so their labels deserve a check.
- **BODMAS families.** 582 named families, 196 of them with at least 10 samples (the page says 581). Every malware row has a family and a category.

## Leakage review (10 Oct 2026)
- **Review.** The leakage-reviewer subagent read `src/driftwatch/data/`, the tests and these reports.
- **No direct leak.** It found no direct temporal leak in the cache contents: one unit per row, no label in any sort key, and nothing fitted at ingestion.
- **Fixed in `bba2692` (cache v2), with tests:**
  - 1: label-revealing metadata (the public view);
  - 2: placeholder dates (per-row flags and the gate sensitivity check);
  - 3: resume mixing builds (builder fingerprints, version archive);
  - 4: verify blind spots (alignment and routing checks, negative tests);
  - 5: ISO year boundary;
  - 6: partly empty slots;
  - 7: explicit week anchor;
  - 8: naive timestamps flagged;
  - 10: missing metadata.csv is an error;
  - 11: sha256 index lower-cased before sorting;
  - 12: batch-size-independent hash.
- **Carried to later ADRs:**
  - 9: cut time-ordered hold-outs at slot boundaries (Phase 3 and Phase 8).
  - 13: E0's duplicate sensitivity must be past-only (Phase 4).

## Open questions (cannot be answered from the data alone)
| # | Question | Why it matters | Who or how |
|---|---|---|---|
| Q1 | Confirm that LAMDA `year_month` is derived from AndroZoo `added` (the date of entering AndroZoo) | C1 meaning of "time" for Android | Read the AndroZoo lists page directly; LAMDA authors |
| Q2 | What do BODMAS benign timestamps mean (daily batch dates; round-date outliers 2020-01-01, 2015-01-01, 2018-02-01, 2018-03-19; 13,514 before Aug 2019)? | C1 and C2 for Windows; whether to exclude placeholder-dated rows (ADR-0004) | BODMAS paper §3 or the authors |
| Q3 | Are the 7 benign `VirusShare_*` rows really benign? | Label noise (tiny) | Flagged in the data card |
| Q4 | Are the 3,712 offset-less BODMAS timestamps UTC? | Date-only values could cross a week boundary under a positive offset | Assumed UTC; flagged per row (`ts_naive`) |
| Q5 | What licence applies to the BODMAS dataset files themselves (the repository code is BSD-2-Clause)? | Licence audit (Phase 12) | Ask the authors, or keep the guide's BSD-2 with [verify] |
| Q6 | Why does LAMDA 2025 hold only January 2025? | Last-year coverage | LAMDA authors or card; treat as a single month |
| Q7 | LAMDA features reach 17: does the vectoriser count tokens? | Model input semantics (binary or count) | `feature_mapping.csv` and the paper's §3; Phase 4 |
