## What and why

## Checks
- [ ] `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`
- [ ] `uv run python scripts/check_guardrails.py`
- [ ] No reported number changed. If one did: it is a CHANGE_REQUEST with a pre-registration addendum, and `docs/CLAIMS.md` has the new row
- [ ] No dataset content, no malware, no secrets; nothing from `data/` or `results/`
- [ ] No guardrail, constraint test or locked file was weakened or edited (the pre-registration, tagged addenda, golden files)
- [ ] `CHANGELOG.md` updated under **Unreleased**
