"""E2 figures from the stored tables (no predictions, no model code, no fits).

    uv run python scripts/make_figures.py --tables reports/tables --out reports/figures

Reads the CSV files written by ``scripts/make_tables.py`` and writes:

- ``e2_heatmap_lamda.png`` and ``e2_heatmap_bodmas.png``: A-AUT over delay (rows) and budget
  (columns), one panel per model; each cell shows the mean and the standard deviation over
  windows, and the never-retrain A-AUT is the reference in the panel title;
- ``e2_per_slot_curves.png``: mean F1 per slot position, never against periodic at d = 0 and
  d = 3 (B = 5%), range over windows shaded;
- ``e2_contrasts.png``: the four primary contrasts with their 95% intervals.

Every figure is deterministic (fixed palette, fixed size, no embedded software tag).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SURFACE, INK, MUTED = "#ffffff", "#1b1f24", "#5f6b76"
ACCENT, ACCENT2, ACCENT3 = "#c2410c", "#1d4ed8", "#4d7c0f"
DELAYS = (0, 1, 2, 3)
BUDGETS = (0.5, 1.0, 2.0, 5.0)
DATASETS = ("lamda", "bodmas")


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, facecolor=SURFACE, metadata={"Software": None})
    _plt().close(fig)


def heatmap(aaut: pd.DataFrame, dataset: str, path: Path) -> bool:
    plt = _plt()
    a = aaut[
        (aaut["dataset"] == dataset) & (aaut["variant"] == "rolling") & (aaut["seed_set"] == "0-4")
    ]
    models = sorted(a["model"].unique())
    if a.empty:
        return False
    fig, axes = plt.subplots(
        1, len(models), figsize=(5.0 * len(models), 3.9), squeeze=False, facecolor=SURFACE
    )
    for ax, model in zip(axes[0], models, strict=True):
        m = a[a["model"] == model]
        grid = np.full((len(DELAYS), len(BUDGETS)), np.nan)
        sd = np.full_like(grid, np.nan)
        per = m[m["policy"] == "periodic"]
        for i, d in enumerate(DELAYS):
            for j, b in enumerate(BUDGETS):
                r = per[(per["delay"] == d) & (per["budget_pct"] == b)]
                if len(r):
                    grid[i, j] = float(r["a_aut_mean"].iloc[0])
                    sd[i, j] = float(r["a_aut_std"].iloc[0])
        never = m[m["policy"] == "never"]
        ref = float(never["a_aut_mean"].iloc[0]) if len(never) else float("nan")
        lo = np.nanmin(np.append(grid, ref)) if np.isfinite(grid).any() else 0.0
        hi = np.nanmax(np.append(grid, ref)) if np.isfinite(grid).any() else 1.0
        span = max(hi - lo, 0.02)
        im = ax.imshow(
            grid, cmap="Blues", vmin=lo - 0.1 * span, vmax=hi + 0.1 * span, aspect="auto"
        )
        for i in range(len(DELAYS)):
            for j in range(len(BUDGETS)):
                if np.isfinite(grid[i, j]):
                    ax.text(
                        j, i, f"{grid[i, j]:.3f}\n±{sd[i, j]:.3f}",
                        ha="center", va="center", fontsize=8, color=INK,
                    )  # fmt: skip
        ax.set_xticks(range(len(BUDGETS)), [f"{b:g}%" for b in BUDGETS])
        ax.set_yticks(range(len(DELAYS)), [f"d={d}" for d in DELAYS])
        ax.set_xlabel("analyst budget (% of the evaluated slot)", color=MUTED)
        ax.set_ylabel("label delay (slots)", color=MUTED)
        ax.set_title(
            f"{dataset} - {model}: periodic(3), never = {ref:.3f}",
            color=INK,
            fontsize=10,
            loc="left",
        )
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.text(
        0.01, 0.01,
        "A-AUT: mean over windows (seed-averaged) with the standard deviation over windows; "
        "5 seeds; windows overlap, so the spread is descriptive.",
        color=MUTED, fontsize=7,
    )  # fmt: skip
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    _save(fig, path)
    return True


def curves(per_slot: pd.DataFrame, path: Path) -> bool:
    plt = _plt()
    if per_slot.empty:
        return False
    models = sorted(per_slot["model"].unique())
    datasets = [d for d in DATASETS if d in set(per_slot["dataset"])]
    fig, axes = plt.subplots(
        len(datasets), len(models), figsize=(5.2 * len(models), 3.3 * len(datasets)),
        sharey=False, squeeze=False, facecolor=SURFACE,
    )  # fmt: skip
    arms = [
        ("never", None, None, "never", MUTED),
        ("periodic", 0.0, 5.0, "periodic d=0, B=5%", ACCENT),
        ("periodic", 3.0, 5.0, "periodic d=3, B=5%", ACCENT2),
    ]
    for i, ds in enumerate(datasets):
        for j, model in enumerate(models):
            ax = axes[i][j]
            for policy, delay, budget, label, color in arms:
                t = per_slot[
                    (per_slot["dataset"] == ds)
                    & (per_slot["model"] == model)
                    & (per_slot["policy"] == policy)
                ]
                if delay is not None:
                    t = t[(t["delay"] == delay) & (t["budget_pct"] == budget)]
                t = t.sort_values("slot_position")
                if t.empty:
                    continue
                ax.fill_between(t["slot_position"], t["min_f1"], t["max_f1"], color=color,
                                alpha=0.12, linewidth=0)  # fmt: skip
                ax.plot(t["slot_position"], t["mean_f1"], color=color, label=label,
                        linewidth=2, marker="o", markersize=3)  # fmt: skip
            ax.set_title(f"{ds} - {model}", color=INK, fontsize=10, loc="left")
            ax.set_xlabel("evaluation slot in window", color=MUTED)
            if j == 0:
                ax.set_ylabel("F1 (mean over windows; band = range)", color=MUTED)
            ax.grid(alpha=0.25)
            ax.tick_params(colors=MUTED)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    _save(fig, path)
    return True


def contrasts(table: pd.DataFrame, path: Path) -> bool:
    plt = _plt()
    t = table[table["seed_set"] == "0-9"]
    if t.empty:
        return False
    ids = ["C-D1", "C-D2", "C-P", "C-B"]
    strata = sorted({(r.dataset, r.model) for r in t.itertuples()})
    fig, ax = plt.subplots(figsize=(7.2, 0.55 * len(strata) * len(ids) + 1.6), facecolor=SURFACE)
    y = 0
    labels, ticks = [], []
    for ds, model in strata:
        for cid in ids:
            r = t[(t["dataset"] == ds) & (t["model"] == model) & (t["contrast"] == cid)]
            if r.empty:
                y += 1
                continue
            r = r.iloc[0]
            color = ACCENT if r["detected"] else MUTED
            ax.plot([r["ci_low"], r["ci_high"]], [y, y], color=color, linewidth=2)
            ax.plot([r["estimate"]], [y], "o", color=color)
            labels.append(f"{ds} {model} {cid}")
            ticks.append(y)
            y += 1
        y += 0.5
    ax.axvline(0, color=INK, linewidth=0.8)
    for edge in (-0.01, 0.01):
        ax.axvline(edge, color=MUTED, linewidth=0.6, linestyle=":")
    ax.set_yticks(ticks, labels, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("A-AUT difference (10 seeds; 95% two-stage bootstrap interval; dotted = +-0.01)",
                  color=MUTED, fontsize=8)  # fmt: skip
    ax.grid(axis="x", alpha=0.25)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    _save(fig, path)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tables", type=Path, default=ROOT / "reports" / "tables")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "figures")
    args = ap.parse_args(argv)

    def read(name: str) -> pd.DataFrame:
        p = args.tables / name
        return pd.read_csv(p) if p.exists() else pd.DataFrame()

    aaut = read("e2_aaut.csv")
    wrote = []
    for ds in DATASETS:
        if not aaut.empty and heatmap(aaut, ds, args.out / f"e2_heatmap_{ds}.png"):
            wrote.append(f"e2_heatmap_{ds}.png")
    if curves(read("e2_per_slot.csv"), args.out / "e2_per_slot_curves.png"):
        wrote.append("e2_per_slot_curves.png")
    if contrasts(read("e2_contrasts.csv"), args.out / "e2_contrasts.png"):
        wrote.append("e2_contrasts.png")
    print("wrote", ", ".join(wrote) or "nothing (no tables yet)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
