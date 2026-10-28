# DriftWatch

[![CI](https://github.com/Yathindra25KB/driftwatch-lifetime/actions/workflows/ci.yml/badge.svg)](https://github.com/Yathindra25KB/driftwatch-lifetime/actions/workflows/ci.yml)
[![Docs](https://github.com/Yathindra25KB/driftwatch-lifetime/actions/workflows/docs.yml/badge.svg)](https://yathindra25kb.github.io/driftwatch-lifetime/latest/)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)

**Status (27 Oct 2026): Tiers 1 and 2 are run (E0 to E4; every planned cell of E2 to E4 completed [E-26, E-40, E-48]); the report is a draft; Tier 3 (cross-platform replication, EMBER2024) is future work.** DriftWatch is an open-source study of how long a malware detector stays useful as malware changes. It applies one time-aware evaluation protocol (TESSERACT constraints C1 to C3, reported with AUT and A-AUT) to pre-extracted feature files from LAMDA (Android) and BODMAS (Windows PE), and asks how **label delay**, a fixed **analyst budget** and **conformal drift monitoring** change a detector's lifetime.

> We study malware detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring in a single time-aware protocol, reported with A-AUT, on Android and Windows PE data.

## What it is
- A reproducible research protocol and the Python package that implements it: a time slicer with C1 to C3 checks, a label-delay and budget simulator, a conformal layer with uncertainty and credibility selectors, four drift monitors behind one alarm interface, and AUT and A-AUT metrics.
- A pre-registered study (`docs/PREREG.md` and its addenda; tags `prereg-v1`, `prereg-v2` and `prereg-v3`) whose every reported number is traceable to a result file and commit (`docs/CLAIMS.md`).
- Tables and figures that are rebuilt from stored per-slot predictions with no model fits (`scripts/make_tables.py`, `scripts/make_figures.py`, `scripts/make_e3.py`, `scripts/make_e4.py`).

| Experiment | Question (RQ) | Status |
|---|---|---|
| E0, E1 | How far does a random split overstate a time-aware score? (RQ1) | done |
| E2 | How much do label delay and analyst budget change the lifetime? (RQ2) | done |
| E3 | Does selecting which samples to label help, and does it shrink with delay? (RQ3) | done |
| E4 | Does retraining when a drift monitor alarms beat retraining every third slot? (RQ4) | done |
| E5, E6 | Cross-platform replication; EMBER2024 | not run: future work |

## What it is not
- Not a malware analysis tool. It never downloads, runs or redistributes malware; it uses feature files only.
- Not an evasion or attack toolkit. It describes how detectors decay, not how to defeat them (`docs/ETHICS.md`).
- Not a production detector, and not related to the PyPI package `driftwatch` (a general ML drift-monitoring library). This project's distribution name is `driftwatch-lifetime` (ADR-0003).

## Install
Python `3.12` is required.

**Not yet published to PyPI** (the release is pending, `docs/RELEASING.md`). Until it is, build the wheel from a clone (`uv build`) and install that: `uv pip install dist/driftwatch_lifetime-0.1.0-py3-none-any.whl`. A locally built wheel ran the smoke experiment from an empty folder with no clone and no data [E-70]. After the release, this works:

```bash
pip install driftwatch-lifetime        # or: uv tool install driftwatch-lifetime
driftwatch --version
driftwatch smoke                       # no data and no clone needed; ends with a line starting MATCH
```

`driftwatch smoke` regenerates a small synthetic fixture (random values in the real file layout), runs the whole pipeline on it and compares the table with a golden copy shipped in the package. Fixture numbers test the code path only; they are never evidence. The unrelated PyPI package `driftwatch` (a general ML drift library) installs the same import name, so do not install both in one environment (ADR-0003).

## Quick start (from a clone)
Requires [uv](https://docs.astral.sh/uv/). uv installs the locked Python itself. Start Claude Code, if you use it, from the repository root: the guardrail hooks resolve every path against the folder where the session started (ADR-0001).

```bash
uv sync --frozen                                  # exact locked environment
uv run pytest -q                                  # fast tests (slow marker excluded)
uv run pytest -q -m slow                          # whole-grid synthetic tests and end-to-end modules
uv run ruff check . && uv run ruff format --check .
uv run driftwatch reproduce table1 --smoke        # minutes, on the synthetic fixture (CI runs it)
uv run driftwatch reproduce table1                # full: fetch BODMAS, run E0, compare with Table 1
```

The full reproduction downloads the BODMAS raw files (265.5 MB [D-09]), runs the E0 configuration on BODMAS and compares the table with `reports/tables/e0_baselines.csv`. On a clean clone it matched: the time-aware columns to four decimals, and the random-split comparator columns within 0.006 (their draw is keyed by the data manifest hash and differs after a rebuild); it took 31 minutes on the development laptop while two other long jobs ran [E-24]. Two later full runs on the same laptop matched as well, in 976 s [E-67] and 1,187 s with the comparator columns within 0.0052 [E-73]; none of these was a different machine. If the download fails, `docs/data_cards/bodmas.md` documents the manual path (the command exits with code 3 and says so).

The tables for E2 to E4 are rebuilt from stored predictions, which are not committed (`results/` is never committed). To rerun an experiment, build the data cache (`uv run driftwatch data build`) and follow `docs/GRID.md`; E4 took 3.3 hours (BODMAS) and 13.0 hours (LAMDA) of cell time on the development laptop [E-48]. `uv run driftwatch grid <config> --smoke` measures time on one seed and one window and prints an extrapolation.

## Headline results (Tier 1), with their limits
Everything below is from stored runs; chapter 7 of the report has the full tables and chapter 8 the limits. Effects are A-AUT differences with 95% two-stage bootstrap intervals over windows and seeds [P-08]; "detected" means the interval excludes zero in the hypothesised direction, and the equivalence margin is 0.01 [P-10] (`docs/PREREG.md`).

- **Retraining on bought labels helps a little on LAMDA.** Periodic retraining with 5% of each month's samples labelled and no extra delay is above never retraining by 0.017 [0.007, 0.024] A-AUT for logistic regression and 0.020 [0.012, 0.022] for LightGBM (about 218 labels per slot) [E-30]. On BODMAS the difference is 0.003 for logistic regression and none for LightGBM [E-29].
- **Late labels cost something on LAMDA.** Delay 0 against delay 3 at 5% of the slot: 0.011 [0.005, 0.017] (LR) and 0.013 [0.008, 0.015] (LightGBM); at 1% the cost is not detected for LR and is inside the 0.01 margin for LightGBM [E-30]. Whether the cost grows with the budget was not a registered contrast and is not claimed.
- **The budget response is positive on LAMDA; diminishing returns are detected in one stratum of four.** 5% against 0.5% of the slot adds 0.013 and 0.017 A-AUT on LAMDA [E-30]. Per 100 extra labels per slot the gain falls from 0.017 to 0.007 between the smallest and largest budget steps for LAMDA LightGBM, the only stratum whose registered concavity interval excludes zero [E-34].
- **The random-split gap depends on the comparator.** Under the registered per-slot comparator the gap is 0.03 to 0.04 on LAMDA and 0.006 to 0.035 on BODMAS, below the 0.05 band (the LAMDA LR interval still contains 0.05); under the window-level comparator it is 0.14 to 0.15 on LAMDA (five seeds) [E-35]. RQ1 was registered after E0 and E1 had been run and read, and the primary comparator was chosen after both numbers were seen and is biased downwards on LAMDA [E-18]. The study does not claim the gap is caused by temporal leakage alone.

**Limits that apply to every sentence above:** the effects are small (hundredths of A-AUT, against LAMDA standard deviations over windows of 0.050 to 0.069 [E-28]); BODMAS has one useful retraining event per window, so its delay numbers measure a delay in one refit, and at delay 3 periodic retraining equals never retraining there by construction [P-12]; LAMDA's 16 windows are about four independent blocks and seeds are draws of the subsample, not replicates of a model, so intervals are wide (by design; their coverage was not measured); all runs are on one machine.

**E3 (selection under delay)** was registered separately (`docs/prereg/addendum-v2.md`) and its numbers are comparable only within E3 (ADR-0009). On LAMDA (ten seeds, 16 windows, 43.6 and 87.3 labels per slot) the advantage of uncertainty or credibility selection over random selection at equal labels is 0.0109 to 0.0177 A-AUT with no delay and 0.0015 to 0.0095 after a delay of three slots; at delay three, three of the eight advantages (all logistic regression) have intervals that include zero [E-43]. The registered interaction is positive in all eight rows, 0.0061 to 0.0118, tested with a Wilcoxon test on seed means that is conditional on the realised windows [E-42]. The rows share one random arm and about four independent blocks of windows, the seed-level test is conditional on the realised windows, and seeds 5 to 9 were added after the five-seed rows had been read, so the intervals are indicative [E-42]. The advantage is not separated from the change in class mix of the labels that selection brings in, and the one arm that leaves the class mix unchanged is not above random [E-46, E-47]. On BODMAS the delay-3 advantage is zero by construction, so its interaction (0.0030 to 0.0079) is not a test of shrinkage [E-41]. Chapter 7 section 7.5 has the limits, including a trap arm whose accuracy is confounded with not retraining.

**E4 (drift monitors)** was registered separately (`docs/prereg/addendum-v3.md`, `docs/DECISIONS/ADR-0010-monitor-inputs-and-reference.md`) and is comparable with E3's random arm, not with E2. Four monitors (KS on top features, MMD, a domain classifier, and a test on conformal scores) each drove retraining at a budget of 1%, against retraining every third slot at the same labels spent, and against a control that refits as often as the monitor but at evenly spaced slots. **No monitor beat periodic retraining:** none of the 32 monitor-minus-periodic contrasts has an interval above zero, and logistic regression with the KS monitor is below it by 0.0089 [-0.0225, -0.0002] at delay 0 and 0.0052 [-0.0136, -0.0007] at delay 3 on LAMDA [E-59, E-60]; "below it" is a descriptive reading without family-wise control [P-18]. At the same number of refits, the timing of the alarms made no difference larger than 0.01 on LAMDA [E-61]. The monitors alarmed in many slots on LAMDA (0.562 to 0.997 of slots for LightGBM, 0.997 for the domain classifier), and their precision at detecting drops in F1 was close to that of a monitor that alarms in every slot; these baselines are exploratory, not registered [E-63]. The thresholds were frozen before the run and not tuned. On BODMAS, periodic retraining has one useful refit per window, and several rows are the same comparison [E-60, E-62]. With 32 contrasts and 10 seeds no Holm-adjusted p-value can fall below 0.0625, so the bootstrap interval is the decision rule [P-18]. Chapter 7 section 7.6 has the limits.

**Not run:** E5 (repeat the headline contrasts on another platform) and E6 (EMBER2024). As defined, E5 has no platform left to repeat on, because E3 and E4 ran on both; they are future work (`reports/G5-tier3-decision.md`).

## Where things are
| Path | Contents |
|---|---|
| `docs/PROTOCOL.md` | Every protocol constant (single source of truth) |
| `docs/PREREG.md`, `docs/prereg/` | Pre-registered hypotheses and analysis rules, and addenda |
| `docs/CLAIMS.md` | Every number, with its file and commit |
| `docs/PHASES.md` | Phase and gate ledger |
| `docs/DECISIONS/` | Architecture decision records |
| `docs/GRID.md` | Running the grids (E2, E3, E4): cells, chunks, ledger, frozen worktree, Kaggle and Colab path |
| `docs/architecture/` | How the system is built: package map, the sealed label queue, the per-slot loop, conformal layer, monitors, evidence chain, pipelines (with diagrams) |
| `docs/MAINTENANCE.md`, `docs/RELEASING.md`, `docs/ROADMAP.md` | The maintenance playbook, the release procedure with its go gates, and future work |
| `CHANGELOG.md` | What changed in each release |
| `docs/results_audit.md` | What is on disk under `results/` (never committed), with code versions and flags |
| `src/driftwatch/` | The package (`data`, `models`, `sim`, `conformal`, `monitors`, `metrics`) |
| `configs/` | One YAML per run family; `e2_*`, `e3_*` and `e4_*` are grid specs |
| `scripts/` | Table, figure and audit scripts (`make_*.py`, `claims_audit.py`, `audit_results.py`, `check_*.py`) |
| `reports/` | Tables, figures, gate evidence files |
| `report/` | The report chapters (drafts) |

## Ethics
The repository contains no malware, no decompiled code and no evasion tooling, and generates no adversarial examples. Feature files are used under their own licences (LAMDA under the MIT licence; BODMAS code under a BSD licence with the dataset licence not stated by its authors; EMBER2024 under the Apache licence). See `docs/ETHICS.md`.

## Documentation
The documentation site has the protocol, the pre-registration, the claims ledger, the report chapters, the architecture and the API reference: https://yathindra25kb.github.io/driftwatch-lifetime/latest/ (versioned: one folder per release).

## Limits
Read these before relying on any result. They are stated in full, with their evidence, in chapter 8 of the report.
- The effects are small against the spread over windows, and several intervals are wide by design (see the limits paragraph under "Headline results").
- Seeds are draws of a subsample, not replicates of a model, and LAMDA's windows overlap: its 16 windows are about four independent blocks [E-42].
- RQ1 (how far a random split overstates the time-aware score) was registered after E0 and E1 had been run and read, so it is a registered reading of known numbers, and its primary comparator was chosen after both numbers were seen [E-18].
- Delay is simulated and the analyst is perfect (the dataset label is the truth). Labels are the datasets' own: LAMDA's card warns of antivirus-centric labelling, and how BODMAS's labels were produced is not verified (D-17, still open). None of this is measured in a real security operations centre.
- Two datasets, two detectors, one machine. Tier 3 (another platform, EMBER2024) was not run.
- The fixture used by `driftwatch smoke` is random data in the real layout. Its numbers are never evidence.

## Licence, citation and acknowledgements
Code: MIT (`LICENSE`). Datasets keep their own licences and are never redistributed (`docs/ETHICS.md`, `docs/licence_audit.md`). The wheel and the repository contain no dataset content other than the synthetic fixture.

To cite the software, use `CITATION.cff` (GitHub shows a "Cite this repository" button); each release is meant to get a DOI from Zenodo (none exists yet; it is added here when it does). Until then:

```bibtex
@software{kb_driftwatch,
  author  = {K B, Yathindra},
  title   = {DriftWatch: malware-detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring},
  year    = {2026},
  url     = {https://github.com/Yathindra25KB/driftwatch-lifetime},
  license = {MIT}
}
```