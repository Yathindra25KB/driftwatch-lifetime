# Getting started

## Install

```bash
pip install driftwatch-lifetime        # or: uv tool install driftwatch-lifetime
driftwatch --version
```

Python 3.12 is required. The distribution name is `driftwatch-lifetime` and the import name is `driftwatch`. The unrelated PyPI package `driftwatch` (a general machine-learning drift library) installs the same import name, so do not install both in one environment ([ADR-0003](DECISIONS/ADR-0003-package-name.md)).

## Check that it works (no data needed)

```bash
driftwatch smoke
```

`smoke` regenerates a small synthetic fixture (random values with the real file layout), runs the full pipeline on it (cache build, time slicer with the C1 to C3 checks, two detectors, A-AUT) and compares the table with a golden copy shipped in the package. It ends with a line starting `MATCH` and exit code 0. Fixture numbers test the code path only; they are never evidence.

## Reproduce Table 1 (needs a clone and about 265 MB of data)

```bash
git clone https://github.com/Yathindra25KB/driftwatch-lifetime
cd driftwatch-lifetime
uv sync --frozen
uv run driftwatch reproduce table1
```

This fetches BODMAS, runs the E0 baseline and compares with the stored Table 1. On a clean clone the time-aware columns matched to four decimals and the random-split comparator columns within 0.006 (see the claims ledger, row E-24). Exit code 3 means the dataset host refused the download; [the data card](data_cards/bodmas.md) documents the manual path.

## Rebuild the tables of E2 to E4

The tables and figures are rebuilt from stored per-slot predictions with no model fits (`scripts/make_tables.py`, `make_e3.py`, `make_e4.py`). The predictions are not committed; to rerun an experiment, build the data cache and follow [the grid guide](GRID.md).

## Where to go next

- What was measured, with every number traceable: [claims ledger](CLAIMS.md), report chapters 7 and 8.
- How the code enforces the protocol: [architecture](architecture/index.md).
- Using the code in your own study: the [API reference](reference.md).
