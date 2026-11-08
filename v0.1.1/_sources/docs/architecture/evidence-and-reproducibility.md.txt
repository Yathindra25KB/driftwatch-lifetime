# Evidence and reproducibility

This page follows a number from its birth in a simulated slot to its place in the report, and shows what makes each step repeatable and auditable.

## From configuration to claim

```{mermaid}
flowchart TB
    cfg["one YAML config<br/>configs/*.yaml"]
    reg["pre-registration<br/>(tag prereg-vN)"]
    spec["grid spec<br/>cells = arms x datasets x seeds"]
    run["driftwatch grid / run<br/>fits models, streams slots"]
    res[("results/&lt;config hash&gt;/<br/>predictions.parquet<br/>slots.parquet, run.json<br/>(never committed)")]
    led[("ledger.jsonl<br/>cell events")]
    man["docs/predictions_manifest.csv<br/>SHA-256 of every stored file<br/>(committed)"]
    tab["make_tables, make_e3, make_e4<br/>NO model fits"]
    out["reports/tables/*.csv<br/>reports/figures/*.png<br/>(committed)"]
    cl["docs/CLAIMS.md<br/>number, file, commit"]
    aud["scripts/claims_audit.py"]
    rep["report chapters<br/>README"]

    cfg --> spec
    reg -.->|"fixes hypotheses and<br/>analysis before results"| spec
    spec --> run --> res
    run --> led
    res --> man
    res --> tab
    led --> tab
    tab --> out --> cl --> aud
    cl --> rep
    aud -->|"fails a number without a row"| rep
```

*Figure 9. The evidence chain. Everything left of `results/` needs the datasets and hours of compute; everything right of it is rebuilt from stored predictions in minutes and is checked in CI.*

### What a run records

`sim/results.py` writes one directory per run, named by the first sixteen hexadecimal digits of the **config hash**:

| File | Content |
|---|---|
| `predictions.parquet` | one row per sample scored: true label, probability, decision, with every key (variant, model, seed, window, slot, row id). The raw output every table is rebuilt from |
| `slots.parquet`, `windows.parquet` | confusion counts, F1, FPR, FNR, achieved malware share, C3 status, budget and pool counts; per-window AUT |
| `run.json` | the config, its hash, the code version (git commit, with `-dirty` if uncommitted), the lock-file hash, package versions, seeds, machine, source provenance and `predictions_sha256` |

The **config hash** covers the config values, the code version and the hash of `uv.lock` (`sim/config.py: config_hash`). An evidence run refuses a dirty tree (`--require-clean`), so a stored result always names a commit that exists. For an installed package, which has no `uv.lock`, the hash covers the installed package versions instead (`lock_sha256`).

### Resume without duplicates

The runner works in *units* (one window of one seed of one variant). A finished unit is written to disk and marked done last, so a killed run leaves only whole units; `--resume` restores them and `finalize` merges the units in visit order. A resumed run therefore writes the same tables as an uninterrupted one, and a BODMAS arm killed part-way and resumed gave the same predictions hash (see the S-rows of the [claims ledger](../CLAIMS.md)).

### Determinism, tested

Every random draw is keyed by a seed and an identifier (slot id, window id), never by loop order. A rerun of seed 0 of every E0 variant on the same commit gave identical prediction hashes for every cell [E-11](../CLAIMS.md). The one deliberate exception is the random-split *comparator* of E0, whose split is keyed by a digest of the data manifest; after a data rebuild it is a different draw, which is why the reproduction compares those columns at a looser, stated tolerance than the time-aware columns [E-24](../CLAIMS.md).

## Analysis without fitting

`metrics/` contains no model code. The table builders read each cell's stored predictions, recompute per-slot F1 from labels and decisions, **check it against the slot table**, and then compute AUT, A-AUT, the pre-registered contrasts and their intervals:

- Intervals are two-stage bootstrap intervals over windows and seeds, with a moving-block bootstrap along the window axis because adjacent windows overlap (`metrics/stats.py`). An iid bootstrap was replaced after the first statistics review.
- Contrasts, equivalence margins and the decision rule come from the pre-registration; the code reads them, it does not choose them.
- `scripts/audit_results.py` lists what is on disk under `results/` with code versions and flags, so a table can never silently mix a smoke run with evidence ([results audit](../results_audit.md)).

## `driftwatch reproduce table1`

```{mermaid}
sequenceDiagram
    actor U as User
    participant C as driftwatch reproduce table1
    participant D as Data layer
    participant S as Simulator (E0 config)
    participant T as Table builder
    U->>C: reproduce table1
    C->>D: fetch BODMAS into its own data root
    D-->>C: raw files
    C->>C: compare every raw file hash with the committed manifest
    C->>D: build caches, verify
    C->>S: run configs/e0_bodmas.yaml (clean tree required)
    S-->>C: predictions, run record
    C->>T: rebuild Table 1 from the stored predictions
    T-->>C: rebuilt table
    C->>C: compare with reports/tables/e0_baselines.csv
    C-->>U: MATCH or MISMATCH, JSON report, exit code 0 / 1 / 2 / 3
```

*Figure 10. Full reproduction. The raw-file hash comparison comes first, so a changed upstream file is reported as such and never as a numerical mismatch.*

Exit codes: `0` match, `1` mismatch, `2` cannot run, `3` the dataset host refused the download and the manual path in the data card is needed. Time-aware columns must match to a tolerance of two thousandths and counts exactly.

`driftwatch smoke` is the same pipeline on the synthetic fixture, so it needs no download and no repository: an installed package regenerates the (seeded) fixture and compares with a golden table shipped inside the wheel. Fixture numbers test the code path only and are never evidence.

## Hashing and archives

- `docs/predictions_manifest.csv` lists the SHA-256 and size of every stored prediction, slot table, run record and ledger. `scripts/archive_predictions.py --verify` checks the files on disk against it. The files themselves are archived privately and are not committed [E-69](../CLAIMS.md).
- `data/manifest.json` records the source URL, the Hugging Face revision for LAMDA and the SHA-256 of every raw file for both datasets.
- The package, the lock file and the manifest are the three things a stranger needs: `uv sync --frozen` gives the environment, the manifest gives the data, the config gives the run.
