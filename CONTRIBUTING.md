# Contributing

Thanks for your interest. DriftWatch is a pre-registered study, so some changes are welcome as they are and some need a process.

## Welcome as pull requests

- Bug fixes, documentation fixes and tests.
- Packaging, CI and documentation-site improvements.
- Dependency updates that leave every reported number unchanged (`docs/MAINTENANCE.md`).
- Related-work suggestions (open a *Related work* issue with an arXiv id or DOI).

## Needs a proposal first (open an issue)

- Anything that changes a reported number, a protocol constant (`docs/PROTOCOL.md`) or an analysis rule. Results change only through a new pre-registration addendum written **before** any run, never by looking at results.
- A new dataset loader: it needs a data card, a licence that permits the use, and a manifest with hashes. Datasets are never committed.
- A new monitor, selector or model arm: it needs a registered hypothesis and an entry in the decision records.

## Not accepted

- Evasion or attack tooling, adversarial-example generation, or anything that downloads, runs or redistributes malware (`docs/ETHICS.md`).
- Changes that weaken, skip or delete a constraint test (C1 to C3), a leakage test or a guardrail to make a build pass.
- Dataset content, results or secrets in the repository.

## Set up and check

```bash
uv sync --frozen
uv run pytest -q                                  # fast tests
uv run pytest -q -m slow                          # slow tests (about 10 minutes)
uv run ruff check . && uv run ruff format --check .
uv run python scripts/check_guardrails.py
uv run driftwatch smoke
```

Use conventional commit messages (`fix(queue): ...`, `docs: ...`). Add a line to `CHANGELOG.md` under **Unreleased**. Rules that bind every change are in `CLAUDE.md`; the architecture is in `docs/architecture/index.md`.

## Licence

By contributing you agree that your contribution is licensed under the MIT licence of this repository.
