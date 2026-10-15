"""E2 tables from stored predictions: A-AUT cells, pre-registered contrasts, labels, recovery.

Reads the grid's ledger and, for every complete cell, ``predictions.parquet`` (per-slot F1
is recomputed from stored labels and decisions and checked against the slot table),
``slots.parquet`` and ``run.json``. Nothing is fitted and no model code is imported: the
only simulator modules read are the ledger and the cell-id helper, which hold no model code.

The contrasts, units and decision rules are those of docs/PREREG.md (prereg-v1) and are
implemented in :mod:`driftwatch.metrics.stats`. All values are descriptive of the stored
runs; every number that reaches a report must have a row in docs/CLAIMS.md first.

Reading rules built into the columns (statistics review, Phase 6):

- ``role`` says what a row is: ``primary`` (10 seeds, registered), ``seed_robustness`` (the
  same contrast on seeds 0-4, nested in the 10-seed set, not a replication),
  ``chow_secondary``, ``descriptive``;
- ``verdict`` is one of ``detected``, ``detected_within_margin``, ``reversed``,
  ``equivalent`` (interval inside the margin), ``not_detected``, ``not_computed``;
- a contrast whose arms are missing is a row with ``status = not_computed`` and its reason,
  never a silent omission;
- the seed-level Wilcoxon p-value is conditional on the realised windows and measures
  subsample noise only; it is a supporting check, not a second test.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from driftwatch.metrics import stats
from driftwatch.metrics.slot import drop_events
from driftwatch.sim.ledger import fold_events, merged_ledger_events

MARGIN = 0.01  # practical-equivalence margin (PREREG, estimate confirmed 15 Oct 2026)
BAND = 0.05  # RQ1 band (PREREG)
SEED_SETS = {"0-4": tuple(range(5)), "0-9": tuple(range(10))}
BUDGETS = (0.5, 1.0, 2.0, 5.0)
DELAYS = (0, 1, 2, 3)
PRED_COLUMNS = ["series", "variant", "model", "seed", "window_id", "slot_id", "y_true", "pred"]
PRIMARY = (
    ("C-D1", "d=0 minus d=3, B=1%, periodic", ("periodic", 0, 1.0), ("periodic", 3, 1.0), 3),
    ("C-D2", "d=0 minus d=3, B=5%, periodic", ("periodic", 0, 5.0), ("periodic", 3, 5.0), 3),
    ("C-P", "periodic (d=0, B=5%) minus never", ("periodic", 0, 5.0), ("never", None, None), None),
    ("C-B", "B=5% minus B=0.5%, d=0, periodic", ("periodic", 0, 5.0), ("periodic", 0, 0.5), None),
)
FAMILY_SIZE_PER_STRATUM = len(PRIMARY)

ArmKey = tuple[str, str, str, "int | None", "float | None"]  # variant, model, policy, delay, budget


class GridDataError(ValueError):
    """Stored results are inconsistent with the slot table or the ledger."""


@dataclass
class Collected:
    dataset: str
    arms: dict[ArmKey, pd.DataFrame] = field(default_factory=dict)  # windows x seeds AUT
    f1: dict[ArmKey, pd.DataFrame] = field(default_factory=dict)  # per-slot F1 cells
    counts_blocks: dict[ArmKey, list[tuple[frozenset[int], dict[str, float]]]] = field(
        default_factory=dict
    )  # label counts per seed block (a block is one finished cell)
    undefined: dict[ArmKey, int] = field(default_factory=dict)
    geometry: dict[str, dict[str, int]] = field(default_factory=dict)  # variant -> nT, nE, stride
    period: int = 3
    cells: list[dict[str, Any]] = field(default_factory=list)  # ledger summary rows
    models: list[str] = field(default_factory=list)
    code_versions: set[str] = field(default_factory=set)

    # -- counts ------------------------------------------------------------------------------

    def counts_for(self, key: ArmKey, seeds: Iterable[int]) -> dict[str, float]:
        """Label counts of an arm over exactly the blocks whose seeds lie inside ``seeds``.

        Blocks are weighted by their number of (seed, window) cells, so a "0-4" row reports
        the 0-4 block only and a "0-9" row both blocks.
        """
        want = set(seeds)
        parts = [
            (c, c.get("n_cells", 1.0)) for s, c in self.counts_blocks.get(key, []) if s <= want
        ]
        if not parts:
            return {}
        total = sum(w for _, w in parts)
        names = {k for c, _ in parts for k in c}
        out = {}
        for k in names:
            vals = [(c[k], w) for c, w in parts if k in c and not math.isnan(c[k])]
            out[k] = sum(v * w for v, w in vals) / sum(w for _, w in vals) if vals else float("nan")
        out["n_cells"] = total
        return out

    @property
    def n_refit_events(self) -> int:
        """Retrain events per window (before slots p, 2p, ... inside the evaluation slots)."""
        nE = self.geometry.get("rolling", {}).get("nE", 0)
        return max(0, (nE - 1) // self.period)

    @property
    def delay_axis_note(self) -> str:
        if self.n_refit_events <= 1:
            return (
                "single refit per window: the delay axis is a delay in one refit, "
                "and periodic at d >= period equals never by construction"
            )
        return ""


# --- loading ----------------------------------------------------------------------------------


def _policy(cfg: Mapping[str, Any]) -> tuple[str, int]:
    p = cfg.get("policy")
    if isinstance(p, dict):
        return str(p["name"]), int(p.get("period") or 3)
    return str(p), 3


def _variant_geometry(cfg: Mapping[str, Any], variant: str) -> dict[str, int]:
    w = cfg["window"]
    stride = min(w["nT"], w["nE"]) if variant == "rolling_chow" else w["stride"]
    return {"nT": w["nT"], "nE": w["nE"], "stride": stride}


def block_len(geometry: Mapping[str, int]) -> int:
    return stats.block_length(geometry["nE"], geometry["stride"])


def load_cell(run_dir: Path) -> dict[str, Any]:
    """Per-slot F1 and counts of one finished run, checked against its slot table."""
    run_dir = Path(run_dir)
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    cfg = record["config"]
    preds = pq.read_table(run_dir / "predictions.parquet", columns=PRED_COLUMNS).to_pandas()
    preds = preds[preds["series"] == "time_aware"]
    slots = pd.read_parquet(run_dir / "slots.parquet")
    slots = slots[slots["series"] == "time_aware"] if "series" in slots.columns else slots
    order = slots[["window_id", "slot_id", "slot_index"]].drop_duplicates()
    cells = stats.f1_per_slot(preds, order)
    del preds
    keys = ["model", "seed", "window_id", "slot_id", "variant"]
    chk = cells.merge(
        slots[[*keys, "f1"]].assign(window_id=lambda d: d["window_id"].astype(str)),
        on=keys,
        how="outer",
        suffixes=("", "_slot"),
        indicator=True,
    )
    if (chk["_merge"] != "both").any():
        raise GridDataError(f"{run_dir}: predictions and slot table list different cells")
    if (chk["f1"] - chk["f1_slot"]).abs().max() > 1e-9:
        raise GridDataError(f"{run_dir}: F1 from stored predictions differs from the slot table")
    windows = pd.read_parquet(run_dir / "windows.parquet")
    return {"record": record, "config": cfg, "f1": cells, "slots": slots, "windows": windows}


def _label_counts(slots: pd.DataFrame, windows: pd.DataFrame, model: str, variant: str):
    s = slots[(slots["model"] == model) & (slots["variant"] == variant)]
    w = windows[(windows["model"] == model) & (windows["variant"] == variant)]
    out: dict[str, float] = {"n_cells": float(len(s))}
    if "n_budget" in s.columns and s["n_budget"].notna().any():
        per_ws = s.groupby(["seed", "window_id"])
        out.update(
            labels_budget_per_slot=float(s["n_budget"].mean()),
            labels_queried_per_slot=float(s["n_queried"].mean()),
            labels_queried_per_window=float(per_ws["n_queried"].sum().mean()),
            labels_released_per_window=float(per_ws["n_released"].sum().mean()),
            labels_ignored_per_window=float(per_ws["n_ignored_after_end"].sum().mean()),
            retrains_per_window=float(per_ws["retrained"].sum().mean()),
            noop_retrains_per_window=float(
                (per_ws["retrain_event"].sum() - per_ws["retrained"].sum()).mean()
            ),
            pool_final_mean=float(per_ws["n_pool"].max().mean()),
        )
        if s["n_seen_in_pool"].notna().any():
            out["n_seen_in_pool_share"] = float(s["n_seen_in_pool"].sum() / s["n"].sum())
    if s["n_seen_in_initial_train"].notna().any():
        out["n_seen_initial_share"] = float(s["n_seen_in_initial_train"].sum() / s["n"].sum())
    out["mean_achieved_ratio"] = float(s["achieved_ratio"].mean())
    out["share_below_target"] = float((s["c3_status"] == "below_target").mean())
    out["windows_rows"] = float(len(w))
    return out


def collect(
    root: Path | str,
    dataset: str,
    *,
    ledger_root: Path | str | None = None,
    planned: Sequence[str] = (),
    allow_mixed_versions: bool = False,
) -> Collected:
    """Every complete cell under ``root`` as AUT matrices per arm (seed blocks joined).

    ``planned`` lists the planned cell ids, so that a cell the ledger never saw appears in
    the ledger table as ``planned``. Cells completed at different code versions are an
    error unless ``allow_mixed_versions`` (a reviewed rerun after a fix).
    """
    root = Path(root)
    events = merged_ledger_events(ledger_root or root)
    state = fold_events(events, planned)
    col = Collected(dataset)
    blocks: dict[ArmKey, list[pd.DataFrame]] = {}
    f1_blocks: dict[ArmKey, list[pd.DataFrame]] = {}
    for cell_id in sorted(state):
        st = state[cell_id]
        col.cells.append(
            {
                "cell_id": cell_id,
                "status": st.status,
                "code_version": st.code_version,
                "config_hash": st.config_hash,
                "wall_s": st.wall_s,
                "max_fit_s": st.max_fit_s,
                "peak_gb": st.peak_gb,
                "flags": ";".join(st.flags),
                "reason": st.reason,
                "attempts": st.attempts,
            }
        )
        if st.status != "complete" or not st.dir:
            continue
        if st.code_version:
            col.code_versions.add(st.code_version)
        d = load_cell(Path(st.dir))
        cfg = d["config"]
        policy, period = _policy(cfg)
        if policy == "periodic":
            col.period = period
        delay = cfg.get("delay")
        budget = cfg.get("budget_pct")
        for variant in cfg["e0"]["variants"]:
            col.geometry[variant] = _variant_geometry(cfg, variant)
            for model in sorted(d["f1"]["model"].unique()):
                key: ArmKey = (variant, model, policy, delay, budget)
                m = stats.aut_matrix(d["f1"], model, variant=variant)
                blocks.setdefault(key, []).append(m.values)
                col.undefined[key] = max(col.undefined.get(key, 0), m.n_windows_undefined)
                sel = d["f1"][(d["f1"]["model"] == model) & (d["f1"]["variant"] == variant)]
                f1_blocks.setdefault(key, []).append(
                    sel[["seed", "window_key", "slot_index", "f1"]].copy()
                )
                seeds = frozenset(int(s) for s in m.values.columns)
                col.counts_blocks.setdefault(key, []).append(
                    (seeds, _label_counts(d["slots"], d["windows"], model, variant))
                )
                if model not in col.models:
                    col.models.append(model)
        del d
    if len(col.code_versions) > 1 and not allow_mixed_versions:
        raise GridDataError(
            f"{dataset}: cells were completed at several code versions "
            f"{sorted(col.code_versions)}; a contrast must not mix them (review the ledger)"
        )
    for key, parts in blocks.items():
        seeds = [s for p in parts for s in p.columns]
        if len(set(seeds)) != len(seeds):
            raise GridDataError(f"arm {key}: a seed appears in two cells")
        wins = [tuple(p.index) for p in parts]
        if any(w != wins[0] for w in wins):
            raise GridDataError(f"arm {key}: seed blocks cover different windows")
        col.arms[key] = pd.concat(parts, axis=1).sort_index(axis=1)
        col.f1[key] = pd.concat(f1_blocks[key], ignore_index=True)
    col.models.sort()
    return col


# --- helpers ----------------------------------------------------------------------------------


def _sort_key(k: ArmKey):
    return (k[0], k[1], k[2], -1 if k[3] is None else k[3], -1 if k[4] is None else k[4])


def _seed_cols(frame: pd.DataFrame, seeds: Iterable[int]) -> pd.DataFrame | None:
    want = list(seeds)
    return frame[want] if all(s in frame.columns for s in want) else None


def _arm(col: Collected, variant: str, model: str, policy: str, delay, budget):
    return col.arms.get((variant, model, policy, delay, budget))


def _queried(col: Collected, variant: str, model: str, arm: tuple, seeds) -> float:
    """Mean labels queried per slot (the registered unit uses queries, not the allowance)."""
    policy, delay, budget = arm
    if policy == "never":
        return 0.0
    c = col.counts_for((variant, model, policy, delay, budget), seeds)
    return float(c.get("labels_queried_per_slot", math.nan))


def verdict(est: stats.Estimate, *, margin: float = MARGIN) -> str:
    """Three-way reading of a registered contrast (hypothesised direction: positive)."""
    if est.high < 0.0:
        return "reversed"
    if est.low > 0.0:
        return "detected_within_margin" if est.high <= margin else "detected"
    if est.low >= -margin and est.high <= margin:
        return "equivalent"
    return "not_detected"


# --- tables -----------------------------------------------------------------------------------


def aaut_table(col: Collected) -> pd.DataFrame:
    """A-AUT per arm and seed set: mean and std over windows, seed spread, label counts.

    ``a_aut_std`` follows E0 (the std over windows is taken per seed, then averaged over
    seeds) so that it is comparable with Table 1; ``a_aut_std_seed_averaged`` is the std over
    windows of the seed-averaged AUT.
    """
    rows = []
    for key in sorted(col.arms, key=_sort_key):
        variant, model, policy, delay, budget = key
        frame = col.arms[key]
        for name, seeds in SEED_SETS.items():
            sub = _seed_cols(frame, seeds)
            if sub is None:
                continue
            win = sub.mean(axis=1)
            per_seed_std = sub.std(axis=0, ddof=1) if len(sub) > 1 else None
            c = col.counts_for(key, seeds)
            never = policy == "never"
            rows.append(
                {
                    "dataset": col.dataset,
                    "variant": variant,
                    "model": model,
                    "policy": policy,
                    "delay": delay,
                    "budget_pct": budget,
                    "seed_set": name,
                    "role": "descriptive",
                    "n_windows": int(len(win)),
                    "n_seeds": int(sub.shape[1]),
                    "a_aut_mean": float(win.mean()),
                    "a_aut_std": float(per_seed_std.mean())
                    if per_seed_std is not None
                    else math.nan,
                    "a_aut_std_seed_averaged": float(win.std(ddof=1)) if len(win) > 1 else math.nan,
                    "seed_sd": float(sub.mean(axis=0).std(ddof=1))
                    if sub.shape[1] > 1
                    else math.nan,
                    "windows_undefined": col.undefined.get(key, 0),
                    "labels_per_slot": 0.0 if never else c.get("labels_queried_per_slot", math.nan),
                    "labels_per_window": 0.0
                    if never
                    else c.get("labels_queried_per_window", math.nan),
                    "retrains_per_window": c.get("retrains_per_window", 0.0),
                    "mean_achieved_ratio": c.get("mean_achieved_ratio", math.nan),
                    "share_below_target": c.get("share_below_target", math.nan),
                    "delay_axis_note": col.delay_axis_note if not never else "",
                }
            )
    return pd.DataFrame(rows)


def _not_computed(col: Collected, cid, desc, model, variant, seed_set, role, reason) -> dict:
    return {
        "dataset": col.dataset, "model": model, "variant": variant, "contrast": cid,
        "description": desc, "seed_set": seed_set, "role": role, "status": "not_computed",
        "reason": reason, "verdict": "not_computed",
    }  # fmt: skip


def _row(
    col: Collected,
    cid: str,
    desc: str,
    model: str,
    variant: str,
    seed_set: str,
    plus: tuple,
    minus: tuple,
    *,
    role: str,
    delay_units: int | None = None,
    n_boot: int = stats.N_BOOT,
) -> dict[str, Any]:
    a = _arm(col, variant, model, *plus)
    b = _arm(col, variant, model, *minus)
    if a is None or b is None:
        gone = [str(x) for x, arm in ((plus, a), (minus, b)) if arm is None]
        return _not_computed(col, cid, desc, model, variant, seed_set, role,
                             "arm not complete: " + "; ".join(gone))  # fmt: skip
    seeds = list(SEED_SETS[seed_set])
    short = [s for s in seeds if s not in a.columns or s not in b.columns]
    if short:
        return _not_computed(col, cid, desc, model, variant, seed_set, role,
                             f"seeds {short} missing from an arm")  # fmt: skip
    arrays, windows, used = stats.align_arms({"a": a, "b": b}, seeds=seeds)
    bl = block_len(col.geometry[variant])
    est = stats.difference(arrays, "a", "b", block_len=bl, n_boot=n_boot)
    p = stats.wilcoxon_p(stats.seed_paired_means(arrays, "a", "b"))
    n_plus = _queried(col, variant, model, plus, seeds)
    n_minus = _queried(col, variant, model, minus, seeds)
    d_labels = n_plus - n_minus
    row: dict[str, Any] = {
        "dataset": col.dataset, "model": model, "variant": variant, "contrast": cid,
        "description": desc, "seed_set": seed_set, "role": role, "status": "computed",
        "reason": "", "n_windows": len(windows), "n_seeds": len(used), "block_len": bl,
        "block_len_effective": stats.effective_block(bl, len(windows)),
        "window_stage_coarse": stats.window_stage_is_coarse(bl, len(windows)),
        "estimate": est.point, "ci_low": est.low, "ci_high": est.high,
        "boot_mean_minus_point": est.boot_mean - est.point,
        "half_width": est.half_width, "verdict": verdict(est),
        "detected": bool(est.low > 0.0), "within_margin": bool(
            est.low >= -MARGIN and est.high <= MARGIN
        ),
        "seed_level_wilcoxon_p": p, "min_wilcoxon_p": stats.min_wilcoxon_p(len(used)),
        "labels_per_slot_plus": n_plus, "labels_per_slot_minus": n_minus,
        "delay_axis_note": col.delay_axis_note if delay_units else "",
    }  # fmt: skip
    if delay_units:
        per = stats.scale(est, 1.0 / delay_units)
        row.update(unit="AUT lost per slot of delay", unit_value=per.point,
                   unit_low=per.low, unit_high=per.high)  # fmt: skip
    elif d_labels and not math.isnan(d_labels) and d_labels > 0:
        per = stats.scale(est, 100.0 / d_labels)
        row.update(
            unit="AUT gained per 100 extra labels per slot",
            unit_value=per.point,
            unit_low=per.low,
            unit_high=per.high,
            aut_per_label=est.point / d_labels,
        )
    return row


def contrasts_table(
    col: Collected, *, models: Sequence[str] | None = None, n_boot: int = stats.N_BOOT
) -> pd.DataFrame:
    """One row per registered contrast, model and seed set (``not_computed`` if an arm is missing).

    Holm is added by :func:`add_holm` over the fixed family of the whole study.
    """
    rows = []
    for model in models or col.models:
        for ss in SEED_SETS:
            role = "primary" if ss == "0-9" else "seed_robustness"
            for cid, desc, plus, minus, du in PRIMARY:
                rows.append(_row(col, cid, desc, model, "rolling", ss, plus, minus,
                                 role=role, delay_units=du, n_boot=n_boot))  # fmt: skip
    return pd.DataFrame(rows)


def add_holm(df: pd.DataFrame, datasets: Sequence[str], models: Sequence[str]) -> pd.DataFrame:
    """Holm step-down over the registered family (datasets x models x 4), fixed size.

    A contrast that was not computed enters with p = 1, so a partial grid cannot shrink the
    family. Only the 10-seed primary rows are adjusted: 5 seeds cannot go below 0.0625.
    """
    out = df.copy()
    out["seed_level_wilcoxon_p_holm"] = np.nan
    prim = out[(out["role"] == "primary")]
    expected = [(d, m, c[0]) for d in datasets for m in models for c in PRIMARY]
    ps = []
    for d, m, c in expected:
        r = prim[(prim["dataset"] == d) & (prim["model"] == m) & (prim["contrast"] == c)]
        ok = len(r) == 1 and r["status"].iloc[0] == "computed"
        ps.append(float(r["seed_level_wilcoxon_p"].iloc[0]) if ok else 1.0)
    adj = dict(zip(expected, stats.holm(ps), strict=True))
    for idx, r in prim.iterrows():
        k = (r["dataset"], r["model"], r["contrast"])
        if k in adj and r["status"] == "computed":
            out.loc[idx, "seed_level_wilcoxon_p_holm"] = adj[k]
    out["family_size"] = len(expected)
    return out


def secondary_table(
    col: Collected, *, models: Sequence[str] | None = None, n_boot: int = stats.N_BOOT
) -> pd.DataFrame:
    """Delay slopes per budget (5 seeds) and budget steps and concavity at d=0 (10 seeds)."""
    rows: list[dict[str, Any]] = []
    for model in models or col.models:
        bl = block_len(col.geometry.get("rolling", {"nE": 1, "stride": 1}))
        for b in BUDGETS:
            cells = {f"d{d}": _arm(col, "rolling", model, "periodic", d, b) for d in DELAYS}
            if any(v is None for v in cells.values()):
                continue
            seeds = list(SEED_SETS["0-4"])
            arrays, windows, used = stats.align_arms(cells, seeds=seeds)
            sl = stats.slope(
                arrays, {f"d{d}": float(d) for d in DELAYS}, block_len=bl, n_boot=n_boot
            )
            lost = stats.scale(sl, -1.0)
            rows.append(
                {
                    "dataset": col.dataset, "model": model, "kind": "delay_slope",
                    "role": "descriptive", "budget_pct": b, "delay": None, "seed_set": "0-4",
                    "n_windows": len(windows), "n_seeds": len(used),
                    "estimate": sl.point, "ci_low": sl.low, "ci_high": sl.high,
                    "unit": "AUT lost per slot of delay (positive = AUT falls)",
                    "unit_value": lost.point, "unit_low": lost.low, "unit_high": lost.high,
                    "labels_per_slot": _queried(col, "rolling", model, ("periodic", 0, b), seeds),
                    "delay_axis_note": col.delay_axis_note,
                }
            )  # fmt: skip
        names = {b: f"b{b:g}" for b in BUDGETS}
        cells = {names[b]: _arm(col, "rolling", model, "periodic", 0, b) for b in BUDGETS}
        if any(v is None for v in cells.values()):
            continue
        seeds = list(SEED_SETS["0-9"])
        try:
            arrays, windows, used = stats.align_arms(cells, seeds=seeds)
        except ValueError:
            continue
        rs = stats.resample_means(arrays, bl, n_boot=n_boot)
        pt = stats.arm_means(arrays)
        n = {b: _queried(col, "rolling", model, ("periodic", 0, b), seeds) for b in BUDGETS}
        gains: dict[tuple[float, float], tuple[float, np.ndarray]] = {}
        for lo, hi in [(0.5, 1.0), (1.0, 2.0), (2.0, 5.0)]:
            dn = n[hi] - n[lo]
            if not dn > 0:  # budgets that round to one count have no per-label unit
                continue
            point = (pt[names[hi]] - pt[names[lo]]) / dn * 100.0
            samp = (rs[names[hi]] - rs[names[lo]]) / dn * 100.0
            e = stats.estimate(point, samp)
            gains[(lo, hi)] = (point, samp)
            rows.append(
                {
                    "dataset": col.dataset, "model": model, "kind": "budget_step",
                    "role": "descriptive", "budget_pct": f"{lo:g}->{hi:g}", "delay": 0,
                    "seed_set": "0-9", "n_windows": len(windows), "n_seeds": len(used),
                    "estimate": point, "ci_low": e.low, "ci_high": e.high,
                    "unit": "AUT gained per 100 extra labels per slot",
                    "unit_value": point, "unit_low": e.low, "unit_high": e.high,
                    "labels_lo": n[lo], "labels_hi": n[hi], "labels_per_slot": dn,
                    "delay_axis_note": "",
                }
            )  # fmt: skip
        if (0.5, 1.0) in gains and (2.0, 5.0) in gains:
            first, last = gains[(0.5, 1.0)], gains[(2.0, 5.0)]
            e = stats.estimate(first[0] - last[0], first[1] - last[1])
            rows.append(
                {
                    "dataset": col.dataset, "model": model, "kind": "budget_concavity",
                    "role": "descriptive", "budget_pct": "gain(0.5->1) minus gain(2->5)",
                    "delay": 0, "seed_set": "0-9", "n_windows": len(windows),
                    "n_seeds": len(used), "estimate": e.point, "ci_low": e.low,
                    "ci_high": e.high,
                    "unit": "AUT per 100 labels (positive = diminishing returns)",
                    "unit_value": e.point, "unit_low": e.low, "unit_high": e.high,
                    "labels_lo": n[0.5], "labels_hi": n[5.0], "labels_per_slot": math.nan,
                    "delay_axis_note": "",
                }
            )  # fmt: skip
    return pd.DataFrame(rows)


def chow_table(
    col: Collected, *, models: Sequence[str] | None = None, n_boot: int = stats.N_BOOT
) -> pd.DataFrame:
    """The delay contrasts and periodic-minus-never at Chow's stride (seeds 0-4)."""
    rows = []
    for model in models or col.models:
        for cid, desc, plus, minus, du in PRIMARY[:3]:
            rows.append(_row(col, cid, desc, model, "rolling_chow", "0-4", plus, minus,
                             role="chow_secondary", delay_units=du, n_boot=n_boot))  # fmt: skip
    return pd.DataFrame(rows)


