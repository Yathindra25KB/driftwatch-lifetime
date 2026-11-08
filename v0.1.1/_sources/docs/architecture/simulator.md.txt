# Simulator

The simulator replays a deployed detector through the evaluation slots of a window. It is built around one rule: **a label is invisible to everything except the queue's release call and the scoring function.** This page shows the mechanism and how it is verified.

## The sealed boundary

An `EvalSlot` carries features, true labels, timestamps and dataset row ids. The runner never passes it around. It wraps it once in a `SealedSlot` (`sim/queue.py`) and hands out two different views:

```{mermaid}
flowchart TB
    ev["EvalSlot<br/>X, y, ts, row_id"]
    sealed["SealedSlot<br/>(y, ts, row_id private)"]
    pub["OpaqueSlot<br/>X + handle only<br/>(read-only arrays)"]
    sc["slot.score(pred)<br/>metric door"]
    qq["LabelQueue.query<br/>release door"]
    sel["Selector"]
    pol["Policy"]
    mon["Monitor"]
    det["Detector.predict_proba"]
    pool["TrainingPool"]
    met["F1, FPR, FNR<br/>stored predictions"]

    ev --> sealed
    sealed -->|"public()"| pub
    pub --> sel
    pub --> mon
    pub --> det
    pol -. "slot index only" .-> qq
    sel -->|"Selection: handles"| qq
    sealed --> sc --> met
    sealed --> qq
    qq -->|"after delay: labels"| pool
    pool -->|"fit"| det
```

*Figure 4. Who can see what. Solid arrows into `Selector`, `Monitor` and `Detector` carry only features and opaque handles. True labels flow only along the two arrows leaving `SealedSlot` (to the metric door and to the queue) and then out of the queue, after the delay, into the training pool.*

What the type system and the module layout provide (these are design properties that the tests below sample; they are not proofs, and Python does not enforce private attributes, so code that deliberately reached into `SealedSlot` could still read a label):

- `OpaqueSlot` has **no label, no timestamp and no dataset row id**, and no back-reference to its slot. Its arrays are made read-only, because the same arrays back the scoring door and an in-place shuffle would silently pair predictions with the wrong labels.
- A selector returns a `Selection` of *handles* (positions in a seeded, label-independent order). Only `LabelQueue.query` translates handles into rows, through `SealedSlot._take`.
- The queue accepts a query only for the slot just streamed, so a label is not bought for a slot that has not been scored yet.
- `Released` carries the labels that arrive at a slot, with the slot each was queried in. It is the object that moves labels into the training pool.

None of this addresses noise in the datasets' own labels (antivirus-based, with an unpublished scan date for LAMDA, [D-16](../CLAIMS.md); not verified for BODMAS, [D-17](../CLAIMS.md)); that is a limit of the study.

### How it is verified

`tests/test_sim_sealed.py` replaces `y`, `ts` and `row_id` of an `EvalSlot` with spy objects that record the module of every caller and raise on any operation they do not expect. A whole stream is then driven through the real selector, policy, pool and queue, and the test asserts that every recorded read comes from `driftwatch.sim.queue`, and that selectors, policies and the pool performed none. Import-level checks in the same file (they parse the source with `ast`) fail if a selector, policy, pool or monitor imports a type that holds labels, or if any module other than `sim/queue.py` reads slot labels. The spy test has no recorded mutation check of its own ([S-02](../CLAIMS.md)). Three deliberate breakages of the *runner* (arrived labels not reaching the pool, the in-loop C1 assertion removed, comparator rows not filtered from the E0 table) were each caught by the runner regression tests ([S-04](../CLAIMS.md)).

## The delay rule

```{mermaid}
sequenceDiagram
    participant R as Runner
    participant Q as LabelQueue
    participant P as TrainingPool
    Note over R,Q: delay d, window of n evaluation slots
    R->>R: slot s is streamed and scored
    R->>Q: query(s, selection)
    Note right of Q: release_slot(s) = s + 1 + d
    alt s + 1 + d is inside the window
        Q-->>Q: hold the rows until slot s + 1 + d
    else after the end of the window
        Q-->>Q: ignore (counted, never trained on)
    end
    R->>Q: release(s + 1 + d)
    Q-->>P: labels queried at slot s
    Note over R,P: the model fitted at slot s + 1 + d may use them
```

