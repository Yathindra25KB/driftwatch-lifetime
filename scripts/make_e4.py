"""E4 tables and figure from stored predictions (RQ4). No model fits.

    uv run python scripts/make_e4.py --results results/e4

Reads each dataset's E4 ledger and cells, recomputes per-slot F1 from stored predictions
(checked against the slot table), checks that every arm spent the same labels in every slot,
and writes into ``--out`` (default reports/tables):

- ``e4_monitors.csv``   monitor quality: alarm precision, recall, detection delay, alarm rate
                        (observe-only in the never cell, and inside each monitor arm)
- ``e4_policies.csv``   A-AUT per arm with labels spent and refits per window
- ``e4_contrasts.csv``  M-P (matched labels) and M-C (matched retrains), Holm per family
- ``e4_ledger.csv``     planned, complete and failed cells with reasons

and ``reports/figures/e4_monitors.png``. Every number that reaches a report must have a row
in docs/CLAIMS.md first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driftwatch.metrics import e4_tables as e4  # noqa: E402
from driftwatch.metrics import stats  # noqa: E402
from driftwatch.sim.cell_ids import planned_ids_from_file  # noqa: E402

DATASETS = ("lamda", "bodmas")
FILES = {
    "monitors": "e4_monitors.csv",
    "policies": "e4_policies.csv",
    "contrasts": "e4_contrasts.csv",
    "ledger": "e4_ledger.csv",
}
SURFACE, INK, MUTED = "#ffffff", "#1b1f24", "#5f6b76"
# categorical slots 1-4 of the dataviz reference palette (validated: CVD and normal-vision
# separation pass on the light surface; two slots are under 3:1 contrast, so every mark has a
# legend entry and the numbers are in the CSV tables)
MONITOR_COLORS = {"ks": "#2a78d6", "mmd": "#eb6834", "domain_clf": "#1baf7a",
                  "p_uniformity": "#eda100"}  # fmt: skip
MIN_SPAN = 0.02  # A-AUT axis span at least twice the 0.01 margin
BASE_STYLE = {"never": ("#8a949e", "s"), "periodic": (INK, "D")}


def build(
    results: Path, datasets=DATASETS, n_boot: int = stats.N_BOOT, spec_dir: Path | None = None
):
    parts: dict[str, list[pd.DataFrame]] = {k: [] for k in FILES}
    problems: list[str] = []
    models: set[str] = set()
    delays: set[int] = set()

    for ds in datasets:
        root = results / ds
        if not list(root.glob("ledger*.jsonl")):
            continue
        spec_file = (spec_dir or ROOT / "configs") / f"e4_{ds}.yaml"
        planned = planned_ids_from_file(spec_file) if spec_file.exists() else []
        col = e4.collect(root, ds, planned=planned)
        parts["ledger"].append(e4.ledger_table(col))
        if not col.arms:
            continue

        models |= set(col.models)
        delays |= {k[2] for k in col.arms if k[2] is not None}
        problems += [f"{ds}: {p}" for p in e4.check_equal_labels(col)]
        parts["policies"].append(e4.policies_table(col))
        parts["contrasts"].append(e4.contrasts_table(col, n_boot=n_boot))
        parts["monitors"].append(e4.monitors_table(col, n_boot=n_boot))
    out = {k: (pd.concat(v, ignore_index=True) if v else pd.DataFrame()) for k, v in parts.items()}
    if problems:
        raise SystemExit("labels spent differ across arms:\n" + "\n".join(problems))
    if not out["contrasts"].empty:
        # the registered family: every requested dataset, a missing contrast at p = 1
        out["contrasts"] = e4.add_holm(
            out["contrasts"], list(datasets), sorted(models), sorted(delays)
        )
    return out


def figure(policies: pd.DataFrame, monitors: pd.DataFrame, path: Path) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    if policies.empty:
        return False
    strata = sorted({(r.dataset, r.model) for r in policies.itertuples()})
    delays = sorted(int(d) for d in policies["delay"].dropna().unique())
    ncol = len(delays) + 1
    fig, axes = plt.subplots(len(strata), ncol, figsize=(3.6 * ncol, 2.9 * len(strata)),
                             squeeze=False, facecolor=SURFACE)  # fmt: skip
    for i, (ds, model) in enumerate(strata):
        p = policies[(policies["dataset"] == ds) & (policies["model"] == model)]
        never = p[p["arm"] == "never"]
        for j, d in enumerate(delays):
            ax = axes[i][j]
            if j:
                ax.sharey(axes[i][0])  # one A-AUT scale across delays: no exaggerated gaps
            q = p[p["delay"] == d]
            for kind, (color, marker) in BASE_STYLE.items():
                r = never if kind == "never" else q[q["arm"] == kind]
                if len(r):
                    ax.plot(r["refits_per_window"], r["a_aut_mean"], marker=marker, color=color,
                            markersize=8, linestyle="none", zorder=3)  # fmt: skip
            for m, color in MONITOR_COLORS.items():
                mon, ctl = q[q["arm"] == f"monitor-{m}"], q[q["arm"] == f"matched-{m}"]
                if len(mon) and len(ctl):  # the M-C pair: same refits, timing differs
                    ax.plot([mon["refits_per_window"].iloc[0], ctl["refits_per_window"].iloc[0]],
                            [mon["a_aut_mean"].iloc[0], ctl["a_aut_mean"].iloc[0]],
                            color=color, linewidth=1, alpha=0.6, zorder=2)  # fmt: skip
                if len(mon):
                    ax.plot(mon["refits_per_window"], mon["a_aut_mean"], "o", color=color,
                            markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5,
                            zorder=5)  # fmt: skip
                if len(ctl):
                    ax.plot(ctl["refits_per_window"], ctl["a_aut_mean"], "^", color=color,
                            markerfacecolor=SURFACE, markersize=8, markeredgewidth=2,
                            zorder=4)  # fmt: skip
            ax.set_title(f"{ds} - {model}, delay {d}", color=INK, fontsize=9, loc="left")
            ax.set_xlabel("mean refits per window", color=MUTED, fontsize=8)
            if j == 0:
                ax.set_ylabel("A-AUT", color=MUTED, fontsize=8)
        lo, hi = axes[i][0].get_ylim()  # shared across the delay panels of the row
        if hi - lo < MIN_SPAN:  # never stretch differences inside the 0.01 margin
            mid = (hi + lo) / 2
            axes[i][0].set_ylim(mid - MIN_SPAN / 2, mid + MIN_SPAN / 2)
        ax = axes[i][-1]
        q = monitors[(monitors["dataset"] == ds) & (monitors["model"] == model)
                     & (monitors["context"] == "observe_never")
                     & (monitors["status"] == "computed")]  # fmt: skip
        for r in q.itertuples():
            has_ci = pd.notna(getattr(r, "precision_ci_low", float("nan")))
            ax.errorbar(
                r.precision, r.recall,
                xerr=[[r.precision - r.precision_ci_low], [r.precision_ci_high - r.precision]]
                if has_ci else None,
                yerr=[[r.recall - r.recall_ci_low], [r.recall_ci_high - r.recall]]
                if has_ci else None,
                marker="o" if has_ci else "x", color=MONITOR_COLORS[r.monitor], markersize=8,
                capsize=2, linestyle="none", markeredgewidth=2,
            )  # fmt: skip
        ax.set_xlim(-0.03, 1.03)
        ax.set_ylim(-0.03, 1.03)
        ax.set_title(f"{ds} - {model}, monitors on the never arm", color=INK, fontsize=9,
                     loc="left")  # fmt: skip
        ax.set_xlabel("alarm precision", color=MUTED, fontsize=8)
        ax.set_ylabel("alarm recall", color=MUTED, fontsize=8)
        for a in axes[i]:
            a.grid(alpha=0.2)
            a.tick_params(colors=MUTED, labelsize=7)
            for side in ("top", "right"):
                a.spines[side].set_visible(False)
    handles = [Line2D([], [], marker="o", color=c, linestyle="none", markersize=7, label=m)
               for m, c in MONITOR_COLORS.items()]  # fmt: skip
    handles += [
        Line2D([], [], marker="o", color=MUTED, linestyle="none", label="monitor-triggered"),
        Line2D([], [], marker="^", color=MUTED, markerfacecolor=SURFACE, linestyle="none",
               label="matched-count control"),
        Line2D([], [], marker="D", color=INK, linestyle="none", label="periodic(3)"),
        Line2D([], [], marker="s", color=BASE_STYLE["never"][0], linestyle="none",
               label="never"),
    ]  # fmt: skip
    fig.legend(handles=handles, loc="upper center", ncol=8, frameon=False, fontsize=7,
               labelcolor=INK)  # fmt: skip
    fig.text(0.01, 0.012, "Labels spent are equal in every arm. A line joins each monitor arm "
             "to its matched-count control (same refits per window, evenly spaced).\nRight: "
             "drop = F1 at least 0.05 below the trailing 3-slot mean; an alarm matches a drop "
             "within 2 slots; 95% two-stage bootstrap intervals.",
             color=MUTED, fontsize=7)  # fmt: skip
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", type=Path, default=ROOT / "results" / "e4")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "tables")
    ap.add_argument("--figure", type=Path, default=ROOT / "reports" / "figures" / "e4_monitors.png")
    ap.add_argument("--spec-dir", type=Path, default=ROOT / "configs", help="e4_<dataset>.yaml")
    ap.add_argument("--datasets", nargs="+", default=list(DATASETS), choices=DATASETS)
    ap.add_argument("--n-boot", type=int, default=stats.N_BOOT)
    args = ap.parse_args(argv)
    tables = build(args.results, tuple(args.datasets), args.n_boot, args.spec_dir)
    for key, name in FILES.items():
        df = tables[key]
        if df.empty:
            print(f"{name}: no rows (nothing complete yet)")
            continue
        args.out.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out / name, index=False, float_format="%.8f", lineterminator="\n")
        print(f"{name}: {len(df)} rows")
    if figure(tables["policies"], tables["monitors"], args.figure):
        print(f"wrote {args.figure.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
