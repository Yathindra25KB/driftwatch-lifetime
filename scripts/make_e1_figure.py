"""E1 (RQ1): F1 versus evaluation slot, random split vs time-aware, from stored predictions.

    uv run python scripts/make_e1_figure.py --run lamda=results/e1/<hash16> \\
        --run bodmas=results/e1/<hash16>

Reads only ``predictions.parquet`` of E1 runs (config: policy never, per-slot random-split
comparator on). F1 per (seed, window, slot) is computed from the stored labels and decisions;
nothing is fitted and no model code is imported. Writes ``reports/figures/e1_random_vs_time.png``
and ``reports/tables/e1_per_slot.csv`` and ``e1_summary.csv``.

Definitions (descriptive; windows overlap, so the spread is a range, not a confidence interval):

- slot position: the evaluation slot's place inside its window (1..nE);
- per window, F1 is averaged over seeds first; the plotted line is the mean over windows and
  the band is the min-max range over windows;
- AUT of a series is the area under that series' per-slot F1 within a window (metrics.aut),
  averaged over seeds, then over windows. Both series use the same windows, seeds and C3 ratio.

The random-split series trains on a random draw of the window's pooled raw rows (same size and
class counts as the time-aware training window) and is scored on the held-out rows of each
evaluation slot, malware subsampled to the same target ratio per slot. It violates C1 by design.
Every number that reaches a report must have a row in docs/CLAIMS.md first.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from driftwatch.metrics.aut import aut

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = ["series", "model", "seed", "window_id", "slot_id", "y_true", "pred"]
SURFACE, INK, MUTED = "#ffffff", "#1b1f24", "#5f6b76"
SERIES_STYLE = {
    "time_aware": {"color": "#c2410c", "label": "time-aware (C1 holds)"},
    "random_split": {"color": "#1d4ed8", "label": "random split (C1 violated)"},
}
SLOT_ORDER = ("time_aware", "random_split")


def _f1(tp: pd.Series, fp: pd.Series, fn: pd.Series) -> pd.Series:
    denom = 2 * tp + fp + fn
    return (2 * tp / denom.where(denom > 0)).fillna(0.0)


def _load(run_dir: Path) -> pd.DataFrame:
    p = pd.read_parquet(run_dir / "predictions.parquet", columns=COLUMNS)
    if not (p["series"] == "random_split").any():
        raise ValueError(
            f"{run_dir}: no random_split series; run a config with per_slot_random_split: true"
        )
    return p


def slot_f1(
    preds: pd.DataFrame, model: str, series: str, *, seed: int, window_id: str, slot_id: str
) -> float:
    c = preds[
        (preds["model"] == model)
        & (preds["series"] == series)
        & (preds["seed"] == seed)
        & (preds["window_id"] == window_id)
        & (preds["slot_id"] == slot_id)
    ]
    y, p = c["y_true"].to_numpy(), c["pred"].to_numpy()
    tp = int(((y == 1) & (p == 1)).sum())
    fp = int(((y == 0) & (p == 1)).sum())
    fn = int(((y == 1) & (p == 0)).sum())
    return 0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn)


def _cell_f1(preds: pd.DataFrame) -> pd.DataFrame:
    """F1 per (series, model, seed, window, slot) from labels and decisions."""
    flag = preds.assign(
        tp=((preds["y_true"] == 1) & (preds["pred"] == 1)).astype("int64"),
        fp=((preds["y_true"] == 0) & (preds["pred"] == 1)).astype("int64"),
        fn=((preds["y_true"] == 1) & (preds["pred"] == 0)).astype("int64"),
    )
    keys = ["series", "model", "seed", "window_id", "slot_id"]
    g = flag.groupby(keys, sort=False)[["tp", "fp", "fn"]].sum().reset_index()
    g["f1"] = _f1(g["tp"], g["fp"], g["fn"])
    return g


def _positions(cells: pd.DataFrame, preds: pd.DataFrame) -> pd.DataFrame:
    """Slot position inside the window, in the order slots were written (time order)."""
    order = (
        preds[preds["series"] == "time_aware"][["window_id", "slot_id"]]
        .drop_duplicates()
        .assign(slot_position=lambda d: d.groupby("window_id").cumcount() + 1)
    )
    return cells.merge(order, on=["window_id", "slot_id"], how="left", validate="m:1")


def window_series(run_dir: Path) -> pd.DataFrame:
    """Per (series, model, window, slot position): F1 averaged over seeds."""
    preds = _load(Path(run_dir))
    cells = _positions(_cell_f1(preds), preds)
    return (
        cells.groupby(["series", "model", "window_id", "slot_position"], as_index=False)["f1"]
        .mean()
        .rename(columns={"f1": "f1_seed_mean"})
    )


def per_slot_table(runs: dict[str, Path]) -> pd.DataFrame:
    frames = []
    for dataset, run_dir in runs.items():
        w = window_series(Path(run_dir))
        g = w.groupby(["series", "model", "slot_position"])["f1_seed_mean"]
        t = g.agg(mean_f1="mean", min_f1="min", max_f1="max", n_windows="count").reset_index()
        t.insert(0, "dataset", dataset)
        frames.append(t)
    return pd.concat(frames, ignore_index=True)


def summary_table(runs: dict[str, Path]) -> pd.DataFrame:
    rows = []
    for dataset, run_dir in runs.items():
        w = window_series(Path(run_dir))
        for model, m in w.groupby("model"):
            auts: dict[str, np.ndarray] = {}
            for series, s in m.groupby("series"):
                per_window = [
                    aut(g.sort_values("slot_position")["f1_seed_mean"].tolist())
                    for _, g in s.groupby("window_id")
                    if len(g) >= 2
                ]
                auts[str(series)] = np.asarray(per_window)
            ta, rs = auts.get("time_aware", np.array([])), auts.get("random_split", np.array([]))
            rows.append(
                {
                    "dataset": dataset,
                    "model": model,
                    "n_windows": int(len(ta)),
                    "n_slots": int(m["slot_position"].max()),
                    "aut_time_aware": float(ta.mean()) if len(ta) else float("nan"),
                    "aut_random_split": float(rs.mean()) if len(rs) else float("nan"),
                    "gap_random_minus_time_aware": float((rs - ta).mean())
                    if len(ta) == len(rs) and len(ta)
                    else float("nan"),
                    "gap_min_window": float((rs - ta).min())
                    if len(ta) == len(rs) and len(ta)
                    else float("nan"),
                    "gap_max_window": float((rs - ta).max())
                    if len(ta) == len(rs) and len(ta)
                    else float("nan"),
                    "n_windows_gap_positive": int(((rs - ta) > 0).sum())
                    if len(ta) == len(rs)
                    else 0,
                }
            )
    return pd.DataFrame(rows)


def plot(table: pd.DataFrame, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    datasets = list(dict.fromkeys(table["dataset"]))
    models = list(dict.fromkeys(table["model"]))
    fig, axes = plt.subplots(
        len(datasets),
        len(models),
        figsize=(5.2 * len(models), 3.4 * len(datasets)),
        sharey=True,
        squeeze=False,
        facecolor=SURFACE,
    )
    for i, ds in enumerate(datasets):
        for j, model in enumerate(models):
            ax = axes[i][j]
            ax.set_facecolor(SURFACE)
            for series in SLOT_ORDER:
                t = table[
                    (table["dataset"] == ds)
                    & (table["model"] == model)
                    & (table["series"] == series)
                ].sort_values("slot_position")
                if t.empty:
                    continue
                st = SERIES_STYLE[series]
                ax.fill_between(
                    t["slot_position"],
                    t["min_f1"],
                    t["max_f1"],
                    color=st["color"],
                    alpha=0.15,
                    linewidth=0,
                )
                ax.plot(
                    t["slot_position"],
                    t["mean_f1"],
                    color=st["color"],
                    label=st["label"],
                    linewidth=2,
                    marker="o",
                    markersize=4,
                )
            ax.set_title(f"{ds} - {model}", color=INK, fontsize=10, loc="left")
            ax.set_xlabel("evaluation slot in window", color=MUTED)
            if j == 0:
                ax.set_ylabel("F1 (mean over windows; band = range)", color=MUTED)
            ax.set_ylim(0, 1.02)
            ax.grid(alpha=0.25)
            ax.tick_params(colors=MUTED)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", action="append", required=True, help="DATASET=run directory")
    ap.add_argument(
        "--out-figure", type=Path, default=ROOT / "reports" / "figures" / "e1_random_vs_time.png"
    )
    ap.add_argument("--out-tables", type=Path, default=ROOT / "reports" / "tables")
    args = ap.parse_args(argv)
    runs = {}
    for spec in args.run:
        name, _, path = spec.partition("=")
        runs[name] = Path(path)
    per_slot = per_slot_table(runs)
    summary = summary_table(runs)
    args.out_tables.mkdir(parents=True, exist_ok=True)
    per_slot.to_csv(args.out_tables / "e1_per_slot.csv", index=False)
    summary.to_csv(args.out_tables / "e1_summary.csv", index=False)
    plot(per_slot, args.out_figure)
    print(summary.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
