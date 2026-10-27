"""E1 (RQ1): F1 versus evaluation slot, random split vs time-aware, from stored predictions.

    uv run python scripts/make_e1_figure.py --run lamda=results/e1/<hash16> \\
        --run bodmas=results/e1/<hash16>

Reads ``predictions.parquet`` of E1 runs (config: policy never, per-slot random-split
comparator on) and, for the ratio each slot reached and its C3 status, ``slots.parquet`` and
``windows.parquet``. F1 per (seed, window, slot) is computed from the stored labels and
decisions; nothing is fitted and no model code is imported. Writes
``reports/figures/e1_random_vs_time.png``, ``reports/tables/e1_per_slot.csv`` and
``e1_summary.csv``.

Definitions (descriptive; windows overlap, so spreads are ranges or standard deviations over
overlapping windows, not confidence intervals; the logistic model ignores the seed, so seeds
are not independent replicates):

- slot position: the evaluation slot's place inside its window (1..nE). It is not time since
  training: one calendar month sits at the same position in every window of a stride-aligned
  run, so per-position values mix months;
- per window, F1 is averaged over seeds first; the plotted line is the mean over windows and
  the band is the min-max range over windows;
- AUT of a series is the area under that series' per-slot F1 within a window (metrics.aut),
  averaged over windows. Both series use the same windows and seeds;
- ``gap_random_minus_time_aware``: per window, AUT of the random-split series minus AUT of
  the time-aware series, then the mean, sd and range over windows;
- ``gap_at_target_cells``: the mean per-slot F1 difference over the (seed, window, slot)
  cells where both series reached the target ratio (C3 status at_target);
- ``gap_e0_style``: the window-level pooled comparator F1 (E0's definition, from
  windows.parquet) minus the time-aware AUT, so the two comparators sit side by side;
- ``random_f1_pooled_eval_rows`` against ``random_f1_mean_slot``: the random-split F1 pooled
  over all evaluation-slot rows of a window versus the mean of its per-slot F1.

The random-split series trains on a random draw of the window's pooled raw rows (same size and
class counts as the time-aware training window) and is scored on the held-out rows of each
evaluation slot, malware subsampled to the target ratio per slot. It violates C1 by design.
Every number that reaches a report must have a row in docs/CLAIMS.md first.
"""

from __future__ import annotations

import argparse
from pathlib import Path

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
SLOT_COLUMNS = [
    "series",
    "model",
    "seed",
    "window_id",
    "slot_id",
    "n",
    "achieved_ratio",
    "c3_status",
]


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


def _cell_counts(preds: pd.DataFrame) -> pd.DataFrame:
    """tp, fp, fn and F1 per (series, model, seed, window, slot) from labels and decisions."""
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


def _window_key(window_id: pd.Series) -> pd.Series:
    """window_id embeds the seed through the spec digest; the window is what follows it."""
    return window_id.str.split("|", n=1).str[1]


def cells_table(run_dir: Path) -> pd.DataFrame:
    """One row per (series, model, seed, window, slot).

    F1 comes from the stored predictions; the ratio the slot reached and its C3 status come
    from the stored slot table.
    """
    run_dir = Path(run_dir)
    preds = _load(run_dir)
    cells = _positions(_cell_counts(preds), preds)
    slots = pd.read_parquet(run_dir / "slots.parquet", columns=SLOT_COLUMNS)
    keys = ["series", "model", "seed", "window_id", "slot_id"]
    cells = cells.merge(slots, on=keys, how="left", validate="1:1")
    cells["below_target"] = (cells["c3_status"] == "below_target").astype(float)
    cells["window_key"] = _window_key(cells["window_id"])
    return cells


def _seed_mean(cells: pd.DataFrame) -> pd.DataFrame:
    """Per (series, model, window, slot position): F1 averaged over seeds."""
    return (
        cells.groupby(["series", "model", "window_key", "slot_position"], as_index=False)["f1"]
        .mean()
        .rename(columns={"f1": "f1_seed_mean", "window_key": "window_id"})
    )


def window_series(run_dir: Path) -> pd.DataFrame:
    return _seed_mean(cells_table(run_dir))


def per_slot_table(runs: dict[str, Path]) -> pd.DataFrame:
    frames = []
    for dataset, run_dir in runs.items():
        c = cells_table(Path(run_dir))
        w = _seed_mean(c)
        g = w.groupby(["series", "model", "slot_position"])["f1_seed_mean"]
        t = g.agg(mean_f1="mean", min_f1="min", max_f1="max", n_windows="count").reset_index()
        ratio = (
            c.groupby(["series", "model", "slot_position"])
            .agg(
                mean_achieved_ratio=("achieved_ratio", "mean"),
                share_below_target=("below_target", "mean"),
                mean_n=("n", "mean"),
            )
            .reset_index()
        )
        t = t.merge(ratio, on=["series", "model", "slot_position"], validate="1:1")
        t.insert(0, "dataset", dataset)
        frames.append(t)
    return pd.concat(frames, ignore_index=True)


