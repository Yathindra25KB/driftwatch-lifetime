# Data card: BODMAS (Windows PE)

| Field | Value |
|---|---|
| Name | BODMAS: An Open Dataset for Learning based Temporal Analysis of PE Malware |
| Source | https://whyisyoung.github.io/BODMAS/ (Google Drive folder `1Uf-LebLWyi9eCv97iBal7kL1NgiGEsv_`) |
| Version used | Drive file IDs `bodmas.npz` `1_7uhKCrc9hmIOxxfZMoKK6aP8-GJ-DNJ`, `bodmas_metadata.csv` `16UtiitjekNfqHGlLWtxkxyuU23o2qaja`, `bodmas_malware_category.csv` `10bdoOn9qhf647HwANpAga78ye8rOEgwJ` (downloaded 10 Oct 2026); sha256 in `data/manifest.json` |
| Licence | The repository code is BSD-2-Clause [verified, github.com/whyisyoung/BODMAS README, 10 Oct 2026]. No separate licence is stated for the dataset files; the build guide lists BSD-2-Clause [verify] (inventory notes, Q5). |
| Citation | Yang, L., Ciptadi, A., Laziuk, I., Ahmadzadeh, A., & Wang, G. (2021). *BODMAS: An Open Dataset for Learning based Temporal Analysis of PE Malware.* 4th Deep Learning and Security Workshop (DLS). |
| Content | Pre-extracted EMBER-style feature vectors only. The binaries are available from the authors on request; this project never requests, downloads or opens them. |
| Size | 134,435 samples (57,293 malware, 77,142 benign); 2,381 float32 features, unnormalised [measured; matches the page] |

## How the data was produced (as published)
- The feature vectors are EMBER-style static PE features: 2,381 dimensions, stored unnormalised [verified, BODMAS page].
- Malware was collected from August 2019 to September 2020 [verified, BODMAS page]. `bodmas_metadata.csv` (sha, timestamp, family) is aligned row by row with `X` and sorted by timestamp [measured: 0 inversions].
- `bodmas_malware_category.csv` gives a category (trojan, worm, …) for every malware sample [measured: all 57,293 covered].

## Labels
- `y` = 1 marks malware, 0 benign. An empty family means benign [verified, page]. Label and family agree for every row [measured].
- The page and the repository README do not describe how labels were produced. The paper should be consulted [verify].
- There are 582 named malware families, 196 of them with at least 10 samples [measured].
- 7 benign rows carry `VirusShare_<md5>` identifiers instead of a sha256. Their labels are kept as published and flagged as an open question (inventory notes, Q3).

## Time
- **Field:** `timestamp`, described as when the sample "first appeared" [verified, page]. It is stored in UTC. 3,712 values carry no offset and are read as UTC [measured; assumption Q4].
- **The two classes differ** [measured]:
  - **Malware:** 2019-08-29 to 2020-09-30, second-level, essentially never at midnight.
  - **Benign:** 2007-01-01 to 2020-09-30. 85.8% are date-only (exactly midnight), and they arrive in daily batches: in the study window the median is 150 rows per day, the regular maximum is 599, and many days hold exactly 300.
    - Four round-date outliers look like placeholders: 2020-01-01 (5,877 rows), 2015-01-01 (1,563), 2018-02-01 (1,100) and 2018-03-19 (1,005).
    - 13,514 benign rows predate the first malware week.
    - The cache flags each row with `ts_date_only`, `ts_naive` and `ts_tie_count`. ADR-0004 proposes excluding date-only timestamps shared by at least 1,000 rows.
- **C1 and C2 meaning.**
  - The benign timestamps appear to be a different kind of date from the malware first-seen times (PROTOCOL D13), so the inventory notes list this as Q2.
  - A weekly slot satisfies C2 only where both classes are present. In 2020-W02 to 2020-W07 there are 6 to 29 benign against about 1,000 malware per week.
  - ADR-0004 proposes a study window (the dense period 2019-W35 to 2020-W40, 58 ISO weeks) and the slot length.
- **Span (PROTOCOL D10).** The malware period covers 13 months plus a few days (29 Aug 2019 to 30 Sep 2020), which is 58 ISO weeks.

## Known biases and limits
1. **Benign timestamp semantics and placeholder dates** (above). Benign samples cannot be placed in time as precisely as malware.
2. The benign share per week varies from almost 0 (Jan–Feb 2020) to over 85% (2020-W01).
3. **The series is short.** 58 weeks gives few slots: 15 four-week slots, or 29 two-week slots.
4. The features are static only, and the feature extractor version is fixed to the release (EMBER-style).
5. Duplicate vectors are negligible: 7 pairs, 4 rows across weeks [measured].

## Processing in DriftWatch
`uv run driftwatch data download bodmas` (via gdown; a Drive quota error stops the download with manual steps), then `data build bodmas`, then `data verify`.
- Rows are streamed straight out of the compressed `X.npy` member and written as one float32 `.npy` per ISO week (`data/cache/bodmas/v1/units/YYYY-Www/`), which can be memory-mapped.
- The cache v2 build peaked at 0.56 GB against the 1.5 GB cap and took 23.4 s; the cache is 1,231.2 MB [measured].
- The loader's metadata (`family`, `category`, and `ts` through its time of day) reveals the label. Selectors, policies and monitors get the slicer's opaque `EvalSlot.public()` view only (ADR-0004, addendum 1); `SlotData.public()` keeps `row_id`, which is the time rank, and is loader-level only.
- No normalisation happens at ingestion: scaling is fitted on each training window in later phases.
