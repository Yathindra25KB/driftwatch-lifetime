# Changelog

All notable changes to `driftwatch-lifetime` are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Before 1.0.0, a minor version may change the command-line interface or the Python API. Any change that alters a reported number is listed under **Results** with its CLAIMS id.

## [Unreleased]

## [0.1.0] - unreleased

Initial public release. It contains the whole study as run for the capstone report. Every number the README and the report chapters report has a row in `docs/CLAIMS.md` with a source file and a commit. Rows that cite files under `results/` can be regenerated only from the stored predictions, which are not in the repository (they are hashed in `docs/predictions_manifest.csv` and archived privately, E-69). A few rows are marked `[verify]` where the source could not be read (for example how BODMAS's labels were produced, D-17).

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
- E0 to E4 as reported in chapter 7 of the report and in `README.md`; CLAIMS rows E-01 to E-75 (E-66 and E-68 are exploratory, and E-70 to E-75 record the release work, not results).
- Headline: effects are small (hundredths of A-AUT): retraining on bought labels helps a little on LAMDA and about nothing on BODMAS, and no drift monitor beat retraining every third slot (E-59, E-60). The limits that apply to every one of these sentences are in the README under "Limits".
- Pre-registrations: tags `prereg-v1` (E2), `prereg-v2` (E3) and `prereg-v3` (E4), each placed before the results it governs. The exception is RQ1 (E0 and E1): those results were run and read before `prereg-v1`, so RQ1 is a registered reading of known numbers, not a prediction (`docs/PREREG.md`, "What was already known when this file was locked").

### Not included
- Tier 3 (E5 cross-platform replication, E6 EMBER2024) was not run; see `docs/ROADMAP.md`.
- The 8-page paper is planned for a later 0.x release.

[Unreleased]: https://github.com/Yathindra25KB/driftwatch-lifetime/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Yathindra25KB/driftwatch-lifetime/releases/tag/v0.1.0
