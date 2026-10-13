"""Label influence: how many predictions change once labels have arrived (Phase 5, ADR-0007).

    uv run python scripts/label_influence.py --run lamda=never:<dir>,low:<dir>,high:<dir> ...

Three stored runs of one dataset on the same windows and seeds: ``never`` (the baseline),
``low`` and ``high`` (periodic retraining at a low and a high budget, same delay). For each
model the table counts, among the rows scored from the first retrain slot of each window
onwards, how many predictions differ between never and low, never and high, and low and high.
It also reports how many labels had arrived by the end of the window.

This is a diagnostic of the pool design, not a result. It reads predictions only and computes
no AUT and no F1; the pool design is fixed by ADR-0007 before any grid run and is never
chosen by looking at AUT. Every number that reaches a report must have a CLAIMS row first.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KEY = ["seed", "window_id", "slot_id", "row_id", "model"]


def _record(run_dir: Path) -> dict:
    return json.loads((run_dir / "run.json").read_text(encoding="utf-8"))["config"]


def _policy_name(cfg: dict) -> str | None:
    policy = cfg.get("policy")
    return policy.get("name") if isinstance(policy, dict) else policy


def _check_arms(never: dict, low: dict, high: dict) -> None:
    if never.get("policy") != "never" or never.get("selector") is not None:
        raise ValueError("the first run must be the never baseline (no selector)")
    if not all(_policy_name(c) == "periodic" for c in (low, high)):
        raise ValueError("low and high must be periodic runs")
    if low["delay"] != high["delay"]:
        raise ValueError("low and high must share one delay")
    if not low["budget_pct"] < high["budget_pct"]:
        raise ValueError("low must have the smaller budget_pct than high")
    for a, b in ((never, low), (never, high)):
        if a["seeds"] != b["seeds"] or a["window"] != b["window"] or a["model"] != b["model"]:
            raise ValueError("the runs must share seeds, windows and models")


def _predictions(run_dir: Path) -> pd.DataFrame:
    p = pd.read_parquet(run_dir / "predictions.parquet", columns=[*KEY, "series", "pred"])
    return p[p["series"] == "time_aware"].drop(columns="series")


def influence_table(dataset: str, never: Path, low: Path, high: Path) -> pd.DataFrame:
    never, low, high = Path(never), Path(low), Path(high)
    cfg_n, cfg_l, cfg_h = _record(never), _record(low), _record(high)
    _check_arms(cfg_n, cfg_l, cfg_h)

    m = _predictions(never).rename(columns={"pred": "pred_never"})
    for tag, d in (("low", low), ("high", high)):
        m = m.merge(
            _predictions(d).rename(columns={"pred": f"pred_{tag}"}),
            on=KEY,
            how="inner",
            validate="1:1",
        )
    n_rows = len(_predictions(never))
    if len(m) != n_rows:
        raise ValueError("the runs do not score the same rows")

    slots = pd.read_parquet(high / "slots.parquet", columns=["window_id", "slot_id", "slot_index"])
    slots = slots.drop_duplicates(["window_id", "slot_id"])
    ev = pd.read_parquet(
        high / "slots.parquet", columns=["window_id", "slot_index", "retrain_event"]
    )
    first = ev[ev["retrain_event"]].groupby("window_id")["slot_index"].min().rename("first_retrain")
    m = m.merge(slots, on=["window_id", "slot_id"], how="left").merge(
        first, left_on="window_id", right_index=True, how="left"
    )
    after = m[m["slot_index"] >= m["first_retrain"]]

    wl = pd.read_parquet(low / "windows.parquet")
    wh = pd.read_parquet(high / "windows.parquet")
    rows = []
    for model, grp in after.groupby("model"):
        n = len(grp)
        c_nl = int((grp["pred_never"] != grp["pred_low"]).sum())
        c_nh = int((grp["pred_never"] != grp["pred_high"]).sum())
        c_lh = int((grp["pred_low"] != grp["pred_high"]).sum())
        rows.append(
            {
                "dataset": dataset,
                "model": model,
                "n_windows": int(grp["window_id"].nunique()),
                "n_seeds": int(grp["seed"].nunique()),
                "delay": cfg_h["delay"],
                "budget_pct_low": cfg_l["budget_pct"],
                "budget_pct_high": cfg_h["budget_pct"],
                "n_scored_after_first_retrain": n,
                "n_changed_never_vs_low": c_nl,
                "share_changed_never_vs_low": c_nl / n if n else float("nan"),
                "n_changed_never_vs_high": c_nh,
                "share_changed_never_vs_high": c_nh / n if n else float("nan"),
                "n_changed_low_vs_high": c_lh,
                "share_changed_low_vs_high": c_lh / n if n else float("nan"),
                "mean_labels_arrived_low": float(
                    wl[wl["model"] == model]["n_arrived_final"].mean()
                ),
                "mean_labels_arrived_high": float(
                    wh[wh["model"] == model]["n_arrived_final"].mean()
                ),
                "mean_initial_pool_rows": float(wh[wh["model"] == model]["n_train_rows"].mean()),
            }
        )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--run",
        action="append",
        required=True,
        help="DATASET=never:DIR,low:DIR,high:DIR (repeat per dataset)",
    )
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "tables" / "label_influence.csv")
    args = ap.parse_args(argv)
    frames = []
    for spec in args.run:
        name, _, rest = spec.partition("=")
        dirs = dict(part.split(":", 1) for part in rest.split(","))
        frames.append(influence_table(name, dirs["never"], dirs["low"], dirs["high"]))
    table = pd.concat(frames, ignore_index=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.out, index=False)
    print(table.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