def _aut_by_window(m: pd.DataFrame) -> pd.Series:
    """AUT of the seed-averaged per-slot F1, one value per window (needs two slots)."""
    values = {
        wid: aut(g.sort_values("slot_position")["f1_seed_mean"].tolist())
        for wid, g in m.groupby("window_id")
        if len(g) >= 2
    }
    return pd.Series(values, dtype=float)


def gap_by_window(m: pd.DataFrame) -> pd.DataFrame:
    """Per window: AUT of each series and their difference, paired by window key.

    ``m`` is one model's seed-averaged window series. The two series must cover the same
    windows; a missing window raises rather than being compressed away.
    """
    ta = _aut_by_window(m[m["series"] == "time_aware"])
    rs = _aut_by_window(m[m["series"] == "random_split"])
    if set(ta.index) != set(rs.index):
        only_t = sorted(set(ta.index) - set(rs.index))
        only_r = sorted(set(rs.index) - set(ta.index))
        raise ValueError(
            f"window sets differ between series: time-aware only {only_t}, random only {only_r}"
        )
    out = pd.DataFrame({"aut_time_aware": ta, "aut_random_split": rs.reindex(ta.index)})
    out["gap"] = out["aut_random_split"] - out["aut_time_aware"]
    return out.sort_index()


def _pooled_f1(r: pd.DataFrame) -> float:
    """Random-split F1 pooled over the evaluation rows of each window, then averaged."""
    d = r.groupby(["seed", "window_key"])[["tp", "fp", "fn"]].sum()
    f = _f1(d["tp"], d["fp"], d["fn"])
    return float(f.groupby("window_key").mean().mean())


def summary_table(runs: dict[str, Path]) -> pd.DataFrame:
    rows = []
    for dataset, run_dir in runs.items():
        run_dir = Path(run_dir)
        c = cells_table(run_dir)
        windows = pd.read_parquet(run_dir / "windows.parquet")
        w = _seed_mean(c)
        for model, m in w.groupby("model"):
            gw = gap_by_window(m)
            cm = c[c["model"] == model]
            row: dict[str, object] = {
                "dataset": dataset,
                "model": model,
                "n_windows": int(len(gw)),
                "n_seeds": int(cm["seed"].nunique()),
                "n_slots": int(m["slot_position"].max()),
                "aut_time_aware": float(gw["aut_time_aware"].mean()),
                "aut_sd_time_aware": float(gw["aut_time_aware"].std(ddof=1)),
                "aut_random_split": float(gw["aut_random_split"].mean()),
                "aut_sd_random_split": float(gw["aut_random_split"].std(ddof=1)),
                "gap_random_minus_time_aware": float(gw["gap"].mean()),
                "gap_sd": float(gw["gap"].std(ddof=1)),
                "gap_min_window": float(gw["gap"].min()),
                "gap_max_window": float(gw["gap"].max()),
                "n_windows_gap_positive": int((gw["gap"] > 0).sum()),
            }
            for series in SLOT_ORDER:
                s = cm[cm["series"] == series]
                row[f"mean_achieved_ratio_{series}"] = float(s["achieved_ratio"].mean())
                row[f"share_below_target_{series}"] = float(s["below_target"].mean())
                row[f"mean_n_{series}"] = float(s["n"].mean())
            piv = cm.pivot_table(
                index=["seed", "window_key", "slot_id"],
                columns="series",
                values=["f1", "below_target"],
            )
            at_target = (piv[("below_target", "time_aware")] == 0) & (
                piv[("below_target", "random_split")] == 0
            )
            both = piv[at_target]
            diff = both[("f1", "random_split")] - both[("f1", "time_aware")]
            row["n_cells_at_target_both"] = int(len(both))
            row["gap_at_target_cells"] = float(diff.mean()) if len(both) else float("nan")
            wm = windows[windows["model"] == model]
            row["gap_e0_style"] = float((wm["f1_random_split"] - wm["aut"]).mean())
            r = cm[cm["series"] == "random_split"]
            row["random_f1_pooled_eval_rows"] = _pooled_f1(r)
            row["random_f1_mean_slot"] = float(r["f1"].mean())
            rows.append(row)
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
    fig.text(
        0.01,
        0.005,
        "Positions are slots within a window, not time since training: with a stride-aligned "
        "run one calendar month sits at the same position in every window.",
        color=MUTED,
        fontsize=7,
    )
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
    print(summary.T.to_string(header=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
