# Data and slicing

The data layer turns two published feature files into a stream of time slots that the simulator can consume, and it enforces the three time-aware constraints as checks that raise when violated and that no configuration option can switch off. It never touches a binary, a malware sample or a model.

## The pipeline from upstream file to window

```{mermaid}
flowchart TD
    up1["LAMDA<br/>Hugging Face revision"]
    up2["BODMAS<br/>Google Drive folder"]
    dl["driftwatch data download<br/>(resumable; SOURCE.json records URL and hashes)"]
    raw[("data/raw/&lt;dataset&gt;<br/>git-ignored")]
    bld["driftwatch data build<br/>(streams under a memory watchdog)"]
    cache[("per-unit caches<br/>X + metadata, sorted by time")]
    man[("data/manifest.json<br/>hashes, row counts,<br/>the only tracked data file")]
    ver["driftwatch data verify<br/>(hashes, sorted time, unique row ids,<br/>X aligned with metadata)"]
    src["SlotSource<br/>slot_table, load_slot, provenance"]
    slc["slice_windows<br/>(plan, then one slot at a time)"]
    win["Window<br/>TrainWindow + eval_slots()"]

    up1 --> dl
    up2 --> dl
    dl --> raw --> bld --> cache
    bld --> man
    cache --> ver
    man --> ver
    cache --> src --> slc --> win
```

*Figure 2. Data flow. Only `data/manifest.json` (hashes and source URLs) is tracked by git; `data/` is otherwise ignored and `results/` is never committed.*

Properties worth knowing:

- **Builds are resumable and refuse silent changes.** The manifest is saved after every chunk, so an interrupted build continues. If the raw files changed upstream, the build stops: a new dataset version needs a new data root and a new manifest entry, never an overwrite (`data/build.py`).
- **Verification is independent of the builder.** `data verify` recomputes hashes, checks that timestamps are sorted and inside each unit's window, that every `row_id` appears in exactly one unit, and that each row's feature hash can be recomputed from `X` (`data/verify.py`).
- **Memory is a first-class constraint.** The target machine is a laptop with little RAM (see `CLAUDE.md`), so every build and run executes under a watchdog with a configurable cap (`data/memory.py`, `--memory-cap-gb`).
- **Two loaders hide behind one protocol.** LAMDA is a sparse matrix cut into monthly units; BODMAS is a dense matrix cut into ISO weeks. The slicer sees only `SlotSource` (`data/slicer.py`).

## Slots, windows and the three constraints

Time is divided into equal slots by first-seen date. A *window* is an initial training span of `nT` slots followed by evaluation slots, which are streamed one at a time. Rolling the window start by a stride gives the many windows over which A-AUT is averaged. The values of `nT`, the stride and the target ratio are in [PROTOCOL](../PROTOCOL.md) and [ADR-0005](../DECISIONS/ADR-0005-windows-and-size-gate.md).

```{mermaid}
flowchart TB
    subgraph w1["Window 1"]
        direction LR
        t1["train<br/>slots 1..nT"] --> e1a["eval<br/>slot nT+1"] --> e1b["eval<br/>slot nT+2"] --> e1c["..."]
    end
    subgraph w2["Window 2 (start + stride)"]
        direction LR
        t2["train<br/>slots 2..nT+1"] --> e2a["eval<br/>slot nT+2"] --> e2b["eval<br/>slot nT+3"] --> e2c["..."]
    end
    w1 -.->|"rolling start"| w2
```

*Figure 3. Rolling windows. Per-window AUT is the area under the per-slot F1 curve; A-AUT is its mean and standard deviation over windows.*

| Constraint | Meaning | Where it is raised |
|---|---|---|
| **C1** training consistency | every training sample is strictly older than every evaluation sample | `constraints.check_c1`, in the slicer when the window is planned, and again by `SealedSlot.assert_c1` against the real pool (with arrived labels) at every slot |
| **C2** window consistency | an evaluation slot holds malware **and** benign samples, all from that slot's own time span | `constraints.check_c2`, called on the whole raw slot **before** subsampling so a stray row cannot hide by being dropped |
| **C3** realistic ratio | the evaluation slot has a fixed malware share | `constraints.subsample_malware` (seeded, keyed by seed and slot id so the draw does not depend on iteration order) |

None of the checks can be switched off or downgraded to a warning (`ConstraintViolation`). A slot that cannot reach the target ratio is recorded as `below_target` and counted, not silently accepted ([PROTOCOL](../PROTOCOL.md) section 4).

## The leakage canary

`data/canary.py` re-runs a window with a deliberately leaky split and checks that the metric moves toward the random-split level. It validates the *test harness*: if the canary does not move, the time-aware numbers cannot be trusted. It was first tested on seeded drift (not on the signal-free fixture) and then run on real data [E-09, E-22](../CLAIMS.md).

## Why the slicer is mutation-tested

The slicer is the single place where a mistake silently flatters the results. It is therefore tested by deliberately breaking it: `scripts/mutation_check.py` applies a list of code mutations (for example, sorting rows randomly, or letting a training row from the future through) and requires that at least one test fails for each. The matrix is committed in `reports/mutation_matrix.md`. The latest matrix has every breakage caught [W-07](../CLAIMS.md). In Phase 10 a mutant survived because an earlier speed-up had marked its killer test slow, which the harness skips; the test is fast again and another test guards the harness suites (see the Phase 10 row of [PHASES](../PHASES.md)).
