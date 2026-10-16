"""E3 tables and figure from stored predictions (RQ3). No model fits.

    uv run python scripts/make_e3.py --results results/e3

Reads each dataset's E3 ledger and cells, recomputes per-slot F1 from stored predictions
(checked against the slot table) and writes into ``--out`` (default reports/tables):

- ``e3_selection.csv``  A-AUT per arm with labels spent, coverage and calibration diagnostics
- ``e3_contrasts.csv``  advantage over random per delay and the interaction (registered contrast)
- ``e3_ablation.csv``   the reserved-slice shares at the anchor cell (0 is the trap)
- ``e3_score.csv``      probability against centroid score at the anchor cell
- ``e3_ledger.csv``     planned, complete and failed cells with reasons

and ``reports/figures/e3_selection.png``. Every number that reaches a report must have a row
in docs/CLAIMS.md first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driftwatch.metrics import e3_tables as e3  # noqa: E402
from driftwatch.metrics import stats  # noqa: E402
from driftwatch.sim.cell_ids import planned_ids_from_file  # noqa: E402

DATASETS = ("lamda", "bodmas")
FILES = {
    "selection": "e3_selection.csv",
    "contrasts": "e3_contrasts.csv",
    "ablation": "e3_ablation.csv",
    "score": "e3_score.csv",
    "ledger": "e3_ledger.csv",
}
SURFACE, INK, MUTED = "#ffffff", "#1b1f24", "#5f6b76"
COLORS = {"uncertainty": "#1d4ed8", "credibility": "#c2410c"}


def build(
    results: Path, datasets=DATASETS, n_boot: int = stats.N_BOOT, spec_dir: Path | None = None
):
    parts: dict[str, list[pd.DataFrame]] = {k: [] for k in FILES}
    problems: list[str] = []
    models: set[str] = set()
    present: list[str] = []
    for ds in datasets:
        root = results / ds
        if not list(root.glob("ledger*.jsonl")):
            continue
        spec_file = (spec_dir or ROOT / "configs") / f"e3_{ds}.yaml"
        planned = planned_ids_from_file(spec_file) if spec_file.exists() else []
        col = e3.collect(root, ds, planned=planned)
        parts["ledger"].append(e3.ledger_table(col))
        if not col.arms:
            continue
        present.append(ds)
        models |= set(col.models)
        problems += [f"{ds}: {p}" for p in e3.check_equal_labels(col)]
        parts["selection"].append(e3.selection_table(col))
        parts["contrasts"].append(e3.contrasts_table(col, n_boot=n_boot))
        parts["ablation"].append(e3.ablation_table(col, n_boot=n_boot))
        parts["score"].append(e3.score_table(col))
    out = {k: (pd.concat(v, ignore_index=True) if v else pd.DataFrame()) for k, v in parts.items()}
    if problems:
        raise SystemExit("labels spent differ across arms:\n" + "\n".join(problems))
    if not out["contrasts"].empty:
        out["contrasts"] = e3.add_holm(out["contrasts"], present, sorted(models))
    return out


def figure(contrasts: pd.DataFrame, path: Path) -> bool:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    adv = contrasts[
        contrasts["contrast"].str.startswith("adv_d")
        & (contrasts["status"] == "computed")
        & (contrasts["seed_set"] == "0-4")
    ]
    if adv.empty:
        return False
    strata = sorted({(r.dataset, r.model) for r in adv.itertuples()})
    budgets = sorted(adv["budget_pct"].unique())
    fig, axes = plt.subplots(
        len(strata), len(budgets), figsize=(4.2 * len(budgets), 2.9 * len(strata)),
        squeeze=False, sharey=True, facecolor=SURFACE,
    )  # fmt: skip
    for i, (ds, model) in enumerate(strata):
        for j, b in enumerate(budgets):
            ax = axes[i][j]
            for sel, color in COLORS.items():
                t = adv[
                    (adv["dataset"] == ds) & (adv["model"] == model)
                    & (adv["selector"] == sel) & (adv["budget_pct"] == b)
                ].sort_values("delay")  # fmt: skip
                if t.empty:
                    continue
                ax.errorbar(
                    t["delay"], t["estimate"],
                    yerr=[t["estimate"] - t["ci_low"], t["ci_high"] - t["estimate"]],
                    color=color, marker="o", capsize=3, label=sel, linestyle="none",
                )  # fmt: skip
            ax.axhline(0, color=INK, linewidth=0.8)
            for edge in (-0.01, 0.01):
                ax.axhline(edge, color=MUTED, linewidth=0.6, linestyle=":")
            ax.set_title(f"{ds} - {model}, budget {b:g}%", color=INK, fontsize=9, loc="left")
            ax.set_xlabel("label delay (slots)", color=MUTED)
            if j == 0:
                ax.set_ylabel("A-AUT minus random", color=MUTED)
            ax.set_xticks(sorted(adv["delay"].unique()))
            ax.grid(alpha=0.25)
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False)
    fig.text(0.01, 0.005, "5 seeds, 95% two-stage bootstrap interval; dotted = +-0.01; at equal "
             "labels spent; two delays only, no decay shape implied. BODMAS at delay 3: no "
             "label has arrived at the refit.",
             color=MUTED, fontsize=7)  # fmt: skip
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", type=Path, default=ROOT / "results" / "e3")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "tables")
    ap.add_argument(
        "--figure", type=Path, default=ROOT / "reports" / "figures" / "e3_selection.png"
    )
    ap.add_argument("--spec-dir", type=Path, default=ROOT / "configs", help="e3_<dataset>.yaml")
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
    if not tables["contrasts"].empty and figure(tables["contrasts"], args.figure):
        print(f"wrote {args.figure.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
