# Architecture

This section explains how DriftWatch is built and why it is built that way: what the packages are, how a label travels from the dataset to a retrained detector, which parts of the code make leakage impossible rather than merely unlikely, and how a number gets from a result file into the report. It is written for a reader who wants to review, extend or reproduce the study, and it points at the code (file and symbol) behind every box.

Protocol constants (slot lengths, window sizes, delays, budgets, ratios) are **not** repeated here. They live in [PROTOCOL](../PROTOCOL.md), which is the single source of truth. Numbers that are results are in the [claims ledger](../CLAIMS.md).

```{toctree}
:maxdepth: 1

data-and-slicing
simulator
conformal-and-monitors
evidence-and-reproducibility
quality-and-release
extending
screenshots
```

## What the system does

DriftWatch simulates a malware detector that is deployed and then lives through time. Samples arrive in time slots. In each slot the detector scores the new samples, an analyst may buy labels for a small budgeted selection of them, those labels arrive some slots later, and a policy decides when to retrain. The system measures how long the detector stays useful (AUT and A-AUT of the per-slot F1) under different delays, budgets, selectors and retraining triggers, always inside the time-aware constraints C1 to C3.

Three design decisions shape everything else:

1. **Leakage is prevented by types and by one door, not by discipline.** The true label of a sample is reachable only through the label queue and the scoring function. Selectors, policies and monitors receive an `OpaqueSlot` that has no labels (see [simulator](simulator.md)).
2. **A run is a pure function of a configuration.** One YAML file, a seed and the locked environment determine every stored prediction; the run records the hash of all three (see [evidence](evidence-and-reproducibility.md)).
3. **Tables are rebuilt from stored predictions.** Models are fitted once, during a run. Every table, figure and contrast afterwards is computed from the per-slot predictions on disk, with no model fit, so analysis can be repeated and reviewed cheaply.

## Package map

```{mermaid}
flowchart TB
    cli["<b>driftwatch.cli</b><br/>data, run, grid, reproduce, smoke"]
    sim["<b>driftwatch.sim</b><br/>sealed label queue, selectors, policies,<br/>runners, grids, Table 1 reproduction"]
    metrics["<b>driftwatch.metrics</b><br/>per-slot scores, AUT and A-AUT,<br/>statistics, table builders"]
    data["<b>driftwatch.data</b><br/>download, build, verify,<br/>slicer, C1 C2 C3"]
    models["<b>driftwatch.models</b><br/>detectors"]
    conformal["<b>driftwatch.conformal</b><br/>p-values, credibility"]
    monitors["<b>driftwatch.monitors</b><br/>four monitors, one Alarm"]

    cli --> sim
    cli --> data
    cli --> metrics
    sim --> data
    sim --> models
    sim --> conformal
    sim --> monitors
    sim --> metrics
    metrics -.-> sim
```

*Figure 1. Packages and the direction of imports, counted from the source. `data`, `models`, `conformal` and `monitors` are leaf packages: they import nothing else from DriftWatch, only numpy, scipy, scikit-learn and the like. `sim` composes them. `metrics` supplies the per-slot and AUT primitives that the simulator calls; its table builders (dotted arrow) read only `sim.ledger`, a module kept free of simulator and model imports so that analysis never needs to fit anything.*

| Package | Responsibility | Key symbols |
|---|---|---|
| `driftwatch.data` | Fetch feature files, build per-unit caches, verify them against the manifest, cut time slots and windows, enforce C1 to C3 | `SlotSource`, `slice_windows`, `constraints.*`, `Layout` |
| `driftwatch.models` | One detector interface: fit on a window, score with a threshold fixed at construction | `Detector` in `models/base.py`, `linear`, `lgbm` |
| `driftwatch.sim` | The label queue, selectors, policies, the training pool, runners, grids with a resumable ledger, Table 1 reproduction | `SealedSlot`, `LabelQueue`, `Selector`, `Policy`, `run`, `reproduce_table1` |
| `driftwatch.conformal` | Class-conditional (Mondrian) p-values, credibility, pluggable nonconformity scores, recalibration from arrived labels | `mondrian`, `nonconformity` |
| `driftwatch.monitors` | Four drift monitors behind one `Monitor` protocol that returns an `Alarm` and never sees labels | `Monitor`, `Alarm`, `MonitorState` |
| `driftwatch.metrics` | Per-slot scores, AUT and A-AUT, moving-block bootstrap, contrasts, and the table builders for E0 to E4 | `score_slot`, `aut`, `stats`, `*_tables` |
| `driftwatch.cli` | The `driftwatch` command: `data`, `run`, `grid`, `reproduce`, `smoke` | `main` |

## From hard rule to enforcement

The project's [hard rules](https://github.com/Yathindra25KB/driftwatch-lifetime/blob/main/CLAUDE.md) are not only text. Each one has a place in the code or tooling where it is checked, and a test that fails if the check is removed.

| Rule | Where it is enforced | How it is tested |
|---|---|---|
| C1, C2, C3 are assertions that raise | `data/constraints.py` (`ConstraintViolation`); re-checked by `SealedSlot.assert_c1` against the real training pool | constraint suites and the slicer mutation matrix (every deliberate breakage must be caught, [W-07](../CLAIMS.md)) |
| Label delay lives only in `sim/queue.py` | `LabelQueue.release_slot` is the single place `t + 1 + d` is computed | `tests/test_queue_delay.py`, property tests over the delay range |
| True labels reach only the queue and the metric code | `SealedSlot` hides `y`; selectors, policies and monitors receive `OpaqueSlot` (no labels, no row ids) | the spy test `tests/test_sim_sealed.py`: labels are replaced by objects that record every caller and raise on anything unexpected |
| Fit scalers, thresholds and calibration sets on the current training window only | detectors take the window id at fit and refuse to score under another; calibration rows are never rows the scoring model was fitted on (ADR-0009) | model and conformal suites; leakage reviews of E2, E3 and E4 |
| One YAML config per run; log hash, seeds, versions; store per-slot predictions | `sim/config.py` (`RunConfig`, `config_hash`, `lock_sha256`, `package_versions`), `sim/results.py` | config and result-store tests; repeat runs give identical prediction hashes |
| No number without a ledger row | `scripts/claims_audit.py` fails a paragraph that has a number and no resolving claim id | the audit runs in the closeout and release checks |
| Locked files stay locked | the guard hook blocks edits to the pre-registration after its tag; `tests/test_repo_invariants.py` fails if it differs from its tag | guard tests and the guardrail demonstration |

## Reading order

1. [Data and slicing](data-and-slicing.md) for how time is cut into slots and windows.
2. [Simulator](simulator.md) for the sealed label queue and the per-slot loop, which are the heart of the design.
3. [Conformal layer and monitors](conformal-and-monitors.md) for the signals that selectors and retraining policies use.
4. [Evidence and reproducibility](evidence-and-reproducibility.md) for how a run becomes a table and a ledger row.
5. [Quality and release](quality-and-release.md) for the guardrails, CI, release and maintenance pipelines.
6. [Extending](extending.md) for adding a dataset, selector or monitor without breaking the protocol.