*Figure 5. A label bought in slot `s` is usable from slot `s + 1 + d`; `d = 0` means the next slot. `LabelQueue.release_slot` is the only function that computes this index.*

`release` must be called once per slot, in order from zero; calling it out of order is an error, not a skip. Labels whose release slot falls after the window ends are counted in `n_ignored` and never used.

## One slot of the loop

For each evaluation slot `s` and each detector in the window, `runner._run_sim_window` does exactly this, in this order:

```{mermaid}
flowchart TD
    a["1. release(s)<br/>labels queried at s-1-d arrive"] --> b["2. add to the pool"]
    b --> c["3. assert C1 against the<br/>pool incl. arrived labels"]
    c --> d["4. policy.should_retrain(s)?"]
    d -->|"yes, and new labels since the last fit"| e["5. refit on pool<br/>(window id changes)"]
    d -->|"no, or no new labels"| f
    e --> f["6. predict_proba on the<br/>public slot; fixed threshold"]
    f --> g["7. score_slot against the<br/>true labels (metric door)<br/>and store the predictions"]
    g --> h["8. n_budget = budget_count(slot, pct)<br/>selector.select(public, n_budget)"]
    h --> i["9. queue.query(s, selection)<br/>labels arrive at s+1+d"]
    i --> j["10. store the slot row:<br/>queried, released, pool size, retrained"]
    j --> a
```

*Figure 6. The per-slot loop. Steps one to six use only information that existed before the slot was scored; the slot is scored (step seven) before any label queried in it can exist (step nine).*

Notes that matter when reading the code:

- **Scoring precedes spending.** The slot is scored with the model as it stood *before* this slot's labels were bought, so a label does not inform the slot it came from (the rule in `.claude/rules/sim.md`, checked by the runner tests).
- **A scheduled retrain with nothing new is a no-op.** If the policy fires but no label has arrived since the last fit, the model is not refitted; the event is counted separately (`n_noop_retrains`). This is why, at a delay longer than the retraining period, periodic retraining on BODMAS equals never retraining by construction ([P-12](../CLAIMS.md)).
- **Budget is a percentage of the evaluated slot after C3 subsampling**, because that is the slot the selector sees. The absolute count is always logged next to the percentage (`budget_count`, `n_budget`; [ADR-0007](../DECISIONS/ADR-0007-pool-composition-and-budget.md)).
- **Determinism.** Every random draw is keyed by a seed and a slot id (`selector_rng`, `reserved_rng`), never by iteration order, so a run is repeatable and resumable without duplicate rows.

## Components

| Component | File | Role |
|---|---|---|
| `SealedSlot`, `LabelQueue`, `Released` | `sim/queue.py` | The label door: delay, release, scoring; nothing else touches `y` |
| `Selector` protocol; `RandomSelector`, `UncertaintySelector`, `CredibilitySelector` | `sim/selectors.py` | Choose which handles to buy within the budget; the score-based selectors take model or conformal scores as an extra input and reserve a random slice for calibration |
| `Policy` protocol; `Never`, `Periodic`, `MonitorTriggered`, `Scheduled` | `sim/policies.py` | Decide at slot `s` whether to retrain; they see the slot index and, for the monitor policy, one alarm bit per slot, never a label |
| `TrainingPool` | `sim/pool.py` | The initial window plus labels that have arrived; tracks which rows are new since the last fit |
| `run`, `run_many` | `sim/runner.py` | E0 baseline and the delay/budget simulation for one config |
| E3 window runner | `sim/runner_e3.py` | Adds the conformal layer and monitors on the same stream order |
| `ResultStore` | `sim/results.py` | Per-unit checkpoints, `--resume`, prediction hashes |
| Grids | `sim/grid.py`, `grid_e3.py`, `grid_e4.py`, `ledger.py` | Expand a registered spec into cells, run chunks, record a ledger |
