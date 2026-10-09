---
paths:
  - "configs/**"
  - "scripts/run_grid.py"
---
# Config rules

- One YAML config per run family; never edit a config that produced stored results. Copy it to a new file instead.
- Keys (plan Appendix C): dataset, slots, window (nT, nE, stride), ratio, seeds, model, policy, selector, delay, budget_pct, nonconf, pool, monitors, output.
- The config hash covers every key plus the code version and the lock-file hash; it is logged with every result row and recorded in docs/PHASES.md at closeout.
- Seeds are explicit lists, never implicit defaults. Constants come from docs/PROTOCOL.md; anything not there needs an ADR.
