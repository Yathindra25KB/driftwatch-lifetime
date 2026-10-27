"""E3 tables from stored predictions: selector advantage, delay interaction, ablation, score.

The registered quantities are in docs/prereg/addendum-v2.md. For a selector ``S``
(uncertainty or credibility), budget ``B`` and delay ``d``, the advantage is
``adv_S(d, B) = A-AUT(S, d, B) - A-AUT(random, d, B)``, paired on windows and seeds, and the
primary contrast is the interaction ``I_S(B) = adv_S(d_low, B) - adv_S(d_high, B)`` (the
hypothesis predicts a positive value). Intervals are the two-stage bootstrap of v1.

Nothing is fitted here and no model code is imported. Labels spent are checked equal across
arms (the same ``n_queried`` per slot) before any contrast is built.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from driftwatch.metrics import stats
from driftwatch.metrics.grid_tables import (
    MARGIN,
    GridDataError,
    block_len,
    load_cell,
    verdict,
)
from driftwatch.sim.ledger import fold_events, merged_ledger_events

NOMINAL_COVERAGE = 0.90  # prediction sets {c : p_c > 0.10}
SEED_SETS = {"0-4": tuple(range(5)), "0-9": tuple(range(10))}
ArmKey = tuple[str, str, int, float, float, str]  # model, selector, delay, budget, share, score


def _wid(w: pd.Series) -> pd.Series:
    return stats.window_key(w.astype(str))


class E3Collected:
    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        self.arms: dict[ArmKey, pd.DataFrame] = {}
        self.slots: dict[ArmKey, list[pd.DataFrame]] = {}
        self.geometry: dict[str, int] = {}
        self.period = 3
        self.cells: list[dict[str, Any]] = []
        self.models: list[str] = []
        self.versions: set[str] = set()

    @property
    def n_refit_events(self) -> int:
        return max(0, (self.geometry.get("nE", 0) - 1) // self.period)

    @property
    def delay_axis_note(self) -> str:
        if self.n_refit_events <= 1:
            return (
                "single refit per window: periodic equals never at d >= period, so the "
                "advantage at the larger delay is zero by construction"
            )
        return ""


def collect(
    root: Path | str, dataset: str, *, planned: Sequence[str] = (), allow_mixed: bool = False
) -> E3Collected:
    root = Path(root)
    state = fold_events(merged_ledger_events(root), planned)
    col = E3Collected(dataset)
    blocks: dict[ArmKey, list[pd.DataFrame]] = {}
    for cid in sorted(state):
        st = state[cid]
        col.cells.append(
            {"cell_id": cid, "status": st.status, "code_version": st.code_version,
             "config_hash": st.config_hash, "wall_s": st.wall_s, "max_fit_s": st.max_fit_s,
             "peak_gb": st.peak_gb, "flags": ";".join(st.flags), "reason": st.reason}
        )  # fmt: skip
        if st.status != "complete" or not st.dir:
            continue
        if st.code_version:
            col.versions.add(st.code_version)
        d = load_cell(Path(st.dir))
        cfg = d["config"]
        sel = cfg["selector"]
        nc = cfg.get("nonconf") or {}
        w = cfg["window"]
        col.geometry = {"nT": w["nT"], "nE": w["nE"], "stride": w["stride"]}
        pol = cfg.get("policy")
        if isinstance(pol, dict):
            col.period = int(pol.get("period") or 3)
        for model in sorted(d["f1"]["model"].unique()):
            key: ArmKey = (
                model, sel["name"], int(cfg["delay"]), float(cfg["budget_pct"]),
                float(sel["calibration_fraction"]), str(nc.get("score", "probability")),
            )  # fmt: skip
            m = stats.aut_matrix(d["f1"], model, variant="rolling")
            blocks.setdefault(key, []).append(m.values)
            s = d["slots"][d["slots"]["model"] == model].copy()
            s["window_key"] = _wid(s["window_id"])
            col.slots.setdefault(key, []).append(s)
            if model not in col.models:
                col.models.append(model)
        del d
    if len(col.versions) > 1 and not allow_mixed:
        raise GridDataError(
            f"{dataset}: E3 cells completed at several code versions {sorted(col.versions)}"
        )
    for key, parts in blocks.items():
        seeds = [s for p in parts for s in p.columns]
        if len(set(seeds)) != len(seeds):
            raise GridDataError(f"arm {key}: a seed appears in two cells")
        col.arms[key] = pd.concat(parts, axis=1).sort_index(axis=1)
    col.models.sort()
    return col


# --- helpers ----------------------------------------------------------------------------------


def _diag(col: E3Collected, key: ArmKey, seeds: Sequence[int]) -> dict[str, float]:
    parts = col.slots.get(key, [])
    if not parts:
        return {}
    s = pd.concat(parts, ignore_index=True)
    s = s[s["seed"].isin(list(seeds))]
    if s.empty:
        return {}
    g = s.groupby(["seed", "window_key"])
    last = g.tail(1)
    out = {
        "labels_per_slot": float(s["n_queried"].mean()),
        "reserved_per_slot": float(s["n_calibration"].mean()),
        "selected_per_slot": float(s["n_selected"].mean()),
        "set_coverage": float(s["set_coverage"].mean())
        if s["set_coverage"].notna().any()
        else math.nan,
        "set_size_mean": float(s["set_size_mean"].mean())
        if s["set_size_mean"].notna().any()
        else math.nan,
        "credibility_mean": float(s["credibility_mean"].mean())
        if s["credibility_mean"].notna().any()
        else math.nan,
        "fallback_share": float(s["selection_fell_back_to_random"].astype(float).mean()),
        "cal_skipped_per_window": float(last["cal_skipped_total"].mean()),
        "cal_rows_end": float(last["cal_rows"].mean()),
    }
    arrived = last["n_arrived_train"].astype(float)
    out["arrived_malware_share"] = (
        float(last["n_arrived_train_malware"].sum() / arrived.sum())
        if arrived.sum() > 0
        else math.nan
    )
    return out


def _arms(col: E3Collected, keys: Sequence[ArmKey], seeds: Sequence[int]):
    frames = {}
    for i, k in enumerate(keys):
        f = col.arms.get(k)
        if f is None or any(s not in f.columns for s in seeds):
            return None
        frames[f"a{i}"] = f
    return stats.align_arms(frames, seeds=list(seeds))


def check_equal_labels(col: E3Collected) -> list[str]:
    """Arms compared at the same (delay, budget) must have queried the same labels per slot."""
    problems = []
    index = ["seed", "window_key", "slot_id"]
    by_cond: dict[tuple, list[tuple[ArmKey, pd.Series]]] = {}
    for key, parts in col.slots.items():
        s = pd.concat(parts, ignore_index=True)
        by_cond.setdefault((key[0], key[2], key[3]), []).append(
            (key, s.set_index(index)["n_queried"])
        )
    for cond, arms in by_cond.items():
        # every arm (selector, reserved share, score) is compared per seed, window and slot with
        # every other arm on the slots they share
        base_key, base = arms[0]
        for key, q in arms[1:]:
            both = base.index.intersection(q.index)
            if len(both) and (base.loc[both] != q.loc[both]).any():
                problems.append(f"{cond}: labels per slot differ between {base_key} and {key}")
    return problems


# --- tables -----------------------------------------------------------------------------------


def selection_table(col: E3Collected) -> pd.DataFrame:
    rows = []
    for key in sorted(col.arms):
        model, sel, d, b, frac, score = key
        frame = col.arms[key]
        for name, seeds in SEED_SETS.items():
            if not all(s in frame.columns for s in seeds):
                continue
            sub = frame[list(seeds)]
            win = sub.mean(axis=1)
            rows.append(
                {
                    "dataset": col.dataset, "model": model, "selector": sel, "delay": d,
                    "budget_pct": b, "reserved_share": frac, "score": score, "seed_set": name,
                    "role": "trap_demonstration" if frac == 0.0 else "descriptive",
                    "n_windows": len(win), "n_seeds": sub.shape[1],
                    "a_aut_mean": float(win.mean()),
                    "a_aut_std": float(sub.std(axis=0, ddof=1).mean())
                    if len(sub) > 1
                    else math.nan,
                    **_diag(col, key, seeds),
                    "delay_axis_note": col.delay_axis_note if d >= col.period else "",
                }
            )  # fmt: skip
    return pd.DataFrame(rows)


def _contrast_row(col, model, sel, budget, seed_set, delays, n_boot) -> list[dict[str, Any]]:
    frac, score = 0.20, "probability"
    d_lo, d_hi = min(delays), max(delays)
    keys = [
        (model, sel, d_lo, budget, frac, score), (model, "random", d_lo, budget, frac, score),
        (model, sel, d_hi, budget, frac, score), (model, "random", d_hi, budget, frac, score),
    ]  # fmt: skip
    seeds = SEED_SETS[seed_set]
    got = _arms(col, keys, seeds)
    base = {"dataset": col.dataset, "model": model, "selector": sel, "budget_pct": budget,
            "seed_set": seed_set}  # fmt: skip
    if got is None:
        return [{**base, "contrast": f"I_{sel}", "status": "not_computed",
                 "reason": "an arm or seed is missing", "verdict": "not_computed"}]  # fmt: skip
    arrays, windows, used = got
    bl = block_len({**col.geometry, "stride": col.geometry["stride"]})
    rs = stats.resample_means(arrays, bl, n_boot=n_boot)
    pt = stats.arm_means(arrays)
    out = []
    for name, (s_i, r_i, d) in {
        f"adv_d{d_lo}": ("a0", "a1", d_lo),
        f"adv_d{d_hi}": ("a2", "a3", d_hi),
    }.items():
        est = stats.estimate(pt[s_i] - pt[r_i], rs[s_i] - rs[r_i])
        out.append(
            {**base, "contrast": f"{name}_{sel}", "delay": d, "role": "descriptive",
             "status": "computed", "reason": "", "n_windows": len(windows), "n_seeds": len(used),
             "estimate": est.point, "ci_low": est.low, "ci_high": est.high,
             "verdict": verdict(est), "half_width": est.half_width,
             "labels_per_slot": _diag(col, keys[0] if d == d_lo else keys[2], seeds).get(
                 "labels_per_slot"
             )}
        )  # fmt: skip
    point = (pt["a0"] - pt["a1"]) - (pt["a2"] - pt["a3"])
    samp = (rs["a0"] - rs["a1"]) - (rs["a2"] - rs["a3"])
    est = stats.estimate(point, samp)
    per_seed = ((arrays["a0"] - arrays["a1"]) - (arrays["a2"] - arrays["a3"])).mean(axis=0)
    out.append(
        {**base, "contrast": f"I_{sel}", "delay": None,
         "role": "primary" if seed_set == "0-9" else "seed_robustness", "status": "computed",
         "reason": "", "n_windows": len(windows), "n_seeds": len(used), "block_len": bl,
         "block_len_effective": stats.effective_block(bl, len(windows)),
         "window_stage_coarse": stats.window_stage_is_coarse(bl, len(windows)),
         "estimate": est.point, "ci_low": est.low, "ci_high": est.high,
         "boot_mean_minus_point": est.boot_mean - est.point, "half_width": est.half_width,
         "verdict": verdict(est), "seed_level_wilcoxon_p": stats.wilcoxon_p(per_seed),
         "min_wilcoxon_p": stats.min_wilcoxon_p(len(used)),
         "labels_per_slot": _diag(col, keys[0], seeds).get("labels_per_slot"),
         "delay_axis_note": col.delay_axis_note}
    )  # fmt: skip
    return out


def contrasts_table(
    col: E3Collected, *, delays: Sequence[int] | None = None,
    budgets: Sequence[float] | None = None, models: Sequence[str] | None = None,
    n_boot: int = stats.N_BOOT,
) -> pd.DataFrame:  # fmt: skip
    """Delays and budgets default to those the random (reference) arms were run at."""
    ref = [k for k in col.arms if k[1] == "random" and k[4] == 0.20 and k[5] == "probability"]
    delays = delays or sorted({k[2] for k in ref})
    budgets = budgets or sorted({k[3] for k in ref})
    if len(delays) < 2:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for model in models or col.models:
        for sel in ("uncertainty", "credibility"):
            for b in budgets:
                for ss in SEED_SETS:
                    rows += _contrast_row(col, model, sel, b, ss, delays, n_boot)
    return pd.DataFrame(rows)


def add_holm(df: pd.DataFrame, datasets: Sequence[str], models: Sequence[str],
             budgets: Sequence[float] | None = None) -> pd.DataFrame:  # fmt: skip
    """Holm over the registered interaction family: datasets x models x selectors x budgets."""
    out = df.copy()
    out["seed_level_wilcoxon_p_holm"] = np.nan
    prim = out[(out["role"] == "primary") & out["contrast"].str.startswith("I_")]
    budgets = budgets or sorted(out["budget_pct"].dropna().unique())
    expected = [(d, m, s, b) for d in datasets for m in models
                for s in ("uncertainty", "credibility") for b in budgets]  # fmt: skip
    ps = []
    for d, m, s, b in expected:
        r = prim[(prim["dataset"] == d) & (prim["model"] == m) & (prim["selector"] == s)
                 & (prim["budget_pct"] == b)]  # fmt: skip
        ps.append(float(r["seed_level_wilcoxon_p"].iloc[0]) if len(r) == 1 else 1.0)
    adj = dict(zip(expected, stats.holm(ps), strict=True))
    for idx, r in prim.iterrows():
        k = (r["dataset"], r["model"], r["selector"], r["budget_pct"])
        if k in adj:
            out.loc[idx, "seed_level_wilcoxon_p_holm"] = adj[k]
    out["family_size"] = len(expected)
    return out


def anchor_of(col: E3Collected) -> dict[str, Any]:
    """The anchor cell: the one condition that has other reserved shares or another score."""
    for _model, sel, d, b, frac, score in sorted(col.arms):
        if frac != 0.20 or score != "probability":
            return {"selector": sel, "delay": d, "budget_pct": b}
    return {}


def ablation_table(col: E3Collected, *, anchor: dict[str, Any] | None = None,
                   n_boot: int = stats.N_BOOT) -> pd.DataFrame:  # fmt: skip
    """The reserved-slice shares at the anchor cell, against random and the default share."""
    rows = []
    seeds = SEED_SETS["0-4"]
    a = anchor or anchor_of(col)
    sel = a.get("selector", "credibility")
    d, b = int(a.get("delay", 0)), float(a.get("budget_pct", 2.0))
    for model in col.models:
        shares = sorted(
            {k[4] for k in col.arms if k[:4] == (model, sel, d, b) and k[5] == "probability"}
        )
        ref = (model, "random", d, b, 0.20, "probability")
        for frac in shares:
            key = (model, sel, d, b, frac, "probability")
            got = _arms(col, [key, ref], seeds)
            if got is None:
                continue
            arrays, windows, used = got
            bl = block_len(col.geometry)
            rs = stats.resample_means(arrays, bl, n_boot=n_boot)
            pt = stats.arm_means(arrays)
            est = stats.estimate(pt["a0"] - pt["a1"], rs["a0"] - rs["a1"])
            dg = _diag(col, key, seeds)
            rows.append(
                {"dataset": col.dataset, "model": model, "selector": sel, "delay": d,
                 "budget_pct": b, "reserved_share": frac,
                 "role": "trap_demonstration" if frac == 0.0 else "descriptive",
                 "n_windows": len(windows), "n_seeds": len(used),
                 "advantage_vs_random": est.point, "ci_low": est.low, "ci_high": est.high,
                 "set_coverage": dg.get("set_coverage"),
                 "coverage_minus_nominal": (dg.get("set_coverage") or math.nan) - NOMINAL_COVERAGE,
                 "credibility_mean": dg.get("credibility_mean"),
                 "fallback_share": dg.get("fallback_share"),
                 "cal_skipped_per_window": dg.get("cal_skipped_per_window"),
                 "labels_per_slot": dg.get("labels_per_slot")}
            )  # fmt: skip
    return pd.DataFrame(rows)


def score_table(col: E3Collected, *, anchor: dict[str, Any] | None = None) -> pd.DataFrame:
    rows = []
    a = anchor or anchor_of(col)
    sel = a.get("selector", "credibility")
    d, b = int(a.get("delay", 0)), float(a.get("budget_pct", 2.0))
    for model in col.models:
        for score in ("probability", "centroid"):
            key = (model, sel, d, b, 0.20, score)
            if key not in col.arms:
                continue
            frame = col.arms[key]
            seeds = SEED_SETS["0-4"]
            if not all(s in frame.columns for s in seeds):
                continue
            rows.append(
                {"dataset": col.dataset, "model": model, "selector": sel, "delay": d,
                 "budget_pct": b, "score": score, "role": "descriptive",
                 "a_aut_mean": float(frame[list(seeds)].mean(axis=1).mean()),
                 **_diag(col, key, seeds)}
            )  # fmt: skip
    return pd.DataFrame(rows)


def ledger_table(col: E3Collected) -> pd.DataFrame:
    df = pd.DataFrame(col.cells)
    df.insert(0, "dataset", col.dataset)
    return df


__all__ = [
    "MARGIN", "NOMINAL_COVERAGE", "E3Collected", "ablation_table", "add_holm",
    "check_equal_labels", "collect", "contrasts_table", "ledger_table", "score_table",
    "selection_table",
]  # fmt: skip
