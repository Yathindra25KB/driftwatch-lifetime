# DriftWatch claims ledger

Every number or claim of consequence that appears in the README, the report (`report/`) or the paper (`paper/`) must have a row here first.

## Rules

1. **No row, no claim.** A number without a row is written as `[verify]` or left out.
2. **Traceable.** Each row names the result file that produced the value and the commit that produced that file. For external facts it names the source and the access date.
3. **Tagged.** `[verified]` means checked against a source or a stored result. `[verify]` means still to check. `[estimate]` means a planning number. `[measured]` means a timing or size from a run on this machine.
4. **Never evidence:** toy, sandbox or synthetic-fixture numbers, including the guide's sandbox table in §7. They may appear only as labelled code-behaviour checks.
5. **Never "first".** No contribution is claimed as "first". State what was measured.
6. **Corrections append.** A changed value gets a new row that names the claim it supersedes; old rows are never edited away.
7. **Regenerable.** Values from experiments must regenerate from stored per-slot predictions with `scripts/make_tables.py` (Phase 6 onward).

## Ledger

| Claim ID | Statement | Value | Source file | Commit | Tag | Access date |
|---|---|---|---|---|---|---|
| D-01 | LAMDA size and class counts (Baseline subset, HF commit ad9614bd) | 1,008,381 apps; 369,906 malware; 638,475 benign | reports/data_inventory.md | ade5116 | [verified] (matches arXiv 2505.18551 Table 2) | 2026-10-10 |
| D-02 | LAMDA feature count, storage and density | 4,561 int8 features (values 0-17); 1.63% non-zero | reports/data_inventory.md | ade5116 | [measured] | 2026-10-10 |
| D-03 | LAMDA slotting timestamp | AndroZoo `added` (seconds) for 100% of rows; `year_month` equals its month for every row | reports/data_inventory.md; reports/data_inventory_notes.md §1 | 18b189d | [measured]; meaning of `added` [verify] | 2026-10-10 |
| D-04 | LAMDA empty months in 2013-06..2025-01 | 20, including 2014-09..2016-01 (17 consecutive); 2025 holds January only | reports/tables/data_lamda_slots_month.csv | ade5116 | [measured] | 2026-10-10 |
| D-05 | LAMDA duplicate feature vectors | 679,423 distinct vectors; 238,576 rows (23.7%) repeat a vector from an earlier month; 2,177 vectors with both labels (54,835 rows) | reports/data_inventory.md | ade5116 | [measured] | 2026-10-10 |
| D-06 | LAMDA cache build on the 8 GB laptop | peak 0.85 GB (cap 1.5 GB), 93.1 s, cache 119.6 MB, raw 340.5 MB | reports/data_inventory.md (from data/manifest.json build record) | ade5116 | [measured] | 2026-10-10 |
| D-07 | BODMAS size and features | 134,435 samples (57,293 malware, 77,142 benign); 2,381 float32 features; 27.6% non-zero | reports/data_inventory.md | ade5116 | [verified] against the BODMAS page; density [measured] | 2026-10-10 |
| D-08 | BODMAS timestamps by class | malware 2019-08-29..2020-09-30 (second resolution); benign 2007-01-01..2020-09-30, 85.8% at midnight, 5,877 at 2020-01-01 00:00:00, 13,514 before 2019-W35 | reports/data_inventory.md; reports/data_inventory_notes.md §1 | 18b189d | [measured] | 2026-10-10 |
| D-09 | BODMAS cache build | peak 0.55 GB (cap 1.5 GB), 23.1 s, cache 1,230.5 MB, raw 265.5 MB | reports/data_inventory.md | ade5116 | [measured] | 2026-10-10 |
| D-10 | Clean rebuild reproducibility | all 1,088 cache files byte-identical to data/manifest.json; `driftwatch data verify` 0 problems | reports/data_inventory_notes.md §7 | 18b189d | [measured] | 2026-10-10 |
| D-11 | LAMDA cache v2 build (supersedes D-06) | peak 0.87 GB (cap 1.5 GB; clean rebuild 0.93 GB), 93.1 s, cache 119.7 MB | reports/data_inventory.md; reports/data_inventory_notes.md §3 | 83ffb87 | [measured] | 2026-10-10 |
| D-12 | BODMAS cache v2 build (supersedes D-09) | peak 0.56 GB (cap 1.5 GB), 23.4 s, cache 1,231.2 MB | reports/data_inventory.md | 83ffb87 | [measured] | 2026-10-10 |
| D-13 | Clean rebuild reproducibility, cache v2 (supersedes D-10) | all 1,088 cache files byte-identical to data/manifest.json; `driftwatch data verify` 0 problems on both roots | reports/data_inventory_notes.md §7 | 83ffb87 | [measured] | 2026-10-10 |
| D-14 | BODMAS benign timestamps are daily batches | 66,167 benign rows date-only; study-window median 150 rows/day (regular max 599); placeholder candidates (date-only ts shared by >= 1,000 rows) 9,545 rows, of which 5,877 at 2020-01-01 | reports/tables/data_bodmas_benign_days.csv; reports/data_inventory_notes.md §1 | 83ffb87 | [measured] | 2026-10-10 |
