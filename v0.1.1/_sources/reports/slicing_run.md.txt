# Full-dataset slicing run (Phase 3)

`uv run driftwatch data slice all --nT 4 --nE 12 --stride 1 --ratio 0.10 --min-malware 50`, code version `4ce5cba` (clean tree), data manifest `sha256:50bf7ae3...` (cache v2), 11 Oct 2026, 8 GB Windows laptop, memory cap 1.5 GB. Stride 1 is the heaviest setting (most window overlap, most reloads), chosen as a stress test. This run exercises the slicer only: no model, no AUT. Per-slot manifests are in `results/slicing/` (not committed).

| | LAMDA (month) | BODMAS (2 weeks) |
|---|---|---|
| Grid slots / usable / skipped | 140 / 97 / 43 | 29 / 26 / 3 |
| Windows (nT 4, nE 12, stride 1) | 47 | 2 |
| Evaluation slots yielded | 564 | 24 |
| Evaluation rows after C3 | 2,466,046 | 67,065 |
| Training rows loaded | 1,422,358 | 34,229 |
| Wall-clock | 28.6 s | 2.9 s |
| Peak memory | 0.40 GB | 0.69 GB |
| Feature matrices densified | 0 | 0 (dense by format) |
| C1, C2, C3 violations | 0 | 0 |
| Rows excluded by the placeholder rule | 0 | 5,877 benign (2020-01-01) |

Skipped BODMAS slots: `2w:2019-12-30` (323 benign after exclusion, 35 malware kept at 10%), `2w:2020-01-13` (27 benign), `2w:2020-01-27` (14 benign). This reproduces ADR-0004 decision 5. The first BODMAS run (9 slots) is shorter than nT + nE = 16, so it hosts no window at this setting.
