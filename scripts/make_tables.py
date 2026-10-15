"""E2 tables from stored predictions (RQ2, and RQ1 from the E1 runs). No model fits.

    uv run python scripts/make_tables.py --results results/e2 --e1-root results/e1

Reads each dataset's ledger under ``--results/<dataset>`` and, for every complete cell, its
``predictions.parquet``, ``slots.parquet`` and ``run.json``. Per-slot F1 is recomputed from
the stored labels and decisions and checked against the slot table; AUT, A-AUT, the
pre-registered contrasts (docs/PREREG.md, prereg-v1) and their two-stage bootstrap intervals
come from ``driftwatch.metrics``. The script imports no model code and never reads
``results/e2_smoke``.

Writes into ``--out`` (default reports/tables):

- ``e2_aaut.csv``           A-AUT per arm and seed set, with absolute label counts
- ``e2_contrasts.csv``      the four primary contrasts per dataset, model and seed set
- ``e2_secondary.csv``      delay slopes per budget and budget steps and concavity at d = 0
- ``e2_chow_secondary.csv`` the delay contrasts at Chow's stride (seeds 0-4)
- ``e2_labels_spent.csv``   queries, arrivals, retrains per arm
- ``e2_recovery.csv``       drop events and recovery time per arm (descriptive)
- ``e2_per_slot.csv``       mean F1 per slot position, for the curves
- ``e2_ledger.csv``         planned, complete and failed cells with their reasons
- ``e2_rq1.csv``            the per-slot matched and the E0 window-level gap (from E1)

Every number that reaches a report must have a row in docs/CLAIMS.md first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driftwatch.metrics import grid_tables as gt  # noqa: E402
from driftwatch.metrics import stats  # noqa: E402

DATASETS = ("lamda", "bodmas")


def _write(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.6f", lineterminator="\n")


def build(
    results: Path,
    e1_root: Path | None,
    datasets: tuple[str, ...] = DATASETS,
    n_boot: int = stats.N_BOOT,
) -> dict[str, pd.DataFrame]:
    parts: dict[str, list[pd.DataFrame]] = {
        k: []
        for k in (
            "aaut", "contrasts", "secondary", "chow", "labels", "recovery", "per_slot", "ledger",
            "rq1",
        )
    }  # fmt: skip
    for ds in datasets:
        root = results / ds
        if not (root / "ledger.jsonl").exists() and not list(root.glob("ledger*.jsonl")):
            continue
        col = gt.collect(root, ds)
        parts["ledger"].append(gt.ledger_table(col))
        if not col.arms:
            continue
        parts["aaut"].append(gt.aaut_table(col))
        parts["contrasts"].append(gt.contrasts_table(col, n_boot=n_boot))
        parts["secondary"].append(gt.secondary_table(col, n_boot=n_boot))
        parts["chow"].append(gt.chow_table(col, n_boot=n_boot))
        parts["labels"].append(gt.labels_table(col))
        parts["recovery"].append(gt.recovery_table(col))
        parts["per_slot"].append(gt.per_slot_table(col))
    if e1_root is not None:
        for ds in datasets:
            try:
                run_dir = gt.discover_e1(e1_root, ds)
            except gt.GridDataError:
                continue
            parts["rq1"].append(gt.rq1_table(run_dir, ds, n_boot=n_boot))
    out = {k: (pd.concat(v, ignore_index=True) if v else pd.DataFrame()) for k, v in parts.items()}
    c = out["contrasts"]
    if not c.empty:  # one Holm family per seed set across datasets and models
        c["wilcoxon_p_holm"] = float("nan")
        for _, idx in c.groupby("seed_set").groups.items():
            c.loc[idx, "wilcoxon_p_holm"] = stats.holm(c.loc[idx, "wilcoxon_p"].tolist())
    return out


FILES = {
    "aaut": "e2_aaut.csv",
    "contrasts": "e2_contrasts.csv",
    "secondary": "e2_secondary.csv",
    "chow": "e2_chow_secondary.csv",
    "labels": "e2_labels_spent.csv",
    "recovery": "e2_recovery.csv",
    "per_slot": "e2_per_slot.csv",
    "ledger": "e2_ledger.csv",
    "rq1": "e2_rq1.csv",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", type=Path, default=ROOT / "results" / "e2")
    ap.add_argument("--e1-root", type=Path, default=ROOT / "results" / "e1")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "tables")
    ap.add_argument("--datasets", nargs="+", default=list(DATASETS), choices=DATASETS)
    ap.add_argument("--n-boot", type=int, default=stats.N_BOOT)
    args = ap.parse_args(argv)
    e1 = args.e1_root if args.e1_root.exists() else None
    tables = build(args.results, e1, tuple(args.datasets), args.n_boot)
    for key, name in FILES.items():
        df = tables[key]
        if df.empty:
            print(f"{name}: no rows (nothing complete yet)")
            continue
        _write(df, args.out / name)
        print(f"{name}: {len(df)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
