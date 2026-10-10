# Data card: LAMDA (Android)

| Field | Value |
|---|---|
| Name | LAMDA: A Longitudinal Android Malware Benchmark for Concept Drift Analysis |
| Source | Hugging Face `IQSeC-Lab/LAMDA`, https://huggingface.co/datasets/IQSeC-Lab/LAMDA |
| Version used | commit `ad9614bdd5556767f97ced2fce797c2f06408ebf` (downloaded 10 Oct 2026); file hashes in `data/manifest.json` |
| Files used | `Baseline/<year>/<year>_{train,test}.parquet` (2013, 2014, 2016–2025), `Baseline/feature_mapping.csv`, root `metadata.csv`, `README.md`. The `var_thresh_*` subsets and `NPZ_Version/` are not used. |
| Licence | MIT [verified, dataset card, 10 Oct 2026] |
| Citation | Haque, M. A., Hossain, I., Kamol, M. M., Alam, M. J., Amalapuram, S. K., Talukder, S., & Rahman, M. S. (2026). *LAMDA: A Longitudinal Android Malware Benchmark for Concept Drift Analysis.* ICLR 2026. arXiv:2505.18551. |
| Content | Pre-extracted static features only. This project never downloads, opens or runs an APK. |
| Size | 1,008,381 apps (369,906 malware, 638,475 benign); 4,561 features [measured; matches paper Table 2] |

## How the data was produced (as published)
- APKs were collected from AndroZoo for 2013–2025, except 2015 [verified, paper §3]. The paper gives two reasons for the missing year: 2015 "lacks valid entries" (§3), and "unavailability of hashes in the AndroZoo repository" (Introduction).
- The features are static tokens taken from the decompiled app (Drebin-style categories such as `ActivityList_…`), turned into a bag of words and reduced with a variance threshold to 4,561 columns. `feature_mapping.csv` maps `feat_i` to its token. Values run from 0 to 17 [measured], so they are counts rather than binary flags (see Q7 in the [inventory notes](../../reports/data_inventory_notes.md)).
- The authors provide an 80/20 train/test split per year, stratified by label. **DriftWatch ignores it.** The cache pools both files, and `src_split` is kept for traceability only.

## Labels
- **Label rule.** An app with `vt_detection == 0` is benign and one with `vt_detection >= 4` is malware. Apps with 1–3 detections ("grey") are discarded [verified, paper §3]. The cache confirms the rule holds for every row: 0 conflicts [measured].
- **Families.** Families come from AVClass2. There are 1,381 named families, 435 of them with at least 10 samples. 150,604 malware apps (40.7%) carry an AVClass2 `singleton:<sha>` label, meaning no family was assigned [measured].
- **Warning (dataset card):** labels are "biased toward highly detected malware (AV-centric labeling)". All annotations come from automated pipelines.
  - The 4+ threshold drops borderline apps, so detectors are evaluated on the easier, high-consensus malware.
  - VirusTotal counts depend on the scan date (`vt_scan_date`). This dataset does not publish that date, so labels may reflect later knowledge than the collection date. This is a known form of label leakage in time-aware studies, and DriftWatch cannot remove it. It is reported as a limitation.

## Time
- **Field used: AndroZoo `added`** from the root `metadata.csv`: the date the APK entered AndroZoo [verify, AndroZoo lists page, 10 Oct 2026]. `year_month` in the parquet equals the month of `added` for every row [measured].
- The resolution is seconds. The cache slots by month (base unit), and quarters are built from months.
- **C1 meaning:** time order is collection order, not first-seen or build time (PROTOCOL D13). An app may have existed for years before it was added.
- Coverage runs from 2013-06-09 to 2025-01-26. There are 20 empty months in that span:
  - 2013-07 and 2013-08;
  - 2014-09 to 2016-01 (the "2015 gap", 17 months);
  - 2017-06.

  2025 holds only January 2025.
- **2015 handling:** no rows exist. The slot schemes list the empty months as gap slots, and rolling windows never span them (`.claude/rules/data.md`). The exact policy is in ADR-0004.

## Known biases and limits
1. The labelling is AV-centric (see above). Grey apps are absent, so the benign/malware boundary looks cleaner than it is in the wild.
2. **Class balance swings strongly by month.** The malware share runs from about 0% to 100%: 2016-05 to 2016-12 is nearly all malware, and 2024–2025 is nearly all benign. The yearly totals follow the authors' sampling targets, not real prevalence. C3 subsampling to 10% therefore fails in months with too few benign apps.
3. **Duplicated feature vectors.** 1,008,381 apps hold 679,423 distinct vectors. 23.7% of apps repeat a vector seen in an earlier month, and 2,177 vectors appear with both labels [measured]. See ADR-0004.
4. Malware is scarce late in the series (2023: 7,892; 2024: 794; 2025: 23 apps).
5. The features are static only: no dynamic behaviour, and obfuscation is invisible.

## Processing in DriftWatch
`uv run driftwatch data download lamda`, then `data build lamda`, then `data verify`.
- Batches of 8,192 rows are streamed into one CSR int8 cache per month (`data/cache/lamda/v1/units/YYYY-MM/`), and the full matrix is never densified.
- The build peaked at 0.85 GB against the approved 1.5 GB cap and took 93 s; the cache is 119.6 MB [measured].
- No normalisation or feature selection happens at ingestion.
