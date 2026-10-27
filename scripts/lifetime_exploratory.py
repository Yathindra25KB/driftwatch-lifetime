"""Exploratory lifetime reading of the stored E2 per-slot F1 curves (not registered).

    uv run python scripts/lifetime_exploratory.py   # writes e2_lifetime_exploratory.csv

For each dataset and model it reads ``reports/tables/e2_per_slot.csv`` (mean F1 per slot position
over rolling windows and seeds) and reports, for the never-retrained detector and for periodic
retraining at a delay of 0 and a budget of 5%:

* ``first_f1``: the mean F1 at slot position 1;
* ``lifetime_slots``: the first slot position at which the mean F1 is at least ``DROP`` below
  ``first_f1`` (empty when it never is within the horizon);
* ``slope_per_slot``: the least-squares slope of mean F1 on slot position.

The 0.05 drop is the size already used for drop events in E4. Nothing here is a new experiment:
it reads a committed table. F1 at a fixed threshold also moves with the share of malware in a
slot (CLAIMS E-66), so the numbers are descriptive and are not an effect of age alone.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DROP = 0.05
LOG = logging.getLogger("lifetime")


def curve_rows(group: pd.DataFrame, drop: float = DROP) -> dict[str, float | int | None]:
    """First F1, slots until the mean F1 is ``drop`` below it, and the linear slope."""
    g = group.sort_values("slot_position")
    pos = g["slot_position"].to_numpy(dtype=float)
    f1 = g["mean_f1"].to_numpy(dtype=float)
    below = np.flatnonzero(f1 <= f1[0] - drop)
    slope = float(np.polyfit(pos, f1, 1)[0]) if len(pos) > 1 else float("nan")
    return {
        "n_slots": len(pos),
        "first_f1": round(float(f1[0]), 4),
        "last_f1": round(float(f1[-1]), 4),
        "lifetime_slots": int(pos[below[0]]) if len(below) else None,
        "slope_per_slot": round(slope, 4),
    }


def lifetime_table(per_slot: pd.DataFrame, drop: float = DROP) -> pd.DataFrame:
    never = per_slot[per_slot["policy"] == "never"].assign(arm="never")
    best = per_slot[
        (per_slot["policy"] == "periodic")
        & (per_slot["delay"] == 0.0)
        & (per_slot["budget_pct"] == 5.0)
    ].assign(arm="periodic, delay 0, budget 5%")
    rows = []
    for (dataset, model, arm), g in pd.concat([never, best]).groupby(["dataset", "model", "arm"]):
        rows.append({"dataset": dataset, "model": model, "arm": arm, **curve_rows(g, drop)})
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-slot", type=Path, default=ROOT / "reports/tables/e2_per_slot.csv")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "reports/tables/e2_lifetime_exploratory.csv"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    table = lifetime_table(pd.read_csv(args.per_slot))
    table.to_csv(args.out, index=False, lineterminator="\n")
    LOG.info("%s", table.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