def labels_table(col: Collected) -> pd.DataFrame:
    """Absolute query counts, arrivals and retrains per arm and seed block (no AUT)."""
    rows = []
    for key in sorted(col.counts_blocks, key=_sort_key):
        variant, model, policy, delay, budget = key
        for seeds, c in col.counts_blocks[key]:
            rows.append(
                {"dataset": col.dataset, "variant": variant, "model": model, "policy": policy,
                 "delay": delay, "budget_pct": budget,
                 "seeds": f"{min(seeds)}-{max(seeds)}", **c}
            )  # fmt: skip
    return pd.DataFrame(rows)


def recovery_table(col: Collected) -> pd.DataFrame:
    """Drop events and recovery time per arm: descriptive (PREREG, D6)."""
    rows = []
    for key in sorted(col.f1, key=_sort_key):
        variant, model, policy, delay, budget = key
        events = recovered = 0
        recs: list[int] = []
        n_series = 0
        for _, g in col.f1[key].groupby(["seed", "window_key"], sort=False):
            series = g.sort_values("slot_index")["f1"].to_numpy()
            n_series += 1
            for ev in drop_events(series):
                events += 1
                if ev.recovery_slots is not None:
                    recovered += 1
                    recs.append(ev.recovery_slots)
        rows.append(
            {
                "dataset": col.dataset, "variant": variant, "model": model, "policy": policy,
                "delay": delay, "budget_pct": budget, "role": "descriptive",
                "n_series": n_series,
                "drop_events_per_series": events / n_series if n_series else math.nan,
                "share_recovered": recovered / events if events else math.nan,
                "mean_recovery_slots": float(np.mean(recs)) if recs else math.nan,
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


def per_slot_table(col: Collected) -> pd.DataFrame:
    """Mean F1 per slot position over windows and seeds, with the range over windows."""
    rows = []
    for key in sorted(col.f1, key=_sort_key):
        variant, model, policy, delay, budget = key
        if variant != "rolling":
            continue
        f = col.f1[key].copy()
        f["position"] = (
            f.groupby(["seed", "window_key"])["slot_index"].rank(method="first").astype(int)
        )
        by_w = f.groupby(["window_key", "position"])["f1"].mean().reset_index()
        g = by_w.groupby("position")["f1"].agg(["mean", "min", "max"]).reset_index()
        for _, r in g.iterrows():
            rows.append(
                {"dataset": col.dataset, "model": model, "policy": policy, "delay": delay,
                 "budget_pct": budget, "slot_position": int(r["position"]),
                 "mean_f1": float(r["mean"]), "min_f1": float(r["min"]),
                 "max_f1": float(r["max"])}
            )  # fmt: skip
    return pd.DataFrame(rows)


def ledger_table(col: Collected) -> pd.DataFrame:
    df = pd.DataFrame(col.cells)
    df.insert(0, "dataset", col.dataset)
    return df


# --- RQ1: both comparators from the E1 runs ---------------------------------------------------


def rq1_table(
    run_dir: Path | str, dataset: str, *, n_boot: int = stats.N_BOOT, band: float = BAND
) -> pd.DataFrame:
    """Per-slot matched gap (primary) and the E0 window-level gap (secondary), with intervals.

    The E0 window-level comparator is the prior-matched random-split F1 of the pooled window
    (``f1_random_split`` of the window table) minus the time-aware AUT, as in Table 1 and
    CLAIMS E-19. Its predictions are not stored, so it comes from the window table.
    """
    d = load_rq1_run(Path(run_dir))
    geom = _variant_geometry(d["config"], "rolling")
    bl = block_len(geom)
    rows = []
    for model in sorted(d["f1"]["model"].unique()):
        ta = stats.aut_matrix(d["f1"], model, series="time_aware", variant="rolling")
        rs = stats.aut_matrix(d["f1"], model, series="random_split", variant="rolling")
        arrays, windows, seeds = stats.align_arms({"rs": rs, "ta": ta})
        est = stats.difference(arrays, "rs", "ta", block_len=bl, n_boot=n_boot)
        rows.append(
            _rq1_row(
                dataset,
                model,
                "per-slot matched (primary)",
                est,
                len(windows),
                len(seeds),
                bl,
                band,
            )
        )
        w = d["windows"]
        w = w[(w["model"] == model) & (w["variant"] == "rolling")].copy()
        w["window_key"] = stats.window_key(w["window_id"].astype(str))
        win = w.pivot(index="window_key", columns="seed", values="f1_random_split")
        ta_aligned = ta.values.reindex(win.index)[win.columns]
        arr, wins, sds = stats.align_arms({"e0": win, "ta": ta_aligned})
        est0 = stats.difference(arr, "e0", "ta", block_len=bl, n_boot=n_boot)
        rows.append(
            _rq1_row(
                dataset, model, "E0 window-level (secondary)", est0, len(wins), len(sds), bl, band
            )
        )
    return pd.DataFrame(rows)


def _rq1_row(dataset, model, comparator, est, n_w, n_s, bl, band) -> dict[str, Any]:
    return {
        "dataset": dataset, "model": model, "comparator": comparator, "n_windows": n_w,
        "n_seeds": n_s, "block_len": bl, "gap": est.point, "ci_low": est.low,
        "ci_high": est.high, "band": band,
        "point_at_or_above_band": bool(est.point >= band),
        "lower_at_or_above_band": bool(est.low >= band),
        "role": "primary" if "primary" in comparator else "secondary",
    }  # fmt: skip


def load_rq1_run(run_dir: Path) -> dict[str, Any]:
    """An E1 run: both series from stored predictions, the slot and window tables."""
    record = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    preds = pq.read_table(run_dir / "predictions.parquet", columns=PRED_COLUMNS).to_pandas()
    slots = pd.read_parquet(run_dir / "slots.parquet")
    order = slots[["window_id", "slot_id", "slot_index"]].drop_duplicates()
    cells = stats.f1_per_slot(preds, order)
    return {
        "record": record,
        "config": record["config"],
        "f1": cells,
        "windows": pd.read_parquet(run_dir / "windows.parquet"),
    }


def discover_e1(root: Path | str, dataset: str) -> Path:
    """The single finished E1 run of a dataset under ``root`` (an ambiguity is an error)."""
    found = []
    for p in sorted(Path(root).glob("*/run.json")):
        rec = json.loads(p.read_text(encoding="utf-8"))
        cfg = rec.get("config", {})
        e0 = cfg.get("e0", {})
        if cfg.get("dataset") == dataset and e0.get("per_slot_random_split"):
            found.append(p.parent)
    if len(found) != 1:
        raise GridDataError(f"expected one E1 run for {dataset} under {root}, found {found}")
    return found[0]
