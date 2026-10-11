# ADR-0003: PyPI distribution name

**Status:** ACCEPTED
**Date:** 2026-10-10
**Deciders:** Yathindra (chose the name in the Phase 1 question round); Claude Code (checked availability)
**Phase:** 1

## Context
The build guide calls the package `driftwatch` and every phase prompt uses the import path `src/driftwatch/...`. The plan warned that the name `driftwatch` might be taken on PyPI [verify]. Phase 12 publishes to TestPyPI and then PyPI through Trusted Publishing.

## Availability evidence (checked 2026-10-10)
Method: HTTP GET `https://pypi.org/pypi/<name>/json` and `https://test.pypi.org/pypi/<name>/json`. A 404 response means no project exists under that name.

| Name | PyPI | TestPyPI |
|---|---|---|
| `driftwatch` | **Taken.** v0.4.0, uploaded 2026-02-18; summary "Lightweight ML drift monitoring, built for real-world pipelines"; MIT; project URL github.com/VincentCotella/DriftWatch; imports as `driftwatch` | 404 (free) |
| `driftwatch-ml` | 404 (free) | 404 (free) |
| `driftwatch-lifetime` | 404 (free) | 404 (free) |
| `driftwatch-malware` | 404 (free) | 404 (free) |
| `driftwatch-sec` | 404 (free) | 404 (free) |

A 404 does not guarantee that PyPI will accept a name (PyPI can refuse names it considers too similar or reserved) [verify at Phase 12 with the TestPyPI rehearsal].

Other uses of "DriftWatch" noticed (web search, 2026-10-10): FieldWatch Inc.'s DriftWatch specialty-crop registry for pesticide drift (driftwatch.org); an iOS anchor-drift alarm app; a NOAA buoy-tracking tool. A quick search found no registered "DriftWatch" trademark. This is not a legal clearance [verify].

## Options considered

### Option A: `driftwatch-lifetime`
Names what is measured (detector lifetime) and is clearly distinct from the generic ML-drift `driftwatch` package.

### Option B: `driftwatch-ml`
Short, but easily mistaken for an add-on to the existing `driftwatch` ML-drift library.

### Option C: `driftwatch-sec`
Short; less descriptive.

### Option D: `driftwatch-malware`
Most descriptive. Risks tripping corporate proxies or antivirus heuristics, and can be misread as a malware distribution.

## Decision (choice)
**Distribution name `driftwatch-lifetime`; import name `driftwatch`.** The import name stays `driftwatch` because every later phase prompt, the guide's module map and the reviewers' instructions refer to `src/driftwatch/`.

## Consequences
- `pyproject.toml`: `name = "driftwatch-lifetime"`, `[tool.uv.build-backend] module-name = "driftwatch"`, console script `driftwatch`.
- **Known clash:** the PyPI package `driftwatch` also installs the import package `driftwatch`. Installing both in one environment would overwrite files. The README will say so at release. Renaming the import package later would touch every module path, so revisit only if a user reports the clash.
- **Accidental-upload guard:** `pyproject.toml` carries the classifier `Private :: Do Not Upload`. Per https://pypi.org/classifiers/ (accessed 2026-10-10): "PyPI will always reject packages with classifiers beginning with `Private ::`." Phase 12 removes it, after the licence, ethics and claims audits and the researcher's go.
- Re-check availability right before the Phase 12 TestPyPI rehearsal. If the name has been taken by then, fall back to `driftwatch-sec` and amend this ADR.
