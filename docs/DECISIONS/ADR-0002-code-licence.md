# ADR-0002: Code licence

**Status:** ACCEPTED
**Date:** 2026-10-10
**Deciders:** Yathindra (chose MIT in the Phase 1 question round); Claude Code (proposed)
**Phase:** 1

## Context
DriftWatch will be public by Phase 12, with a PyPI package and a Zenodo DOI. The datasets it uses are licensed MIT (LAMDA), BSD-2-Clause (BODMAS) and Apache-2.0 (EMBER2024, optional) [verified in build guide §1]. The repository redistributes no dataset content except a synthetic fixture. Free tools only.

## Options considered

### Option A: MIT
Short, permissive and widely understood; the same licence as LAMDA. No explicit patent grant.

### Option B: Apache-2.0
Permissive, with an explicit patent grant and patent-retaliation clause. Requires a NOTICE file and statements of changes from redistributors, which means slightly more upkeep.

## Decision (choice)
**MIT.** The project is a research artifact with no patentable machinery. It favours the simplest terms for reuse in coursework and research, and it matches the primary Android dataset's licence.

## Consequences
- `LICENSE` holds the MIT text, "Copyright (c) 2026 Yathindra K B". `pyproject.toml` declares `license = "MIT"` and `CITATION.cff` declares `license: MIT`.
- No patent grant is given. Acceptable for this project.
- Dataset licences are separate from the code licence; `docs/ETHICS.md` and the Phase 12 licence audit cover them.
