"""Build the E0 tables from stored results (no fits): scripts/make_e0_table.py.

    uv run python scripts/make_e0_table.py                       # newest run per dataset
    uv run python scripts/make_e0_table.py --run bodmas=results/e0/<hash16> ...

Reads ``windows.parquet`` and ``slots.parquet`` of each run and the canary JSON files, and
writes under ``reports/tables/``:

- ``e0_baselines.csv``: one row per (dataset, model, variant, ratio). A-AUT is the mean over
  seeds of the per-seed mean of window AUTs, with the std over windows averaged over seeds
  (sample std) and the spread of the per-seed means. The gap is the random-split F1 minus
  A-AUT, with a 95% percentile bootstrap interval over windows (windows averaged over seeds
  first; 2,000 draws, seed 0). Windows overlap, so the interval is a descriptive guide.
- ``e0_per_slot.csv``: F1, FPR, FNR and achieved ratio per evaluated slot, averaged over
  windows and seeds (the decay curve).
- ``e0_canary.csv``: the real-data canary verdicts.

Every number that reaches a report must have a row in docs/CLAIMS.md first.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["dataset", "model", "variant", "ratio"]
N_BOOT = 2000


def _bootstrap_gap(per_window: pd.DataFrame) -> tuple[float, float]:
    d = (per_window["f1_random_split"] - per_window["aut"]).dropna().to_numpy()
    if d.size < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(0)
    draws = d[rng.integers(0, d.size, size=(N_BOOT, d.size))].mean(axis=1)
    low, high = np.percentile(draws, [2.5, 97.5])
    return float(low), float(high)


def _sd(values: pd.Series) -> float:
    return float(values.std(ddof=1)) if len(values) > 1 else float("nan")


def _baseline_rows(
    dataset: str, windows: pd.DataFrame, slots: pd.DataFrame
) -> list[dict[str, Any]]:
    rows = []
    for (model, variant, ratio), g in windows.groupby(["model", "variant", "ratio"], sort=True):
        s = slots[
            (slots["model"] == model) & (slots["variant"] == variant) & (slots["ratio"] == ratio)
        ]
        g = g[g["aut"].notna()]  # a window with fewer than two evaluation slots has no AUT
        if g.empty:
            continue
        by_seed = g.groupby("seed").agg(
            aut_mean=("aut", "mean"),
            aut_std=("aut", _sd),
            f1_random=("f1_random_split", "mean"),
            f1_pooled=("f1_random_pooled", "mean"),
        )
        a_aut = float(by_seed["aut_mean"].mean())
        f1_random = (
            float(by_seed["f1_random"].mean()) if by_seed["f1_random"].notna().any() else np.nan
        )
        f1_pooled = (
            float(by_seed["f1_pooled"].mean()) if by_seed["f1_pooled"].notna().any() else np.nan
        )
        per_window = g.groupby("train_first")[["aut", "f1_random_split"]].mean()
        low, high = _bootstrap_gap(per_window)
        first_seed = g[g["seed"] == g["seed"].min()]
        rows.append(
            {
                "dataset": dataset,
                "model": model,
                "variant": variant,
                "ratio": float(ratio),
                "n_seeds": int(g["seed"].nunique()),
                "n_windows": int(first_seed["window_id"].nunique()),
                "n_eval_slots": int(first_seed["n_eval_slots"].max()),
                "a_aut_mean": a_aut,
                "a_aut_std": float(by_seed["aut_std"].mean())
                if by_seed["aut_std"].notna().any()
                else np.nan,
                "a_aut_seed_sd": _sd(by_seed["aut_mean"]),
                "f1_random_split": f1_random,  # prior-matched comparator (headline)
                "gap": f1_random - a_aut,
                "gap_ci_low": low,
                "gap_ci_high": high,
                "f1_random_pooled": f1_pooled,  # pool-prior comparator (secondary)
                "gap_pooled": f1_pooled - a_aut,
                "f1_first_slot": float(g["f1_first"].mean()),
                "f1_last_slot": float(g["f1_last"].mean()),
                "mean_fpr": float(s["fpr"].mean()),
                "mean_fnr": float(s["fnr"].mean()),
                "mean_achieved_ratio": float(s["achieved_ratio"].mean()),
                "share_below_target": float((s["c3_status"] == "below_target").mean()),
                "n_drop_events": float(first_seed["n_drop_events"].sum()),
                "n_recovered": float(first_seed["n_recovered"].sum()),
                "fit_seconds_median": float(g["fit_seconds"].median()),
                "share_converged": (
                    float(g["converged"].dropna().astype(bool).mean())
                    if g["converged"].notna().any()
                    else np.nan
                ),
                "sanity_band": "[verify]",
            }
        )
    return rows


def build_tables(run_dirs: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    base: list[dict[str, Any]] = []
    per_slot: list[pd.DataFrame] = []
    for dataset, directory in run_dirs.items():
        windows = pd.read_parquet(Path(directory) / "windows.parquet")
        slots = pd.read_parquet(Path(directory) / "slots.parquet")
        base.extend(_baseline_rows(dataset, windows, slots))
        agg = (
            slots.assign(below=(slots["c3_status"] == "below_target").astype(float))
            .groupby(["model", "variant", "ratio", "slot_id"], as_index=False)
            .agg(
                slot_index=("slot_index", "first"),
                n_cells=("f1", "size"),
                f1=("f1", "mean"),
                fpr=("fpr", "mean"),
                fnr=("fnr", "mean"),
                achieved_ratio=("achieved_ratio", "mean"),
                share_below_target=("below", "mean"),
            )
        )
        agg.insert(0, "dataset", dataset)
        per_slot.append(agg.sort_values(["model", "variant", "ratio", "slot_index"]))
    table = pd.DataFrame(base).sort_values(KEYS).reset_index(drop=True)
    return table, pd.concat(per_slot, ignore_index=True)


def canary_table(paths: Iterable[Path]) -> pd.DataFrame:
    rows = []
    for path in paths:
        r = json.loads(Path(path).read_text(encoding="utf-8"))
        verdict = r["verdict"]
        warning = bool(r.get("leakage_warning"))
        code = {"PASS": 3 if warning else 0, "FAIL": 1, "NO_GAP": 3}[verdict]
        rows.append(
            {
                "dataset": r["dataset"],
                "verdict": verdict,
                "exit_code": code,
                "n_windows": r["n_windows"],
                "aut_true": r["aut_true"],
                "aut_shuffled": r["aut_shuffled"],
                "f1_random_split": r["f1_random"],
                "gap": r["gap"],
                "closure": r["closure"],
                "leakage_warning": warning,
                "spec_digest": r["spec_digest"],
            }
        )
    return pd.DataFrame(rows)


class RunRejected(Exception):
    """A stored run is not a valid source for the E0 table."""


def check_run(directory: Path, config_dir: Path | None = None) -> dict[str, Any]:
    """Refuse a run that is partial, from a dirty tree, or not the committed E0 config.

    A toy or half-finished run in ``results/`` must never become Table 1.
    """
    record = json.loads((Path(directory) / "run.json").read_text(encoding="utf-8"))
    if record.get("status") != "complete":
        raise RunRejected(f"{directory}: status {record.get('status')!r}")
    if str(record.get("code_version", "")).endswith("-dirty"):
        raise RunRejected(f"{directory}: produced from a dirty tree ({record['code_version']})")
    cfg = record["config"]
    if config_dir is not None:
        path = Path(config_dir) / f"e0_{cfg['dataset']}.yaml"
        if path.exists():
            from driftwatch.sim.config import RunConfig

            committed = RunConfig.from_file(path).to_dict()
            if committed != cfg:
                raise RunRejected(f"{directory}: its config differs from {path.name}")
    return record


def _newest_runs(results: Path, config_dir: Path | None) -> dict[str, Path]:
    found: dict[str, tuple[float, Path]] = {}
    for record in results.glob("*/run.json"):
        try:
            data = check_run(record.parent, config_dir)
        except RunRejected as exc:
            print(f"skipped: {exc}")
            continue
        dataset = data["config"]["dataset"]
        mtime = record.stat().st_mtime
        if dataset not in found or mtime > found[dataset][0]:
            found[dataset] = (mtime, record.parent)
    return {k: v[1] for k, v in sorted(found.items())}


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
