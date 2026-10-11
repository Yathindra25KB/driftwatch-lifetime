"""Compare a rerun with an original E0 run: scripts/compare_runs.py ORIGINAL RERUN.

The rerun may cover a subset of the original's seeds (the same config with fewer seeds).
For every cell of the rerun this checks

1. the per-cell prediction hash equals the original's (time-aware predictions are
   byte-identical), and
2. the window rows agree on AUT and on every comparator column (the random-split F1, its
   confusion counts and the pooled draw), which the prediction hash does not cover.

Exit code 0 when everything matches, 1 otherwise. Timing columns are ignored.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

KEY = ["variant", "model", "ratio", "seed", "window_id"]
COMPARE = [
    "aut",
    "f1_first",
    "f1_last",
    "f1_random_split",
    "random_tp",
    "random_fp",
    "random_fn",
    "random_n_test",
    "random_n_train_malware",
    "f1_random_pooled",
    "random_pooled_n_test",
]


def compare(original: Path, rerun: Path) -> dict[str, object]:
    a = json.loads((original / "run.json").read_text(encoding="utf-8"))
    b = json.loads((rerun / "run.json").read_text(encoding="utf-8"))
    cells_a, cells_b = a["cell_predictions_sha256"], b["cell_predictions_sha256"]
    missing = sorted(set(cells_b) - set(cells_a))
    mismatched = sorted(k for k in cells_b if k in cells_a and cells_a[k] != cells_b[k])
    wa = pd.read_parquet(original / "windows.parquet").set_index(KEY)
    wb = pd.read_parquet(rerun / "windows.parquet").set_index(KEY)
    absent = [k for k in wb.index if k not in wa.index]
    shared = wb.index.intersection(wa.index)
    differing: list[str] = []
    for col in COMPARE:
        x, y = wa.loc[shared, col], wb.loc[shared, col]
        same = (x == y) | (x.isna() & y.isna())
        if not same.all():
            differing.append(col)
    return {
        "cells_compared": len(cells_b),
        "cells_missing_in_original": missing,
        "cells_with_different_hash": mismatched,
        "window_rows_compared": int(len(shared)),
        "window_rows_absent_in_original": len(absent),
        "columns_that_differ": differing,
        "identical": not (missing or mismatched or absent or differing) and len(cells_b) > 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("original", type=Path)
    parser.add_argument("rerun", type=Path)
    args = parser.parse_args(argv)
    result = compare(args.original, args.rerun)
    print(json.dumps(result, indent=2))
    return 0 if result["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
