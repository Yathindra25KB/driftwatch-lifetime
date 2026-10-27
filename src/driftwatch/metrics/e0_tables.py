"""Table 1 (E0 baselines) from stored results: the builder behind scripts/make_e0_table.py.

Kept in the library so that ``driftwatch reproduce table1`` and the script cannot diverge.
See the script docstring for the column definitions. No fits, no model code.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

KEYS = ["dataset", "model", "variant", "ratio"]
N_BOOT = 2000


def _time_aware(slots: pd.DataFrame) -> pd.DataFrame:
    """Keep the time-aware rows: an E1 run also stores per-slot random-split comparator rows."""
    if "series" not in slots.columns:
        return slots
    return slots[slots["series"] == "time_aware"]


def _block_bootstrap_gap(per_window: pd.DataFrame, block_len: int) -> tuple[float, float]:
    """95% interval of the mean gap over windows by moving-block bootstrap (time order)."""
    d = (per_window["f1_random_split"] - per_window["aut"]).dropna().to_numpy()
    n = d.size
    if n < 2:
        return float("nan"), float("nan")
    b = int(min(max(block_len, 1), n))
    rng = np.random.default_rng(0)
    n_blocks = -(-n // b)  # ceil
    starts = rng.integers(0, n - b + 1, size=(N_BOOT, n_blocks))
    idx = (starts[:, :, None] + np.arange(b)[None, None, :]).reshape(N_BOOT, -1)[:, :n]
    low, high = np.percentile(d[idx].mean(axis=1), [2.5, 97.5])
    return float(low), float(high)


def _block_len(config: dict[str, Any], variant: str) -> int:
    from driftwatch.metrics.aut import chow_stride

    w = config["window"]
    stride = chow_stride(w["nT"], w["nE"]) if variant == "rolling_chow" else w["stride"]
    return max(1, -(-w["nE"] // stride))


def _sd(values: pd.Series) -> float:
    return float(values.std(ddof=1)) if len(values) > 1 else float("nan")


def _baseline_rows(
    dataset: str, windows: pd.DataFrame, slots: pd.DataFrame, config: dict[str, Any]
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
        per_window = g.groupby("train_first")[["aut", "f1_random_split"]].mean().sort_index()
        block = _block_len(config, variant)
        low, high = _block_bootstrap_gap(per_window, block)
        window_gap = (per_window["f1_random_split"] - per_window["aut"]).dropna()
        prior = g["n_train_malware"] / g["n_train_rows"]
        distinct = s.drop_duplicates("slot_id")
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
                "gap_ci_low": low,  # moving-block bootstrap over windows
                "gap_ci_high": high,
                "gap_block_len": block,
                "gap_window_min": float(window_gap.min()) if len(window_gap) else np.nan,
                "gap_window_max": float(window_gap.max()) if len(window_gap) else np.nan,
                "random_test_ratio": float(g["random_achieved_ratio"].mean()),
                "train_prior_min": float(prior.min()),
                "train_prior_max": float(prior.max()),
                "f1_random_pooled": f1_pooled,  # pool-prior comparator (secondary)
                "gap_pooled": f1_pooled - a_aut,
                "f1_first_slot": float(g["f1_first"].mean()),
                "f1_last_slot": float(g["f1_last"].mean()),
                "mean_fpr": float(s["fpr"].mean()),
                "mean_fnr": float(s["fnr"].mean()),
                "mean_achieved_ratio": float(s["achieved_ratio"].mean()),
                "share_below_target": float((s["c3_status"] == "below_target").mean()),
                "n_distinct_slots": int(len(distinct)),
                "share_distinct_slots_below_target": float(
                    (distinct["c3_status"] == "below_target").mean()
                ),
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
        slots = _time_aware(pd.read_parquet(Path(directory) / "slots.parquet"))
        config = json.loads((Path(directory) / "run.json").read_text(encoding="utf-8"))["config"]
        base.extend(_baseline_rows(dataset, windows, slots, config))
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


def repeats_table(run_dirs: dict[str, Path]) -> pd.DataFrame:
    """Evaluated rows that repeat a feature vector of their training window (time-aware path)."""
    rows = []
    for dataset, directory in run_dirs.items():
        s = _time_aware(pd.read_parquet(Path(directory) / "slots.parquet"))
        s = s[(s["variant"] == "rolling") & (s["model"] == s["model"].iloc[0])]
        s = s[s["seed"] == s["seed"].min()]
        n, seen = int(s["n"].sum()), s["n_seen_in_initial_train"]
        rows.append(
            {
                "dataset": dataset,
                "variant": "rolling",
                "window_slot_cells": int(len(s)),
                "eval_rows": n,
                "repeat_rows": int(seen.sum()) if seen.notna().all() else None,
                "share": float(seen.sum() / n) if seen.notna().all() else None,
            }
        )
    return pd.DataFrame(rows)


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
