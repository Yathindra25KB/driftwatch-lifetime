---
paths:
  - "src/driftwatch/sim/**"
  - "tests/test_queue*.py"
  - "tests/test_runner*.py"
---
# Simulator rules (delay, budget, sealed labels)

- Label delay d lives only in `sim/queue.py`. A label queried in slot t becomes usable from slot t+1+d (d = 0 means the next slot). No other module computes or applies a delay.
- Labels whose release slot falls after the window ends are ignored, by a documented rule.
- The held-back true labels are sealed. Only the queue's release call and the metric code can reach them; selectors and policies cannot. A spy test proves it.
- A slot is scored before any label queried in that slot can exist (stream order).
- Budget is a percentage of the evaluated slot (0.5, 1, 2, 5); always log the absolute count next to the percentage. Calibration labels come only from the reserved random slice.
- Retraining uses only labels that have arrived. The pool design is fixed by ADR before any grid run, never by looking at AUT.
- Deterministic given config and seed; resumable without duplicate rows.
