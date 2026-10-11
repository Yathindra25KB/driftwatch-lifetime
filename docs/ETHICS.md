# Ethics, licences and data handling

DriftWatch studies how malware detectors **decay** over time, and what label delay, a small analyst budget and drift monitoring do to that decay. It does not study how to defeat detectors.

## What this project never does

- Never downloads, runs, opens, decompiles, unpacks or redistributes malware samples or any binary. The project uses **pre-extracted feature files only**: LAMDA's Drebin-style vectors, BODMAS's EMBER-style vectors and, optionally, EMBER2024 vectors.
- Never builds evasion tooling and never generates adversarial examples. It publishes no detector tuned for evasion and no guidance on bypassing detection.
- Never commits dataset content. `data/` and `results/` are git-ignored. The only data in the repository is a synthetic fixture under 1 MB with the same schema (Phase 2), created for tests and CI.

## Licences

| Item | Licence | Use here |
|---|---|---|
| DriftWatch code | MIT (ADR-0002) | This repository |
| LAMDA | MIT [verified in build guide §1] | Feature files; cite the dataset paper; not redistributed |
| BODMAS | BSD-2-Clause [verified in build guide §1] | Feature files; cite; not redistributed |
| EMBER2024 (optional, Tier 3) | Apache-2.0 [verified in build guide §1] | Win32 weekly subset only; not redistributed |
| AndroZoo | Academic key; redistribution forbidden | Not used (would need a faculty-sponsored key) |
| SOREL-20M | Own terms, not verified | Excluded (build guide §10) |

Every dataset version, source URL and file hash goes into `data/manifest.json` (Phase 2) and its data card under `docs/data_cards/`. The full licence audit is `docs/licence_audit.md` (Phase 12).

## Data handling

- Raw files and caches live under `data/` on the researcher's machine; results live under `results/`. Both are git-ignored, and the guard hook blocks `git add` of either (except `data/manifest.json`).
- Claude Code permissions deny editing `data/**` and reading secrets (`.env`, `secrets/`, keys).
- Labels come from the datasets' own labelling (antivirus-based). LAMDA's card warns of antivirus-centric labelling bias; data cards and limitations will say so (plan Appendix E, threats 20–21).
- No personal data is collected. The feature files describe software, not people.

## Honest reporting

- Every number of consequence goes into `docs/CLAIMS.md`, with its file and commit, before it is written anywhere else.
- Hypotheses and analysis rules are pre-registered (`docs/PREREG.md`, locked by git tags) before results exist. Negative and flat results are reported as they are.
- No contribution is claimed as "first"; the text states what was measured.

## AI assistance

Claude Code (an AI coding agent) implements, tests and drafts under the researcher's direction. The researcher decides scope, approves every pre-registration, ADR and gate, verifies each statistic and rewrites all report and paper text in their own words.

| Item | Status |
|---|---|
| VISTAS AI-assistance disclosure policy | **unknown, to verify** (researcher's answer, 10 Oct 2026) |
| Disclosure plan until verified | Disclose AI assistance in the report and the paper (plan default) |
| Other VISTAS rules (deadline, template, page rules, demo) | unknown, to verify; tracked in `docs/PHASES.md` |
