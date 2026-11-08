# ADR-0009: Calibration rows are not training rows; the E3 initial model leaves a hold-out

**Status:** ACCEPTED by the researcher on 2026-10-15: option A (calibration rows never train), without the sensitivity cell of option C. It is registered with `docs/prereg/addendum-v2.md`.
**Date:** 2026-10-15
**Deciders:** Yathindra (researcher, decides); Claude Code (engineering lead, proposes)
**Phase:** 8

## Context
- ADR-0007 fixed the Tier 1 pool: the initial window plus every arrived label, weight 1, no truncation. In E0 to E2 every label that arrives enters the pool; there is no calibration set.
- E3 adds a calibration set for conformal p-values. Split conformal prediction gives valid p-values when the calibration samples are exchangeable with the test samples **and the scoring model was not fitted on them**. A model scores its own training rows as less unusual than fresh rows, so calibration scores of training rows are too low and the p-values of fresh samples too small (credibility looks worse than it is).
- The Phase 8 prompt says both "keep the same pool design as Tier 1" and "the initial calibration set comes from a time-ordered hold-out inside the initial training window that was **not used to train that model**". The second sentence states the intent for the initial set; it is silent on the labels that arrive later.
- The leakage review of Phase 6 (item 9) flagged exactly this: if the calibration slice is consumed and also enters the pool, conformal p-values come out optimistic.

## Options

### A. Calibration rows never enter the training pool (recommended)
The initial model is fitted on the window minus its newest 20% of rows (by time); those rows are the initial calibration set. Arrived labels from the reserved random slice go to the calibration buffer only. All arms do this, including random selection, so arms differ only in how the non-reserved budget is spent.
- Pro: valid conformal calibration; the credibility selector and the later monitors read p-values that mean what they say.
- Con: every arm trains on fewer rows than the E2 arms (the hold-out, plus the reserved 20% of each slot's labels are not used for training); E3 absolutes are not comparable with E2. The study compares arms only within E3.

### B. Calibration rows also enter the pool (Tier 1 pool unchanged)
- Pro: identical pool rule to Tier 1.
- Con: p-values are biased low for fresh samples, the hold-out would also need to be in the initial fit (contradicting "not used to train that model") or be dropped, and credibility-based selection is evaluated with a miscalibrated score. The bias would be reported, not removed.

### C. Disjoint reserved slice, pool otherwise unchanged
Calibration rows are used for calibration and not for training, but the initial model keeps the whole window.
- Con: the initial hold-out is then trained on, which the prompt forbids.

## Decision (recommended)
Option A, with these rules (all registered in `docs/prereg/addendum-v2.md`):
1. The initial hold-out is the newest 20% of the initial window's rows by time; no timestamp is split across the boundary.
2. The reserved random slice (default 20% of each slot's budget; 0, 10, 20, 40% in the ablation) is the only source of later calibration labels; rows chosen by a selector never enter the calibration buffer.
3. Calibration rows are not training rows (`calibration_in_pool: false`); the flag is a config key so that option B can be run as a stated sensitivity check if the researcher wants it.
4. Recalibration happens in every slot in which calibration rows arrived or the model was refitted; at least 20 rows per class are needed, otherwise the previous calibration is kept and the skip is counted.
5. All arms of E3 share these rules; labels spent are asserted equal in every slot.

## Consequences
- E3 results are comparable within E3 only. Chapter 7 must not set an E3 A-AUT beside an E2 A-AUT.
- The training pool of an E3 arm is smaller than that of the corresponding E2 arm by the hold-out and by the reserved slice; the label-influence share (CLAIMS E-13 to E-15) was measured for E2 and does not carry over.
- The Tier 1 pool design (ADR-0007) is not changed; E3 is a different experiment with its own pool rule.

## Evidence and references
- `src/driftwatch/conformal/recalibrate.py`, `src/driftwatch/sim/runner_e3.py`, `tests/test_conformal.py`, `tests/test_runner_e3.py` (contamination tests, including a deliberately broken router that fails).
- Leakage review of Phase 6, item 9 (carried item 12 of reports/G2.md); `.claude/rules/conformal-monitors.md`.
