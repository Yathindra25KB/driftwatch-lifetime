# Data inventory: interpretation and open questions (Phase 2)

Companion to the generated [data_inventory.md](data_inventory.md). Every number below comes from that file, its CSV tables, or `data/manifest.json` at commit `ade5116`. The real builds ran on 10 Oct 2026; tags: [measured] means this machine, [verified] means checked against a source, [verify] means still to check.

## Answers to the guide's week-1 [verify] questions

### 1. Timestamp type and granularity
**LAMDA.**
- **Timestamp.** The parquet files carry only `year_month` (YYYY-MM). The repository's root `metadata.csv` (not described in the README) carries `added` (`YYYY-MM-DD HH:MM:SS`) for all 1,008,381 apps. `year_month` equals the month of `added` for every row (0 mismatches) [measured].
- **What `added` means.** It is AndroZoo's "added" field: the date the APK entered AndroZoo. AndroZoo notes that an APK "could very well have existed for years before it was added" [verify: AndroZoo lists page as quoted by a search result, 10 Oct 2026; the direct fetch returned 404].
- **What the cache uses.** The cache uses `added` as the slotting timestamp `ts`, at second resolution.
- **C1 implication.** Time order is AndroZoo collection order. It is not first-seen in the wild, and it is not compile or dex time (PROTOCOL D13). "Never train on the future" therefore means "never train on apps collected later". An app collected late may be older than apps collected earlier. This is a threat to validity for the report, not a leakage bug.

**BODMAS.** `bodmas_metadata.csv` has one `timestamp` per sample. The BODMAS page describes it as when the sample "first appeared". The two classes behave differently [measured]:
- **Malware** (57,293 rows) spans 2019-08-29 to 2020-09-30, with second-level times. Fewer than 0.01% of malware timestamps fall at midnight.
- **Benign** (77,142 rows):
  - spans 2007-01-01 to 2020-09-30;
  - 85.8% of benign timestamps fall exactly at midnight, so most are date-only;
  - 5,877 benign rows share the single value `2020-01-01 00:00:00`;
  - 13,514 benign rows (none malware) predate the first malware week (2019-W35).
- **Offset.** 3,712 timestamps (all benign) carry no UTC offset; the cache reads them as UTC.
- **C1 and C2 implication.** The benign timestamps look like a different kind of date (often a day or a placeholder) from the malware first-seen times. Weeks 2020-W02 to 2020-W07 hold 6 to 29 benign against about 900 to 1,100 malware each. Week 2020-W01 holds 6,188 benign, most of them stamped 2020-01-01. A slot can only satisfy C2 (both classes from the same window) where both classes are present. ADR-0004 therefore proposes a study window, and the data card records the benign-date caveat.

### 2. Feature count, dtype, values
| | LAMDA | BODMAS |
|---|---|---|
| Features | 4,561 (`feat_0`…`feat_4560`, matches PROTOCOL D9) | 2,381 |
| Stored as | int8, CSR | float32, dense, unnormalised |
| Value range | 0 to 17: counts, not only 0/1 | as published; 0 NaN, 0 inf |
| Density (non-zero share) | 1.63% (75.1 M non-zeros) | 27.6% |

### 3. Size on disk and build cost (LAMDA)
| | LAMDA | BODMAS |
|---|---|---|
| Raw files | 340.5 MB (Baseline parquet + metadata.csv + README) | 265.5 MB |
| Cache | 119.6 MB | 1,230.5 MB (dense float32, memory-mappable) |
| Peak memory (cap 1.5 GB) | **0.85 GB** | 0.55 GB |
| Wall-clock | 93.1 s | 23.1 s |

The LAMDA build streams one 8,192-row batch at a time. Each source file is a single parquet row group, so a whole file is never decompressed at once (probe of 2013_train alone: 0.53 GB peak). The 1.5 GB cap held with 0.65 GB of headroom, so the Phase 2 stop rule does not fire.

### 4. Slot occupancy and the minimum-size gate
See the gate tables in the inventory. The main points:
- **LAMDA months (span 2013-06 to 2025-01, 140 slots).**
  - 20 months are empty, and 101 of the 120 non-empty months pass M = 30.
  - The longest unbroken passing run is 66 months (2018-11 to 2024-04) at M = 30, and 62 months at M = 50 or M = 100.
  - Failures cluster in 2016-05 to 2016-12 and 2017-07 to 2017-09 (almost no benign) and in 2024 to 2025 (almost no malware).
- **LAMDA quarters (48 slots).**
  - 5 quarters are empty (2014Q4 and all of 2015), and 39 of 43 non-empty quarters pass M = 30 or M = 50.
  - The longest run is 29 quarters (2017Q4 to 2024Q4) at M = 30 or M = 50.
