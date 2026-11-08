# Extending DriftWatch

DriftWatch is a study, so extensions come in two kinds. A change that only adds a *capability* (a loader, a selector, a monitor) must leave every existing result untouched. A change that alters what a result *means* is not an extension: it needs a new pre-registration before any run ([CONTRIBUTING](https://github.com/Yathindra25KB/driftwatch-lifetime/blob/main/CONTRIBUTING.md)). The extension points below are the places where the first kind can be made safely.

Every extension follows the same four steps: implement the protocol, register it in the factory, add the tests that prove it cannot see what it must not see, and write down the decision.

| To add | Implement | Register in | Must be proven by tests |
|---|---|---|---|
| A **dataset** | `SlotSource` (`slot_table`, `load_slot`, `provenance`) in `data/`, a data card, a preset in `data/presets.py` | `PRESETS` in `data/presets.py` (and the unit routing in `data/sources.py`) | the slicer's constraint and mutation suites run on it; `data verify` passes; rows are unique across slots; timestamps are sorted; the licence permits the use |
| A **selector** | `Selector.select(public, n, rng, scores=None, exclude=None) -> Selection` in `sim/selectors.py` | `make_selector` | it takes an `OpaqueSlot` only; it never returns more handles than `n`; it is deterministic given the seed; the spy and import tests still pass |
| A **retraining policy** | `Policy.should_retrain(slot_index) -> bool` in `sim/policies.py` | `make_policy` | it reads no label; a retrain with no new labels is a no-op |
| A **monitor** | `Monitor.start(...)` and `Monitor.update(view, state) -> Alarm` in `monitors/` | `MONITORS` and `make_monitor` in `monitors/__init__.py` | no label or metric import (`tests/test_sim_sealed.py`); an undecided slot returns `undecided`, never a guess; a no-drift synthetic stream does not alarm in most slots |
| A **detector** | subclass `Detector` in `models/` (fit on a window, score with a fixed threshold) | `_REGISTRY` in `models/__init__.py` (`make_model`) | it refuses to score under another window's id (`WindowMismatch`); fit time is below the budget set in the protocol |
| A **nonconformity score** | `NonconformityScore` in `conformal/nonconformity.py` | the E3 config | bound to one window; calibration rows are never rows the model was fitted on |

## A worked example: a new selector

1. Add `class MarginSelector(_ScoreSelector)` to `sim/selectors.py`, choosing the handles with the smallest gap between the two class probabilities. It receives `scores` from the runner and `public` for the handles; it has no way to ask for a label.
2. Add `if name == "margin": return MarginSelector()` to `make_selector`.
3. Add a test next to `tests/test_sim_selectors.py`: the selection has at most `n` handles, it is the same for the same seed, and it differs from the random selection on a score vector that has structure.
4. Run the import checks of `tests/test_sim_sealed.py`; they fail if the new class imports anything that holds labels.
5. Write the config (`selector: margin`) and register the hypothesis in a pre-registration addendum **before** running it. A selector that is added after seeing results is exploratory and must be labelled so.

## What must not be done

- Do not read a label outside `sim/queue.py`, and do not compute a delay anywhere else.
- Do not fit a scaler, threshold, feature selector or calibration set on anything but the current training window.
- Do not weaken, skip or delete a constraint test or a guardrail to make a change pass; write an ADR and ask.
- Do not add evasion tooling or adversarial-example generation. The repository describes how detectors decay, not how to defeat them ([ethics](../ETHICS.md)).
