---
paths:
  - "src/driftwatch/models/**"
  - "src/driftwatch/metrics/**"
  - "tests/test_aut*.py"
  - "scripts/bench_fit.py"
---
# Models and metrics rules

- Scalers, thresholds and feature selectors are fitted on the current training window only; fitted objects carry the window id.
- The decision threshold is fixed (default 0.5, ADR-0006). A tuned threshold may use only the final training slot.
- AUT(f, N) = 1/(N-1) * sum_{k=1..N-1} (f_k + f_{k+1}) / 2 over per-slot F1 of the malware class. A-AUT = mean and std of AUT over rolling windows. Tests: constant F1 gives that constant; a two-point example matches the hand-computed trapezoid.
- Hyperparameters are fixed in config and recorded in docs/PREREG.md before E0. Never tune them to chase published numbers.
- Treat any AUT above 0.90 on a hard split as a leakage alarm until explained.
- A fit over 60 s: fast profile, then subsampling; shrink the grid before the claim.
- True labels are read only by metric code.
