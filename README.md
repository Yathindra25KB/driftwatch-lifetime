# DriftWatch

**Status: pre-release.** No results yet. Phase 1 of 12 (foundations and governance) is in progress.

DriftWatch is an open-source study of how long a malware detector stays useful as malware changes. It applies one time-aware evaluation protocol (TESSERACT constraints C1–C3, reported with AUT and A-AUT) to pre-extracted feature files from LAMDA (Android) and BODMAS (Windows PE). It asks how **label delay**, a fixed **analyst budget** and **conformal drift monitoring** change a detector's lifetime.

## What it is
- A reproducible research protocol and the Python package that implements it: a time slicer with C1–C3 checks, a label-delay and budget simulator, conformal and classical drift monitors, and AUT/A-AUT metrics. These are built in Phases 2–9.
- A pre-registered study (`docs/PREREG.md`) whose every reported number is traceable to a result file and commit (`docs/CLAIMS.md`).

## What it is not
- Not a malware analysis tool. It never downloads, runs or redistributes malware; it uses feature files only.
- Not an evasion or attack toolkit. It describes how detectors decay, not how to defeat them (`docs/ETHICS.md`).
- Not a production detector, and not related to the PyPI package `driftwatch` (a general ML drift-monitoring library). This project's distribution name is `driftwatch-lifetime` (ADR-0003).

## Quick start (development)
Requires [uv](https://docs.astral.sh/uv/). uv installs Python 3.12 itself. Start Claude Code from the repository root: the guardrail hooks resolve every path against the folder where the session started (ADR-0001).

```bash
uv sync --frozen                            # exact locked environment
uv run pytest -q                            # fast tests (slow marker excluded)
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_guardrails.py   # watch each guardrail fire
uv run driftwatch --version
```

## Where things are
| Path | Contents |
|---|---|
| `docs/PROTOCOL.md` | Every protocol constant (single source of truth) |
| `docs/PREREG.md` | Pre-registered hypotheses and analysis rules |
| `docs/PHASES.md` | Phase and gate ledger, weekly hours |
| `docs/DECISIONS/` | Architecture decision records |
| `docs/prompts/` | The twelve phase prompts |
| `src/driftwatch/` | Package (empty modules until their phase) |

## Licence and citation
Code: MIT (`LICENSE`). Datasets keep their own licences (`docs/ETHICS.md`). Citation metadata is in `CITATION.cff`.
