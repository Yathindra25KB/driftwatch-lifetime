# Conformal layer and monitors

Two optional layers sit on top of the simulator. The **conformal layer** turns a detector score into a p-value that says how unusual a sample is for a class; selectors use it to choose which samples to label. The **monitors** look at the stream of unlabelled features and decide when to raise an alarm; a retraining policy can act on that alarm. Both are designed so that they cannot read a held-back label.

## Conformal p-values and credibility

For each class `c`, the calibration set keeps the nonconformity scores of labelled calibration samples of that class. A new sample gets the Mondrian (class-conditional) p-value

```text
p_c(x) = (1 + #{ calibration samples i of class c with s_i >= s_c(x) }) / (n_c + 1)
```

and its **credibility** is the p-value of its predicted class. A low credibility means the sample looks unlike what the model knows for that class. A class with no calibration sample gets `p = 1`: nothing says the sample is unusual (`conformal/mondrian.py`).

The validity of a p-value needs the calibration samples to be a fair draw from the current data. Two rules protect that, and both are code, not convention:

1. **Calibration labels come only from a reserved random slice** of each slot's budget (`sim/selectors.py: select_with_reserved_slice`, `reserved_rng`). A sample chosen by uncertainty or credibility is tagged `selected` and is never calibration data, because a selected sample is by construction not exchangeable with the rest.
2. **Calibration rows are never rows the scoring model was fitted on.** The initial detector is fitted on the window minus a time-ordered hold-out, which becomes the first calibration set ([ADR-0009](../DECISIONS/ADR-0009-calibration-rows-are-not-training-rows.md); `conformal/recalibrate.py: time_ordered_holdout`). `CalibrationContamination` is raised if a sample that a selector chose enters the calibration buffer.

Nonconformity scores are pluggable (`conformal/nonconformity.py`): `ProbabilityScore` uses one minus the model's probability of the class, `CentroidScore` the distance to a class centroid. Scores are bound to the window they were computed under and refuse another (`WindowMismatch`).

```{mermaid}
flowchart LR
    pub["OpaqueSlot (features)"] --> det["Detector"]
    det -->|"score"| nc["NonconformityScore<br/>s_c(x)"]
    cal[("CalibrationBuffer<br/>arrived reserved-slice labels<br/>+ time-ordered hold-out")] --> p["Mondrian p-values<br/>per class"]
    nc --> p
    p --> cred["credibility =<br/>p of predicted class"]
    cred --> sel["CredibilitySelector<br/>(lowest first)"]
    det -->|"probability"| uns["UncertaintySelector<br/>(closest to 0.5)"]
    sel --> q["Selection: handles"]
    uns --> q
    rnd["RandomSelector"] --> q
    res["reserved random slice"] --> cal
```

*Figure 7. How a selector gets its signal. Calibration data flows in only from the reserved random slice, after the label delay. Random, uncertainty and credibility selection spend the same absolute budget.*

## Drift monitors behind one interface

A monitor answers one question per evaluation slot: *does this slot look unlike the reference the model in force knows?* All four implement the same protocol and return the same record.

```python
class Monitor(Protocol):
    name: str
    alpha: float

    def start(self, state, train_X, train_y, ref_full_X) -> None: ...
    def update(self, view: SlotView, state: MonitorState) -> Alarm: ...
```

| Monitor | Compares | File |
|---|---|---|
| KS on top features | a two-sample Kolmogorov–Smirnov test per feature on the `k` features with the largest standardised class-mean difference in the initial training rows, Holm-adjusted over the `k` tests | `monitors/ks.py` |
| MMD | a maximum-mean-discrepancy test on a low-dimensional projection of the features and the model score (the detectors have no learned embedding, so this is a stated substitute, [ADR-0010](../DECISIONS/ADR-0010-monitor-inputs-and-reference.md)) | `monitors/mmd.py` |
| Domain classifier | how well a cross-validated logistic regression separates reference rows from current rows; its p-value comes from a permutation null computed once per window (a stated approximation, ADR-0010) | `monitors/domain_clf.py` |
| p-uniformity | a two-sample KS test between the slot's conformal scores and the calibration scores, per predicted class, so a finite calibration set is not treated as exact; it is label-free | `monitors/p_uniformity.py` |

An `Alarm` records the statistic, its p-value, the threshold, the reference slot and the two sample sizes; a monitor that cannot decide (too few rows) returns an undecided alarm instead of guessing.

What a monitor may see is fixed by the type `SlotView` (public features, model scores through a callable, and the features of calibration rows that have arrived) and by import rules: `tests/test_sim_sealed.py` fails if a monitor imports a label holder or metric code. **Monitors never see true labels**; scoring a monitor against true drops in F1 happens afterwards, from stored predictions (`metrics/monitor_scores.py`).

### The reference rule

After a retrain, the reference becomes a seeded sample of the newest evaluation slot whose labelled rows were in the pool at that fit (rule R of ADR-0010). Under a delay `d`, a refit before slot `s` can use only labels queried up to slot `s - 1 - d`, so the reference lags by exactly the rows the model has learned from. An arm that never refits keeps the initial reference.

### From alarm to retraining

```{mermaid}
sequenceDiagram
    participant R as Runner
    participant M as Monitor
    participant P as MonitorTriggered policy
    R->>R: score slot s
    R->>M: update(view of slot s)
    M-->>R: Alarm(fired, p_value, ...)
    R->>P: notify(fired)
    Note over P: pending for slot s+1 only
    R->>P: should_retrain(s+1)
    P-->>R: true if pending and gap since last fit is large enough
    R->>R: refit only if labels arrived since the last fit
    R->>P: record(s+1, refitted)
    Note over P: the alarm is consumed, never carried forward
```

*Figure 8. A monitor decides after seeing slot `s`; the retraining it triggers happens before slot `s + 1` is scored. Evidence for the E4 contrasts is in the [claims ledger](../CLAIMS.md) (E-59 to E-63), including that no monitor beat periodic retraining and that the monitors alarmed in most slots.*

Two controls make the E4 comparison fair, and both are structural: a *matched* arm copies a monitor run's refit counts and label spend, and a *scheduled* arm refits as often as the monitor but at evenly spaced slots (`sim/policies.py: Scheduled`, `even_schedule`). The thresholds were fixed before the run and were not tuned (the no-tuning rule in `CLAUDE.md`).
