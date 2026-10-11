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
| W-01 | LAMDA usable runs at 10%, M = 50 (cap and flag) | 97 usable months in 10 runs; longest 62 (2018-11..2023-12), of which 31 months hold under 10% malware (36 of 97 overall) | reports/window_options.md; reports/tables/window_segments_lamda.csv | 4ce5cba | [measured] (slot counts only) | 2026-10-11 |
| W-02 | BODMAS usable runs at 10%, M = 50, placeholder rows excluded | 26 usable 2-week slots in 2 runs (9 and 17); none below 10% | reports/window_options.md; reports/tables/window_segments_bodmas.csv | 4ce5cba | [measured] (slot counts only) | 2026-10-11 |
| W-03 | Sensitivity-ratio reach (M = 50) | 5%: 95 usable LAMDA months, 8 below target, longest run 47; 20%: 97 usable, 50 below target; BODMAS 5%: 0 below, 20%: 1 below | reports/window_options.md | 4ce5cba | [measured] (slot counts only) | 2026-10-11 |
| W-04 | Full-dataset slicing pass, nT 4, nE 12, stride 1, 10%, M = 50 | LAMDA: 47 windows, 564 evaluation slots, 28.6 s, peak 0.40 GB, 0 densified; BODMAS: 2 windows, 24 evaluation slots, 2.9 s, peak 0.69 GB; no C1-C3 violation | reports/slicing_run.md | 4ce5cba | [measured] | 2026-10-11 |
| W-05 | Slicer mutation checks | 12 of 12 deliberate breakages caught by the constraint, slicer, property and cache suites; baseline green | reports/mutation_matrix.md | 448e20d | [measured] (code-behaviour check, not evidence about detectors) | 2026-10-10 |
| W-06 | Slicer mutation checks after the leakage review (supersedes W-05) | 14 of 14 deliberate breakages caught; baseline 112 tests green | reports/mutation_matrix.md | ee4bcd0 | [measured] (code-behaviour check, not evidence about detectors) | 2026-10-11 |
| W-07 | Slicer mutation checks after the second review pass (supersedes W-06) | 15 of 15 deliberate breakages caught; baseline 120 tests green | reports/mutation_matrix.md | 9b27b58 | [measured] (code-behaviour check, not evidence about detectors) | 2026-10-11 |
| M-01 | Chow et al. A-AUT window formula | A-AUT = (mean, std) of AUT over windows (Eq. 1). nE >= nT: windows advance by nT, k = floor((|D|-nE)/nT) (Eq. 2-4). nE < nT: advance by nE, k = floor((|D|-nT)/nE) (Eq. 6-8). Both are stride min(nT, nE) | docs/DECISIONS/ADR-0006-metrics-threshold-scaling.md (source: arXiv 2506.23814v2, HTML, section V and appendix A-E) | b077f05 | [verified] (std's ddof is not stated in the paper) | 2026-10-11 |
| M-02 | TESSERACT AUT normalisation | arXiv v4 comments: published Eq. (4) had an extra 1/N factor (typo); results rely on numpy's area under the curve. The guide's 1/(N-1) form equals np.trapezoid(f, dx=1/(N-1)) (pinned by tests/test_aut.py) | docs/DECISIONS/ADR-0006-metrics-threshold-scaling.md (source: arXiv 1807.07838v4 abstract page) | b077f05 | [verified] (comment text); equivalence [measured] by test | 2026-10-11 |
| B-01 | Largest E0 training windows (plan counts) | BODMAS 17,873 rows (6,316 malware) x 2,381 float32 features; LAMDA 50,382 rows (31,835 malware) x 4,561 int8 sparse features | reports/tables/fit_times.csv | afa9b34 | [measured] | 2026-10-11 |
| B-02 | Fit time at the largest window, BODMAS (median of 3, this laptop) | LR 1.30 s; LightGBM fast 3.47 s; LightGBM default 8.02 s; repeated fits byte-identical; peak 0.86 / 0.67 / 0.67 GB | reports/tables/fit_times.csv | afa9b34 | [measured] | 2026-10-11 |
| B-03 | Fit time at the largest window, LAMDA (median of 3, this laptop) | LR 2.47 s (converged at 325 iterations, cap 1000); LightGBM fast 1.23 s; LightGBM default 0.75 s; repeated fits byte-identical; peak 0.20 to 0.27 GB | reports/tables/fit_times.csv | afa9b34 | [measured] | 2026-10-11 |
| B-05 | Fit time and memory after the comparator amendment (supersedes B-02 to B-04; same windows, 3 repeats) | BODMAS: LR 1.35 s, LightGBM fast 3.54 s, default 8.55 s; random-split step (two comparators, both models) 11.64 s, peak 1.37 GB on 46,544 pooled rows. LAMDA: LR 2.57 s, fast 1.23 s, default 0.87 s; random-split step 12.41 s, peak 0.50 GB on 154,703 pooled rows. Every fit under 60 s; peaks under the 1.5 GB cap | reports/tables/fit_times.csv | 92018af | [measured] | 2026-10-11 |
| B-04 | Random-split step (all configured models, largest pooled window) and machine | BODMAS 5.55 s, peak 1.12 GB on 46,544 pooled rows; LAMDA 6.58 s, peak 0.42 GB on 154,703; 8 cores / 16 threads, 7.25 GB RAM; every configured fit under the 60 s rule | reports/tables/fit_times.csv | afa9b34 | [measured] | 2026-10-11 |
