# Running the E2 grid: cells, chunks, the ledger, Kaggle and Colab

The grid (E2) is the pre-registered delay x budget grid of `docs/PREREG.md` (tag `prereg-v1`). It is run by `driftwatch grid`, one cell at a time.

## What a cell is

A grid file (`configs/e2_lamda.yaml`, `configs/e2_bodmas.yaml`) is a run config plus a `grid:` block. Each dataset expands into 27 runs:

| Role | Count | What |
|---|---|---|
| `grid` | 16 | periodic(3), every delay {0,1,2,3} x budget {0.5,1,2,5}%, seeds 0-4 |
| `headline` | 6 | d in {0,3} x B in {1,5}%, plus B = 0.5% and 2% at d = 0, seeds 5-9 (10 seeds in all with the grid cells) |
| `chow` | 4 | the four delay-contrast cells at Chow's stride, seeds 0-4 |
| `never` | 1 | never retrain, seeds 0-9, both window variants (it does not depend on delay or budget) |

Each cell is an ordinary `RunConfig` with scalar delay and budget; its config hash covers the config, the code version and `uv.lock`. A cell's results live in one directory: `<out>/<cell>/<hash16>/` with `predictions.parquet`, `slots.parquet`, `windows.parquet` and `run.json`.

## Commands

```bash
uv run driftwatch grid configs/e2_bodmas.yaml --smoke        # 1 seed, 1 window per cell shape; prints timing only
uv run driftwatch grid configs/e2_bodmas.yaml --status       # planned, complete, failed (all ledgers under --out)
uv run driftwatch grid configs/e2_bodmas.yaml                # everything, resumable
uv run driftwatch grid configs/e2_lamda.yaml --chunk 2/6     # the 2nd of 6 cost-balanced chunks
uv run driftwatch grid configs/e2_lamda.yaml --retry-failed "memory cap hit while another job ran"
```

`--smoke` writes to `results/e2_smoke/<dataset>`, never counts toward the real grid, and prints seconds per window x seed x model unit by cell shape, the extrapolation to every planned cell, and a chunk plan. It prints no AUT.

Defaults: data under `data/`, results under the spec's `output` (`results/e2/<dataset>`), memory cap 1.5 GiB, tree must be clean (tracked files unchanged and no untracked file under `src/`, `configs/`, `scripts/`, `tests/`).

## The ledger

`<out>/ledger.jsonl` (or `ledger-chunk-i-of-n.jsonl` when `--chunk` is used) is append-only JSON lines: `started`, `complete` (directory, wall time, longest fit, peak memory, predictions hash), `failed` (reason, traceback, whether it was an infrastructure failure), `retry`, `invalidated`, `flag`. The last event of a cell is its state. Rules:

- A completed cell is skipped on a rerun. A failed cell is kept as failed and is not retried unless `--retry-failed REASON` is given; the retry is recorded with its reason. No cell is rerun because of how its result looks.
- One grid, one commit. The code version is read once when the grid starts and pinned; if HEAD or the tree moves, the next cell is refused. A ledger that holds cells from another commit is refused unless `--allow-code-change REASON` is given, which is recorded as a flag.
- A bug found after the tag is fixed in a new commit; the affected cells get an `invalidated` event with the reason and exactly those are rerun.
- A fit over 60 s stops the chunk and is flagged; the shrink order of PREREG (delay 2, budget 0.5%, windows, seeds on non-headline cells) is then applied by the researcher.

## Running the full grid on this laptop

Chunks run one at a time (`--workers 1` is the only mode: two concurrent BODMAS runs crossed the 1.5 GiB cap in Phase 5). Because `code_version` is part of every hash, run from a frozen worktree so that work on the main tree cannot change the commit mid-grid:

```bash
git worktree add --detach ../DriftWatch-grid prereg-v1     # or the commit the grid is pinned to
cd ../DriftWatch-grid && uv sync --frozen
uv run driftwatch grid configs/e2_bodmas.yaml --root ../DriftWatch/data --out ../DriftWatch/results/e2/bodmas
uv run driftwatch grid configs/e2_lamda.yaml  --root ../DriftWatch/data --out ../DriftWatch/results/e2/lamda
```

## Kaggle or Colab (documented, not used unless the researcher decides)

The same CLI runs on a notebook machine. Steps:

1. Check out the same commit as the ledger's `code_version` (`git clone` then `git checkout <commit>`), `uv sync --frozen`.
2. Fetch the data through the manifest: `driftwatch data download lamda` and `driftwatch data build lamda` (BODMAS: `download bodmas`, or `--manual` with the Google Drive file named in `data/manifest.json`), then `driftwatch data verify`. Kaggle gives about 13 GB RAM and Colab about 12 GB; keep the 1.5 GiB cap anyway so that results are comparable.
3. Run chunks: `driftwatch grid configs/e2_lamda.yaml --chunk i/n --out results/e2/lamda` with a fixed `n` for all chunks. Each chunk writes its own ledger file, so chunks run on different machines never write the same file.
4. Download `results/e2/<dataset>/` (cell directories and ledgers) and merge them into the local `results/e2/<dataset>/`. `driftwatch grid <spec> --status` reads every `ledger*.jsonl` there.
5. Cross-platform drift: floating point and thread scheduling can differ between machines. Every `run.json` records the platform; a chunk run elsewhere is reported as such and any numerical difference to a local rerun is reported, never corrected. If a platform difference matters for a claim, rerun that cell locally.

## Tables and figures

```bash
uv run python scripts/make_tables.py  --results results/e2 --e1-root results/e1
uv run python scripts/make_figures.py
```

Both read stored results only (no model fits). Two runs produce byte-identical outputs.

## E3 (selection under delay)

`configs/e3_bodmas.yaml` and `configs/e3_lamda.yaml` are E3 grid specs (a `grid:` block with `selectors`). They use the same driver, ledger, chunks, smoke mode and resume as E2; each dataset expands into 28 cells (12 main at seeds 0 to 4, the same 12 at seeds 5 to 9, 3 reserved-slice ablation cells, 1 centroid-score cell). The registration is `docs/prereg/addendum-v2.md` (tag `prereg-v2`); run from a frozen worktree at that tag:

```bash
git worktree add --detach ../DriftWatch-e3 prereg-v2
cd ../DriftWatch-e3
uv run driftwatch grid configs/e3_bodmas.yaml --smoke                       # timing only
uv run driftwatch grid configs/e3_bodmas.yaml --out ../DriftWatch/results/e3/bodmas
uv run python scripts/make_e3.py --results results/e3                        # tables and figure
```

LAMDA E3 runs seeds 0 to 4 first; the seeds 5 to 9 cells are run only if the researcher's hours allow (drop the `extra_seeds` key to skip them). E3 numbers are comparable only within E3 (ADR-0009).
