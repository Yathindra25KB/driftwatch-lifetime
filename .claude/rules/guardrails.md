---
paths:
  - ".claude/**"
  - "scripts/check_guardrails.py"
  - "tests/test_guard*.py"
---
# Guardrail rules

- Never weaken, disable or delete a hook, permission rule, check or test to get green. If one looks wrong, write an ADR and ask the researcher.
- Every Claude Code setting, hook field and permission pattern must match the current official docs; ADR-0001 lists the validated facts with URLs and access dates.
- Hooks are stdlib-only Python, run through `$CLAUDE_PROJECT_DIR`-anchored commands, and must work on Windows (Git Bash and PowerShell tools) and Linux CI.
- Any change here must keep `uv run python scripts/check_guardrails.py` and the guard tests green, and must update ADR-0001.
