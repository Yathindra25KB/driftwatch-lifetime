# Changelog

All notable changes to `driftwatch-lifetime` are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Before 1.0.0, a minor version may change the command-line interface or the Python API. Any change that alters a reported number is listed under **Results** with its CLAIMS id.

## [Unreleased]

## [0.1.0] - unreleased

First public release. It contains the whole study as run for the capstone report. Every number it reports is traceable in `docs/CLAIMS.md`.

### Added
- **Data:** download, build, verify and inventory the LAMDA (Android) and BODMAS (Windows PE) feature files. Caching respects a memory cap, and a manifest records the expected hashes (`driftwatch data ...`). No dataset content is shipped.
- **Time-aware protocol:** a slot and window slicer with the TESSERACT constraints C1 to C3 as raising assertions, and a leakage canary (`driftwatch data slice`).
- **Models:** logistic regression and LightGBM behind one interface; AUT and A-AUT metrics with a moving-block bootstrap.
- **Simulator:** label delay in a sealed queue, a fixed analyst budget, labelling pools, periodic and never-retrain policies; per-slot predictions stored with config, seed and package versions (`driftwatch run`).
- **Grids:** the pre-registered delay x budget grid E2, conformal selection E3 and drift monitors E4, run by cell with a ledger and resume (`driftwatch grid`).
- **Conformal layer:** Mondrian calibration, uncertainty and credibility selectors.
- **Monitors:** four drift monitors (KS on top features, MMD, a domain classifier, a p-value uniformity test) behind one alarm interface, and monitor-triggered retraining.
- **Reproduction:** `driftwatch reproduce table1` (full, on BODMAS) and `--smoke` (synthetic fixture).
- **Report and evidence:** report chapters 0 to 9, the claims ledger with its audit script, and a bibliography checker.
- **Release and maintenance:** release pipeline (TestPyPI rehearsal, PyPI through Trusted Publishing, GitHub Release, Zenodo DOI), documentation site, maintenance playbook, monthly arXiv audit, issue templates.

### Results
- E0 to E4 as reported in chapter 7 of the report and in `README.md`; CLAIMS rows E-01 to E-69. Pre-registrations: tags `prereg-v1` (E2), `prereg-v2` (E3) and `prereg-v3` (E4), each placed before the results it governs.

### Not included
- Tier 3 (E5 cross-platform replication, E6 EMBER2024) was not run; see `docs/ROADMAP.md`.
- The 8-page paper is planned for a later 0.x release.

[Unreleased]: https://github.com/Yathindra25KB/driftwatch-lifetime/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Yathindra25KB/driftwatch-lifetime/releases/tag/v0.1.0
