# Chapter 6: Method (draft)

> Status: draft written by Claude Code in Phase 5 for the researcher to rewrite and defend. Sections 6.1 to 6.5 describe code that exists and is tested at the commit named in docs/PHASES.md; sections 6.6 and 6.7 describe things that do not exist yet and are marked so. No result number appears here. Protocol constants (slot length, delay, budget, period) are quoted from docs/PROTOCOL.md; they are settings, not measurements. Anything not yet checked against the source is marked [verify].

## 6.1 What the simulator is for

The experiments need one instrument that can answer a single question many times: *if a detector is trained on a window of data and then used, slot by slot, on later data, how well does it do when true labels arrive late, only a few can be bought per slot, and retraining is allowed only on labels that have arrived?* The simulator streams one rolling window under a label delay, a per-slot analyst budget, a selector and a retraining policy. Its main design commitment is that the delay lives in exactly one place, so that no other part of the code can quietly use a label early.

Terms used in this chapter.

- **Slot**: a fixed calendar interval. One calendar month for LAMDA, two weeks for BODMAS (ADR-0004, PROTOCOL.md section 2).
- **Window**: `nT` consecutive training slots followed by `nE` evaluation slots (ADR-0005). The model is trained on the first part and used on the second.
- **C1, C2, C3**: the three TESSERACT constraints, implemented as assertions that raise (hard rule 2). C1: every training sample is older than every evaluation sample. C2: each evaluation slot holds malware and benign samples from its own time window. C3: each evaluation slot is brought to the target malware ratio by seeded subsampling of malware only (pendlebury2019tesseract).
- **Delay `d`**: the number of whole slots a requested label takes to arrive, beyond the next slot (section 6.3).
- **Budget**: the number of labels the analyst may request in one slot, set as a percentage of that slot.
- **AUT** and **A-AUT**: area under the F1-versus-time curve within one window, and its mean over windows (ADR-0006).

## 6.2 Data flow

```
 slicer                              one run = one window x seed x model x policy x delay x budget
 train: TrainWindow (raw rows, labels allowed here)
 eval:  EvalSlot 0..nE-1  --wrapped at once-->  SealedSlot  (held only by the queue and the metric door)
                                                   |
  for s = 0 .. nE-1:                                |
  +------------------------------------------------------------------------------------------+
  | 1 RELEASE   queue.release(s)    labels queried at s-1-d arrive, pool.add(...)            |
  | 2 RETRAIN?  policy(s)           fires only if new labels arrived since the last fit      |
  |             fit(pool = initial window + arrived labels)                                  |
  | 3 SCORE     predict on the label-free public view; metrics read the true labels          |
  | 4 SELECT    selector(public view, n)          sees features and slot-local handles only  |
  | 5 QUERY     queue.query(s, handles)          release slot = s + 1 + d, ignored if >= nE  |
  +------------------------------------------------------------------------------------------+
```

The order inside a slot is the stream order: a slot is scored (step 3) before any label queried in that slot exists (step 5), and a label queried in slot `s` cannot be released earlier than slot `s + 1`.

## 6.3 The label queue and the delay rule

`sim/queue.py` is the only module that knows `d`. A label requested while evaluation slot `t` is being streamed becomes usable from slot `t + 1 + d`; `d = 0` therefore means "available at the next slot". Queue timeline for `d = 1`, retraining every three slots:

```
 slot index   0    1    2    3    4    5
 query        Q0   Q1   Q2   Q3   Q4   Q5
 usable            -    Q0   Q1   Q2   Q3        usable from t + 1 + d = t + 2
 retrain                     R@3
                                                 R@3 sees Q0 and Q1; Q2 arrives at slot 4
                                                 Q4 and Q5 would arrive at slots 6 and 7: ignored
```

Rules, all enforced by tests (`tests/test_queue_delay.py`, including property-based tests for `d` in {0, 1, 2, 3}):

1. A queried label is released exactly once, at slot `t + 1 + d`, never earlier.
2. A label whose release slot is at or after the last slot of the window has no slot left to inform. It is **ignored and counted** (`n_ignored_after_end`). A window is an independent run; nothing carries into the next window.
3. Nothing is lost or invented: queued labels equal released plus ignored.
4. A selection is tagged with the slot it was made for; the queue refuses handles from another slot.

The held-back labels are *sealed*. `SealedSlot` wraps the evaluation slot so that the true labels leave it by two doors only: the queue (which hands them back after the delay) and the scoring call used by the metric code. Selectors and policies receive an `OpaqueSlot` (features plus slot-local integer handles in a seeded, label-independent order) and a slot index; they cannot import the types that hold labels. A spy test replaces the label arrays with objects that record who reads them and fails on any use but indexing; every recorded read comes from the queue module, and selectors and policies read nothing (`tests/test_sim_sealed.py`, and the same check at the runner level in `tests/test_runner_sim.py`).

## 6.4 Budget and selection

The budget for a slot is a percentage of the **evaluated slot after C3 subsampling**, because that is the slot the selector can see. The number of labels is `floor(pct / 100 * n + 1/2)`, capped at the slot size; both the percentage and the absolute count are stored with every slot row. The settings are 0.5, 1, 2 and 5 percent (PROTOCOL.md section 2).

