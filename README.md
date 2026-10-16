# DriftWatch

**Status: Tier 1 results exist; the report is a draft.** DriftWatch is an open-source study of how long a malware detector stays useful as malware changes. It applies one time-aware evaluation protocol (TESSERACT constraints C1 to C3, reported with AUT and A-AUT) to pre-extracted feature files from LAMDA (Android) and BODMAS (Windows PE), and asks how **label delay**, a fixed **analyst budget** and **conformal drift monitoring** change a detector's lifetime.

> We study malware detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring in a single time-aware protocol, reported with A-AUT, on Android and Windows PE data.

## What it is
- A reproducible research protocol and the Python package that implements it: a time slicer with C1 to C3 checks, a label-delay and budget simulator, a conformal layer with uncertainty and credibility selectors, and AUT and A-AUT metrics.
- A pre-registered study (`docs/PREREG.md`, tags `prereg-v1` and `prereg-v2`) whose every reported number is traceable to a result file and commit (`docs/CLAIMS.md`).
- Tables and figures that are rebuilt from stored per-slot predictions with no model fits (`scripts/make_tables.py`, `scripts/make_figures.py`, `scripts/make_e3.py`).

## What it is not
- Not a malware analysis tool. It never downloads, runs or redistributes malware; it uses feature files only.
- Not an evasion or attack toolkit. It describes how detectors decay, not how to defeat them (`docs/ETHICS.md`).
- Not a production detector, and not related to the PyPI package `driftwatch` (a general ML drift-monitoring library). This project's distribution name is `driftwatch-lifetime` (ADR-0003).

## Quick start
Requires [uv](https://docs.astral.sh/uv/). uv installs the locked Python itself. Start Claude Code, if you use it, from the repository root: the guardrail hooks resolve every path against the folder where the session started (ADR-0001).

```bash
uv sync --frozen                                  # exact locked environment
uv run pytest -q                                  # fast tests (slow marker excluded)
uv run pytest -q -m slow                          # whole-grid synthetic tests and end-to-end modules
uv run ruff check . && uv run ruff format --check .
uv run driftwatch reproduce table1 --smoke        # minutes, on the synthetic fixture (CI runs it)
uv run driftwatch reproduce table1                # full: fetch BODMAS, run E0, compare with Table 1
```

The full reproduction downloads about 265 MB, runs the E0 configuration on BODMAS and compares the table with `reports/tables/e0_baselines.csv`. On a clean clone it matched: the time-aware columns to four decimals, and the random-split comparator columns within 0.006 (their draw is keyed by the data manifest hash and differs after a rebuild); it took 31 minutes on the development laptop while two other long jobs ran [E-24]. If the download fails, `docs/data_cards/bodmas.md` documents the manual path (the command exits with code 3 and says so).

## Headline results (Tier 1), with their limits
Everything below is from stored runs; chapter 7 of the report has the full tables and chapter 8 the limits. Effects are A-AUT differences with 95% two-stage bootstrap intervals over windows and seeds [P-08]; "detected" means the interval excludes zero in the hypothesised direction, and the equivalence margin is 0.01 [P-10] (`docs/PREREG.md`).

- **Retraining on bought labels helps a little on LAMDA.** Periodic retraining with 5% of each month's samples labelled and no extra delay is above never retraining by 0.017 [0.007, 0.024] A-AUT for logistic regression and 0.020 [0.012, 0.022] for LightGBM (about 218 labels per slot) [E-30]. On BODMAS the difference is 0.003 for logistic regression and none for LightGBM [E-29].
- **Late labels cost something on LAMDA.** Delay 0 against delay 3 at 5% of the slot: 0.011 [0.005, 0.017] (LR) and 0.013 [0.008, 0.015] (LightGBM); at 1% the cost is not detected for LR and is inside the 0.01 margin for LightGBM [E-30]. Whether the cost grows with the budget was not a registered contrast and is not claimed.
- **The budget response is positive on LAMDA; diminishing returns are detected in one stratum of four.** 5% against 0.5% of the slot adds 0.013 and 0.017 A-AUT on LAMDA [E-30]. Per 100 extra labels per slot the gain falls from 0.017 to 0.007 between the smallest and largest budget steps for LAMDA LightGBM, the only stratum whose registered concavity interval excludes zero [E-34].
- **The random-split gap depends on the comparator.** Under the registered per-slot comparator the gap is 0.03 to 0.04 on LAMDA and 0.006 to 0.035 on BODMAS, below the 0.05 band (the LAMDA LR interval still contains 0.05); under the window-level comparator it is 0.14 to 0.15 on LAMDA [E-35]. The primary comparator was chosen after both numbers were seen and is biased downwards on LAMDA [E-18]. The study does not claim the gap is caused by temporal leakage alone.

**Limits that apply to every sentence above:** the effects are small (hundredths of A-AUT, against standard deviations over windows of 0.05 to 0.07 [E-28]); BODMAS has one useful retraining event per window, so its delay numbers measure a delay in one refit, and at delay 3 periodic retraining equals never retraining there by construction [P-12]; LAMDA's 16 windows are about four independent blocks and seeds are draws of the subsample, not replicates of a model, so intervals are wide (by design; coverage was not measured beyond a synthetic check); all runs are on one machine.

**E3 (selection under delay)** was registered separately (`docs/prereg/addendum-v2.md`) and its numbers are comparable only within E3 (ADR-0009). On LAMDA (seeds 0 to 4, 16 windows) the advantage of uncertainty or credibility selection over random selection at equal labels is 0.0105 to 0.0194 A-AUT with no delay and 0.0019 to 0.0096 after a delay of three slots; the interaction is positive in all eight rows, 0.0064 to 0.0116 [E-42, E-43]. The advantage is not separated from the change in class mix of the labels that selection brings in [E-47]. On BODMAS the delay-3 advantage is zero by construction, so its interaction (0.0030 to 0.0079) is not a test of shrinkage [E-41]. Chapter 7 section 7.5 has the limits, including a trap arm whose accuracy is confounded with not retraining.

## Where things are
| Path | Contents |
|---|---|
| `docs/PROTOCOL.md` | Every protocol constant (single source of truth) |
| `docs/PREREG.md`, `docs/prereg/` | Pre-registered hypotheses and analysis rules, and addenda |
| `docs/CLAIMS.md` | Every number, with its file and commit |
| `docs/PHASES.md` | Phase and gate ledger |
| `docs/DECISIONS/` | Architecture decision records |
| `docs/GRID.md` | Running the grids: cells, chunks, ledger, Kaggle and Colab path |
| `src/driftwatch/` | The package (`data`, `models`, `sim`, `conformal`, `metrics`) |
| `configs/` | One YAML per run family; `e2_*` and `e3_*` are grid specs |
| `reports/` | Tables, figures, gate evidence files |
| `report/` | The report chapters (drafts) |

## Ethics
The repository contains no malware, no decompiled code and no evasion tooling, and generates no adversarial examples. Feature files are used under their own licences (LAMDA under the MIT licence; BODMAS code under a BSD licence with the dataset licence not stated by its authors; EMBER2024 under the Apache licence). See `docs/ETHICS.md`.

## Licence and citation
Code: MIT (`LICENSE`). Datasets keep their own licences (`docs/ETHICS.md`). Citation metadata is in `CITATION.cff`: Yathindra K B, DriftWatch: malware-detector lifetime under label delay, a fixed analyst budget and conformal drift monitoring (pre-release software, repository `Yathindra25KB/Driftwatch-`).