- **LAMDA 2025** has only January (44,663 apps, 23 malware), so 2025 is one month, not a year.
- **BODMAS, dense period 2019-W35 to 2020-W40 (58 ISO weeks, no empty weeks).** These counts are for the dense period; the longest runs are computed over the whole span.

  | Length | Slots | Fail M = 50 | Longest run at M = 50 |
  |---|---|---|---|
  | 1 week | 58 | 9, mainly the Jan–Feb 2020 benign drought | 25 weeks |
  | 2 weeks | 29 | 2 | 17 |
  | 4 weeks | 15 | 1 | 9 |

### 5. The 2015 gap and other gaps (LAMDA)
LAMDA has no 2015 folder and no `added` date in 2015. The empty run is longer than 2015: 2014-09 to 2016-01, 17 consecutive empty months. 2013-07, 2013-08 and 2017-06 are also empty. The paper gives two reasons for the missing year ("lacks valid entries"; "unavailability of hashes in the AndroZoo repository") [verified, arXiv 2505.18551, 10 Oct 2026]. The cache stores no rows for empty months. The slot schemes list them as gap slots, and `.claude/rules/data.md` forbids rolling windows that span a gap. The handling is proposed in ADR-0004.

### 6. Duplicate feature vectors (leakage risk)
- **LAMDA.** 1,008,381 rows hold only 679,423 distinct feature vectors.
  - 238,576 rows (23.7%) carry a vector that already appeared in an earlier month; 196,556 rows (19.5%) do so for quarters.
  - The per-month share peaks at about 0.65 in early 2018 and settles at about 0.1 to 0.2 after 2020.
  - 2,177 vectors carry both labels, covering 54,835 rows: identical features, different label.
  - No sha256 appears twice.
  - Duplicated vectors inflate a time-aware score whenever the same vector sits in training and test. ADR-0004 proposes how to handle them.
- **BODMAS.** 7 vector pairs (14 rows), 4 of them across weeks: negligible.

### 7. Clean rebuild and verification
- **Rebuild.** Both datasets were rebuilt from the raw files into a fresh root, `data/rebuild_check/` (10 Oct 2026). The rebuild ran at 0.87 GB peak and 103.4 s for LAMDA, and 0.55 GB and 21.4 s for BODMAS [measured].
- **Byte-identical.** All 1,088 cache files (LAMDA 240, BODMAS 848) are byte-identical to those recorded in `data/manifest.json`, and the raw file hashes match.
- **Verify.** `driftwatch data verify` passes on both roots: 0 problems.

## Other findings
- **LAMDA labels.** All checks are consistent: benign rows have vt_count 0, malware rows have vt_count of at least 4, and the parquet labels, vt_count and family agree with `metadata.csv` for every row. 1,381 named AVClass2 families exist, 435 of them with at least 10 samples. 150,604 malware rows (40.7% of malware) carry an AVClass2 `singleton:<sha>` label instead of a family.
- **BODMAS identifiers.** 7 rows carry a `VirusShare_<md5>` identifier instead of a sha256, and all 7 are labelled benign (y = 0, empty family) with timestamp 2020-01-01. VirusShare is a malware repository, so their labels deserve a check (open question).
- **BODMAS families.** 582 named families, 196 of them with at least 10 samples (the page says 581). Every malware row has a family and a category.

## Open questions (cannot be answered from the data alone)
| # | Question | Why it matters | Who or how |
|---|---|---|---|
| Q1 | Confirm that LAMDA `year_month` is derived from AndroZoo `added` (the date of entering AndroZoo) | C1 meaning of "time" for Android | Read the AndroZoo lists page directly; LAMDA authors |
| Q2 | What do BODMAS benign timestamps mean (midnight dates; 5,877 at 2020-01-01; 13,514 before Aug 2019)? | C1 and C2 for Windows; whether benign rows from before the malware period may train at all | BODMAS paper §3 or the authors |
| Q3 | Are the 7 benign `VirusShare_*` rows really benign? | Label noise (tiny) | Out of scope to resolve; flag in the data card |
| Q4 | Are the 3,712 offset-less BODMAS timestamps UTC? | Off by at most one day; can move a sample across a week boundary | Assumed UTC; listed |
| Q5 | What licence applies to the BODMAS dataset files themselves (the repository code is BSD-2-Clause)? | Licence audit (Phase 12) | Ask the authors, or keep the guide's BSD-2 with [verify] |
| Q6 | Why does LAMDA 2025 hold only January 2025? | Last-year coverage | LAMDA authors or card; treat as a single month |
| Q7 | LAMDA features reach 17: does the vectoriser count tokens? | Model input semantics (binary or count) | `feature_mapping.csv` and the paper's §3; Phase 4 |
