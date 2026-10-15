"""Build the E0 tables from stored results (no fits): scripts/make_e0_table.py.

    uv run python scripts/make_e0_table.py                       # newest run per dataset
    uv run python scripts/make_e0_table.py --run bodmas=results/e0/<hash16> ...

Reads ``windows.parquet`` and ``slots.parquet`` of each run and the canary JSON files, and
writes under ``reports/tables/``:

- ``e0_baselines.csv``: one row per (dataset, model, variant, ratio). A-AUT is the mean over
  seeds of the per-seed mean of window AUTs, with the std over windows averaged over seeds
  (sample std) and the spread of the per-seed means. Seeds are not independent replicates:
  the logistic fit ignores the seed, so they differ only in the C3 malware draw and the
  comparator's split. The gap is the random-split F1 minus A-AUT, with the range of
  per-window gaps and a 95% moving-block bootstrap interval over windows (windows averaged
  over seeds first, in time order; block length ceil(nE / stride) windows, which is how far
  a slot's influence reaches; 2,000 draws, seed 0). The windows of one run overlap heavily,
  so there are only a few independent blocks and the interval is descriptive.
- ``e0_per_slot.csv``: F1, FPR, FNR and achieved ratio per evaluated slot, averaged over
  windows and seeds (the decay curve).
- ``e0_canary.csv``: the real-data canary verdicts.
- ``e0_repeats.csv``: evaluated rows whose feature vector also occurs in their training
  window (rolling windows, logistic regression, first seed; counted per window-slot cell, so
  a slot in several windows is counted once per window).

Every number that reaches a report must have a row in docs/CLAIMS.md first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driftwatch.metrics.e0_tables import (  # noqa: E402,F401
    KEYS,
    RunRejected,
    _baseline_rows,
    _block_bootstrap_gap,
    _block_len,
    _newest_runs,
    _sd,
    _time_aware,
    build_tables,
    canary_table,
    check_run,
    repeats_table,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--results", type=Path, default=ROOT / "results" / "e0")
    parser.add_argument("--run", action="append", default=[], metavar="DATASET=DIR")
    parser.add_argument("--canary", nargs="*", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "tables")
    args = parser.parse_args(argv)

    config_dir = ROOT / "configs"
    runs = (
        dict(r.split("=", 1) for r in args.run)
        if args.run
        else _newest_runs(args.results, config_dir)
    )
    runs = {k: Path(v) for k, v in runs.items()}
    for directory in runs.values():
        check_run(directory, config_dir)
    if not runs:
        raise SystemExit(f"no finished run under {args.results}")
    base, per_slot = build_tables(runs)
    args.out.mkdir(parents=True, exist_ok=True)
    repeats_table(runs).to_csv(args.out / "e0_repeats.csv", index=False, lineterminator="\n")
    base.round(4).to_csv(args.out / "e0_baselines.csv", index=False, lineterminator="\n")
    per_slot.round(4).to_csv(args.out / "e0_per_slot.csv", index=False, lineterminator="\n")
    canaries = args.canary or sorted((ROOT / "results" / "canary").glob("*-adr0005.json"))
    if canaries:
        canary_table(canaries).round(4).to_csv(
            args.out / "e0_canary.csv", index=False, lineterminator="\n"
        )
    print(f"runs: { {k: v.name for k, v in runs.items()} }")
    print(f"wrote {args.out / 'e0_baselines.csv'} ({len(base)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