Selection is behind a small interface, `select(public_slot, n, rng, scores=None)`. Phase 5 has one selector, uniform random selection without replacement. Its random generator depends on the seed and the slot identity only, so a small budget selects a subset of the rows a larger budget selects: comparisons across budgets are paired. Uncertainty and credibility selectors (Phase 8) use the same call through the optional `scores` argument; they do not exist yet. A reserved random calibration slice (a share of the budget, default 20 percent) is a configuration parameter that is stored and logged but has no effect until the conformal layer exists. [Phase 8 not yet implemented.]

## 6.5 Retraining and the training pool

A retraining policy decides *when*. Phase 5 has two: **never**, and **periodic**, which fires before scoring evaluation slots 3, 6, 9, ... counted from the first evaluation slot of the window (decision D7, ADR-0007). A scheduled event with no new label since the last fit is logged as a no-op and does not refit. A monitor-triggered policy exists only as an interface that raises `NotImplementedError` until Phase 9.

The pool a retraining fits on is **the initial training window plus every label that has arrived**, each row weighted once, never truncated (ADR-0007; chosen by the researcher before any grid run, and not by looking at AUT). Three consequences are stated up front. First, arrived rows are C3-subsampled evaluation rows (close to the target malware ratio), while the initial rows are raw, so the pool mixes two class priors; this is a property of the design, not a defect to be tuned away. Second, with weight 1 and a budget of at most 5 percent per slot, arrived labels are a small share of the pool; a diagnostic that counts how many decisions change after retraining (not AUT) is reported next to the design for that reason (`scripts/label_influence.py`; numbers in docs/CLAIMS.md E-13 to E-15). It counts changed decisions only, has no noise-floor comparison, and says nothing yet about detection quality. Third, scalers and any thresholds are fitted on the current pool only (hard rule 5); the threshold is fixed at 0.5 (ADR-0006).

C1 is re-asserted for every scored slot against the whole pool, including released rows.

## 6.6 Runs, determinism and resumption

One YAML file describes one run; the run is identified by a hash of the configuration, the code version and the lock file (hard rule 6). Per-row predictions are stored, so every table and figure is regenerated from stored predictions.

- **Determinism.** The same configuration and seed give identical per-slot predictions (`tests/test_runner_sim.py`). C3 draws, public shuffles and selector draws are each seeded from the seed and the slot identity.
- **Resumption.** The unit of work is one window of one seed of one variant. A finished unit is checkpointed and marked done last; a run that is killed can be resumed (`--resume`), skips finished units, and writes tables identical to an uninterrupted run with no duplicate rows. Resuming needs a clean working tree, so the same hash cannot mix code states.
- **Initial-model cache.** The initial model for a (dataset, training window, model, seed) is fitted once and shared across runs in the same process; the seed is part of the key only for models that use it.
- **Parallelism** is across runs, one thread per run, never inside a run. On the 8 GB development machine this is bounded by memory, not by cores: the approved memory cap is per process, so two concurrent BODMAS runs exceed it (section 6.7).

## 6.7 Limits stated before results

- **Short windows on BODMAS.** With six evaluation slots and a retraining period of three, a window has one useful retraining event (before slot 3). At `d = 3` no label queried in slots 0 to 2 has arrived by then, so periodic retraining equals never retraining on BODMAS at `d = 3` (shown in `tests/test_runner_sim.py`). Delay contrasts on BODMAS are therefore limited by construction (ADR-0005 window geometry), and results must be read with that in mind. [verify against the final ADR-0007 wording]
- **Comparator.** E0's random-split comparator was not matched per slot. E1 uses a per-slot matched comparator (section 6.8) and E0 numbers are not reused for RQ1 attribution.
- **Memory.** Runs are limited to the researcher-approved cap; parallel runs share it.
- **Not implemented yet:** the conformal layer, drift monitors, uncertainty and credibility selectors, monitor-triggered retraining (Phases 8 and 9).

## 6.8 The E1 comparator

E1 asks how much of a detector's apparent quality is an artefact of a random split. Both series use the same windows, the same models and the same C3 target ratio.

- **Time-aware series**: the detector trained on the initial window, never retrained, scored on each evaluation slot (C1 holds).
- **Random-split series**: a detector trained on a random draw from the window's pooled raw rows, with the same number of malware and benign rows as the time-aware training window, scored on the held-out rows of each evaluation slot; malware in each held-out slot is subsampled to the target ratio with the same C3 check. It violates C1 by design.

The figure shows F1 per evaluation slot for both series, from stored predictions only; the script fits nothing and imports no model code (`scripts/make_e1_figure.py`, `tests/test_make_e1_figure.py`). The random-split series has fewer rows per slot than the time-aware series (it scores only the rows it did not train on), so its per-slot values are noisier.

## 6.9 Threats to validity of the instrument

- The synthetic regression fixture reproduces an ordering (never retraining is worst, more labels help, longer delay hurts). It is a test of mechanics, not evidence; its numbers are never reported.
- The pool mixes C3-subsampled and raw rows (section 6.5).
- Random selection draws about the base rate of malware, so at small budgets few malware labels arrive; selection that targets uncertain or drifting samples is a Phase 8 question.
- Seeds are not independent replicates for the logistic model (it ignores the seed); they differ only in the C3 draw, the selector draw and the comparator split. [verify before any seed-based interval is written]
