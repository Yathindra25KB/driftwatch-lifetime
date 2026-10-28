"""E4 tables from stored predictions: policies, RQ4 contrasts, monitor quality, ledger.

The registered quantities are in docs/prereg/addendum-v3.md. Per dataset x model, monitor
``m`` and delay ``d``:

- ``M-P(m, d) = A-AUT(monitor-m, d) - A-AUT(periodic, d)``: at matched labels spent (every arm
  uses the random selector with the same seeded draws; checked here slot by slot);
- ``M-C(m, d) = A-AUT(monitor-m, d) - A-AUT(matched-m, d)``: at matched number of retrains
  (the matched arm copies the monitor arm's refit count per window, spread evenly).

A positive value favours the monitor. Intervals are the two-stage bootstrap of v1; Holm is
applied within each family (M-P and M-C separately) over datasets x models x monitors x
delays. Monitor quality (alarm precision, recall, detection delay against drop events from
true labels) is read from the never cell, where all monitors observe with the initial
reference (primary), and from each monitor arm's own alarms (secondary).

Nothing is fitted here and no model code is imported.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from driftwatch.metrics import stats
from driftwatch.metrics.grid_tables import MARGIN, GridDataError, block_len, load_cell, verdict
from driftwatch.metrics.monitor_scores import AlarmCounts, score_alarms
from driftwatch.metrics.slot import drop_events
from driftwatch.sim.ledger import fold_events, merged_ledger_events

MONITORS = ("ks", "mmd", "domain_clf", "p_uniformity")
REGISTERED_SEEDS = tuple(range(10))  # addendum v3: seeds 0 to 9 for every E4 cell
MIN_DROP_WINDOWS = 3  # fewer windows with a drop event: counts only, no interval (stats review)
MAX_DROPPED_SHARE = 0.025  # flag a ratio interval that lost more replicates than this


def e4_verdict(est: stats.Estimate) -> str:
    """The v1 reading, with a reversal inside the margin named as such (stats review E4 #3)."""
    v = verdict(est)
    if v == "reversed" and est.low >= -MARGIN:
        return "reversed_within_margin"  # no change larger than 0.01, interval below zero
    return v


ArmKey = tuple[str, str, int | None]  # model, arm label, delay (None for never)


def _seed_set(frame: pd.DataFrame) -> str:
    """The seeds an arm was run with, as "first-last" (or a list when not contiguous)."""
    s = sorted(int(c) for c in frame.columns)
    return f"{s[0]}-{s[-1]}" if s == list(range(s[0], s[-1] + 1)) else "_".join(map(str, s))


def _arm_label(cfg: dict[str, Any]) -> str:
    pol = cfg.get("policy")
    if isinstance(pol, dict):
        name = pol["name"]
        return f"{name}-{pol['trigger']}" if name in ("monitor", "matched") else name
    return str(pol)


class E4Collected:
    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        self.arms: dict[ArmKey, pd.DataFrame] = {}  # AUT (window x seed)
        self.slots: dict[ArmKey, pd.DataFrame] = {}  # slot rows with F1 and alarm columns
        self.windows: dict[ArmKey, pd.DataFrame] = {}  # window rows (refits, matched k)
        self.geometry: dict[str, int] = {}
        self.cells: list[dict[str, Any]] = []
        self.models: list[str] = []
        self.versions: set[str] = set()


def collect(
    root: Path | str, dataset: str, *, planned: Sequence[str] = (), allow_mixed: bool = False
) -> E4Collected:
    root = Path(root)
    state = fold_events(merged_ledger_events(root), planned)
    col = E4Collected(dataset)
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
        w = cfg["window"]
        col.geometry = {"nT": w["nT"], "nE": w["nE"], "stride": w["stride"]}
        arm = _arm_label(cfg)
        delay = None if arm == "never" else int(cfg["delay"])
        for model in sorted(d["f1"]["model"].unique()):
            key: ArmKey = (model, arm, delay)
            aut = stats.aut_matrix(d["f1"], model, variant="rolling").values
            s = d["slots"][d["slots"]["model"] == model].copy()
            s["window_key"] = stats.window_key_of(s["window_id"])
            w_rows = d["windows"][d["windows"]["model"] == model].copy()
            if key in col.arms:  # the same arm under another seed set (seeds 0-4 and 5-9)
                if set(aut.columns) & set(col.arms[key].columns):
                    raise GridDataError(f"arm {key}: a seed appears in two cells")
                if set(aut.index) != set(col.arms[key].index):
                    raise GridDataError(f"arm {key}: the seed sets cover different windows")
                aut = pd.concat([col.arms[key], aut], axis=1).sort_index(axis=1)
                s = pd.concat([col.slots[key], s], ignore_index=True)
                w_rows = pd.concat([col.windows[key], w_rows], ignore_index=True)
            col.arms[key], col.slots[key], col.windows[key] = aut, s, w_rows
            if model not in col.models:
                col.models.append(model)
        del d
    if len(col.versions) > 1 and not allow_mixed:
        raise GridDataError(
            f"{dataset}: E4 cells completed at several code versions {sorted(col.versions)}"
        )
    col.models.sort()
    return col


def check_equal_labels(col: E4Collected) -> list[str]:
    """Every arm of a model queried the same number of labels in every (seed, window, slot)."""
    problems = []
    index = ["seed", "window_key", "slot_id"]
    for model in col.models:
        keys = [k for k in col.slots if k[0] == model]
        if not keys:
            continue
        base = col.slots[keys[0]].set_index(index)["n_queried"]
        for k in keys[1:]:
            q = col.slots[k].set_index(index)["n_queried"]
            both = base.index.intersection(q.index)
            if (
                len(both) != len(base)
                or len(q) != len(base)
                or (base.loc[both] != q.loc[both]).any()
            ):
                problems.append(f"{model}: labels per slot differ between {keys[0]} and {k}")
    return problems


def _per_window(s: pd.DataFrame) -> pd.DataFrame:
    g = s.groupby(["seed", "window_key"])
    return pd.DataFrame(
        {
            "labels": g["n_queried"].sum(),
            "refits": g["retrained"].sum(),
            "events": g["retrain_event"].sum(),
        }
    )


def policies_table(col: E4Collected) -> pd.DataFrame:
    rows = []
    for key in sorted(col.arms, key=lambda k: (k[0], k[1], -1 if k[2] is None else k[2])):
        model, arm, d = key
        frame = col.arms[key]
        s = col.slots[key]
        pw = _per_window(s)
        rows.append(
            {
                "dataset": col.dataset, "model": model, "arm": arm, "delay": d,
                "seed_set": _seed_set(frame), "n_windows": frame.shape[0],
                "n_seeds": frame.shape[1],
                "a_aut_mean": float(frame.mean(axis=1).mean()),
                "a_aut_std": float(frame.std(axis=0, ddof=1).mean())
                if len(frame) > 1 else math.nan,
                "labels_per_slot": float(s["n_queried"].mean()),
                "labels_per_window": float(pw["labels"].mean()),
                "refits_per_window": float(pw["refits"].mean()),
                "events_per_window": float(pw["events"].mean()),
                "noops_per_window": float((pw["events"] - pw["refits"]).mean()),
            }
        )  # fmt: skip
    return pd.DataFrame(rows)


def _contrast(col, model, plus: ArmKey, minus: ArmKey, family: str, monitor: str, d: int,
              n_boot: int) -> dict[str, Any]:  # fmt: skip
    base = {"dataset": col.dataset, "model": model, "family": family, "monitor": monitor,
            "delay": d, "contrast": f"{family}({monitor}, d={d})",
            "plus_arm": plus[1], "minus_arm": minus[1]}  # fmt: skip
    if plus not in col.arms or minus not in col.arms:
        return {**base, "status": "not_computed", "reason": "an arm is missing",
                "verdict": "not_computed", "seed_level_wilcoxon_p": 1.0}  # fmt: skip
    pair = {"p": col.arms[plus], "m": col.arms[minus]}
    try:  # the registered seeds; anything less is the registered fallback and says so
        arrays, windows, used = stats.align_arms(pair, seeds=list(REGISTERED_SEEDS))
        fallback = False
    except ValueError:
        arrays, windows, used = stats.align_arms(pair)
        fallback = True
    base["seed_set"] = _seed_set(col.arms[plus][used])
    bl = block_len(col.geometry)
    rs = stats.resample_means(arrays, bl, n_boot=n_boot)
    pt = stats.arm_means(arrays)
    est = stats.estimate(pt["p"] - pt["m"], rs["p"] - rs["m"])
    per_seed = (arrays["p"] - arrays["m"]).mean(axis=0)
    pw_p, pw_m = _per_window(col.slots[plus]), _per_window(col.slots[minus])
    same_schedule = _schedule_identity(col.slots[plus], col.slots[minus])
    v = e4_verdict(est)
    if family == "M-C" and same_schedule == 1.0:
        v = "not_informative_identical_schedule"  # the control refits at the monitor's slots
    return {
        **base, "status": "computed", "reason": "", "n_windows": len(windows),
        "n_seeds": len(used), "seed_fallback": fallback, "block_len": bl,
        "block_len_effective": stats.effective_block(bl, len(windows)),
        "window_stage_coarse": stats.window_stage_is_coarse(bl, len(windows)),
        "n_boot": n_boot, "boot_seed": stats.BOOT_SEED,
        "estimate": est.point, "ci_low": est.low, "ci_high": est.high,
        "boot_mean_minus_point": est.boot_mean - est.point,
        "half_width": est.half_width, "verdict": v,
        "identical_schedule_share": same_schedule,
        "seed_level_wilcoxon_p": stats.wilcoxon_p(per_seed),
        "min_wilcoxon_p": stats.min_wilcoxon_p(len(used)),
        "a_aut_plus": pt["p"], "a_aut_minus": pt["m"],
        "refits_per_window_plus": float(pw_p["refits"].mean()),
        "refits_per_window_minus": float(pw_m["refits"].mean()),
        "labels_per_window_plus": float(pw_p["labels"].mean()),
        "labels_per_window_minus": float(pw_m["labels"].mean()),
        **_shortfall(col.windows.get(minus)),
    }  # fmt: skip


def _schedule_identity(a: pd.DataFrame, b: pd.DataFrame) -> float:
    """Share of (seed, window) pairs in which two arms refitted at exactly the same slots."""

    def schedules(s: pd.DataFrame) -> pd.Series:
        r = s[s["retrained"].astype(bool)]
        sched = r.groupby(["seed", "window_key"])["slot_index"].apply(lambda x: tuple(sorted(x)))
        keys = s[["seed", "window_key"]].drop_duplicates().set_index(["seed", "window_key"])
        return sched.reindex(keys.index).apply(lambda x: x if isinstance(x, tuple) else ())

    sa, sb = schedules(a), schedules(b)
    both = sa.index.intersection(sb.index)
    if not len(both):
        return math.nan
    return float((sa.loc[both] == sb.loc[both]).mean())


def _shortfall(windows: pd.DataFrame | None) -> dict[str, Any]:
    """For a matched arm: windows whose control made fewer refits than its source monitor."""
    if windows is None or "matched_refit_shortfall" not in windows.columns:
        return {}
    short = windows["matched_refit_shortfall"].astype(float)
    return {
        "matched_shortfall_window_share": float((short > 0).mean()),
        "matched_shortfall_mean": float(short.mean()),
    }


def contrasts_table(col: E4Collected, *, n_boot: int = stats.N_BOOT) -> pd.DataFrame:
    delays = sorted({k[2] for k in col.arms if k[2] is not None})
    rows = []
    for model in col.models:
        for m in MONITORS:
            for d in delays:
                mon = (model, f"monitor-{m}", d)
                rows.append(_contrast(col, model, mon, (model, "periodic", d), "M-P", m, d, n_boot))
                rows.append(_contrast(col, model, mon, (model, f"matched-{m}", d), "M-C", m, d,
                                      n_boot))  # fmt: skip
    out = pd.DataFrame(rows)
    if not out.empty:  # monitors whose arms are identical: one comparison, not several
        out["same_arm_as"] = [
            ",".join(
                m for m in MONITORS
                if m != r.monitor
                and (r.model, f"monitor-{m}", r.delay) in col.arms
                and (r.model, f"monitor-{r.monitor}", r.delay) in col.arms
                and col.arms[(r.model, f"monitor-{m}", r.delay)].equals(
                    col.arms[(r.model, f"monitor-{r.monitor}", r.delay)])
            )
            for r in out.itertuples()
        ]  # fmt: skip
    return out


def add_holm(df: pd.DataFrame, datasets: Sequence[str], models: Sequence[str],
             delays: Sequence[int]) -> pd.DataFrame:  # fmt: skip
    """Holm within each family over datasets x models x monitors x delays (missing at p = 1)."""
    out = df.copy()
    out["seed_level_wilcoxon_p_holm"] = np.nan
    for fam in ("M-P", "M-C"):
        expected = [(ds, mo, m, d) for ds in datasets for mo in models for m in MONITORS
                    for d in delays]  # fmt: skip
        ps = []
        for ds, mo, m, d in expected:
            r = out[(out["family"] == fam) & (out["dataset"] == ds) & (out["model"] == mo)
                    & (out["monitor"] == m) & (out["delay"] == d)]  # fmt: skip
            ps.append(float(r["seed_level_wilcoxon_p"].iloc[0]) if len(r) == 1 else 1.0)
        adj = dict(zip(expected, stats.holm(ps), strict=True))
        for idx, r in out[out["family"] == fam].iterrows():
            k = (r["dataset"], r["model"], r["monitor"], r["delay"])
            if k in adj:
                out.loc[idx, "seed_level_wilcoxon_p_holm"] = adj[k]
        out.loc[out["family"] == fam, "family_size"] = len(expected)
    return out


# --- monitor quality --------------------------------------------------------------------------

_COUNT_FIELDS = ("n_drops", "n_alarms", "n_true_alarms", "n_detected", "delay_sum", "n_slots")


def _count_matrices(s: pd.DataFrame, monitor: str) -> tuple[dict[str, pd.DataFrame], dict]:
    """Per (window, seed) alarm counts of one monitor against the arm's own F1 series.

    Also returns, for the exploratory baselines and the drop-window count: the distinct
    (window, slot) positions of drop events, the alarms an always-alarming monitor would score
    as matched, and for every drop the number of scored slots that could match it.
    """
    col_alarm = f"alarm_{monitor}"
    recs: dict[tuple[str, int], AlarmCounts] = {}
    drop_at: set[tuple[str, int]] = set()
    always_true, always_n, matchable = 0, 0, []
    for (wkey, seed), g in s.groupby(["window_key", "seed"], sort=False):
        g = g.sort_values("slot_index")
        f1 = g["f1"].to_numpy()
        fired = g[col_alarm].fillna(False).to_numpy(bool)
        recs[(str(wkey), int(seed))] = score_alarms(f1, fired)
        always = score_alarms(f1, np.ones(len(f1), dtype=bool))
        always_true += always.n_true_alarms
        always_n += always.n_alarms
        slot_idx = g["slot_index"].to_numpy()
        for ev in drop_events(f1):
            drop_at.add((str(wkey), int(slot_idx[ev.index])))
            matchable.append(min(ev.index + 2, len(f1) - 1) - ev.index + 1)
    first = s.groupby("window_key")["slot_index"].min().sort_values(kind="stable")
    out = {}
    for i, f in enumerate(_COUNT_FIELDS):
        ser = pd.Series({k: v.as_tuple()[i] for k, v in recs.items()}, dtype=float)
        mat = ser.unstack(level=1)
        out[f] = mat.loc[[w for w in first.index.astype(str) if w in mat.index]]
    extra = {"drop_at": drop_at, "always_true": always_true, "always_n": always_n,
             "matchable": matchable}  # fmt: skip
    return out, extra


def _ratio_estimate(rs: dict[str, np.ndarray], num: str, den: str, point: float,
                    keep: np.ndarray) -> tuple[float, float, float]:  # fmt: skip
    """Point and percentile interval over the kept replicates (one rule for every ratio)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        r = (rs[num] / rs[den])[keep]
    r = r[np.isfinite(r)]
    if not np.isfinite(point) or r.size == 0:
        return math.nan, math.nan, math.nan
    lo, hi = stats.interval(r)
    return point, lo, hi


def _quality_row(col, model, monitor, context, key: ArmKey, n_boot: int) -> dict[str, Any]:
    s = col.slots[key]
    base = {"dataset": col.dataset, "model": model, "monitor": monitor, "context": context,
            "arm": key[1], "delay": key[2], "seed_set": _seed_set(col.arms[key])}  # fmt: skip
    if f"alarm_{monitor}" not in s.columns:
        return {**base, "status": "not_computed", "reason": "monitor not run in this arm"}
    mats, extra = _count_matrices(s, monitor)
    total = AlarmCounts(*(int(mats[f].to_numpy().sum()) for f in _COUNT_FIELDS))
    arrays = {f: mats[f].to_numpy(dtype=np.float64) for f in _COUNT_FIELDS}
    drop_windows = len({w for w, _ in extra["drop_at"]})
    rate = total.alarm_rate
    # exploratory baselines (not registered): an always-alarming monitor's precision, and the
    # expected recall of random alarms at this monitor's alarm rate
    always_prec = extra["always_true"] / extra["always_n"] if extra["always_n"] else math.nan
    m = np.asarray(extra["matchable"], dtype=float)
    random_recall = float(np.mean(1.0 - (1.0 - rate) ** m)) if m.size else math.nan
    row = {
        **base, "status": "computed", "reason": "",
        "n_windows": arrays["n_drops"].shape[0], "n_seeds": arrays["n_drops"].shape[1],
        "n_drops": total.n_drops, "n_distinct_drop_slots": len(extra["drop_at"]),
        "n_windows_with_drops": drop_windows,
        "n_alarms": total.n_alarms, "n_true_alarms": total.n_true_alarms,
        "n_detected": total.n_detected, "n_scored_slots": total.n_slots,
        "alarm_rate": rate,
        "precision": total.precision, "recall": total.recall, "mean_delay": total.mean_delay,
        "baseline_always_alarm_precision": always_prec,
        "baseline_random_recall_at_rate": random_recall,
        "undecided_share": float(1.0 - s[f"decided_{monitor}"].astype(bool).mean()),
    }  # fmt: skip
    if drop_windows < MIN_DROP_WINDOWS:
        return {**row, "intervals": f"none: drops in {drop_windows} window(s) only",
                "n_boot": n_boot, "n_boot_used": 0}  # fmt: skip
    rs = stats.resample_means(arrays, block_len(col.geometry), n_boot=n_boot)
    keep = (rs["n_drops"] > 0) & (rs["n_alarms"] > 0)  # one replicate set for every ratio
    _, p_lo, p_hi = _ratio_estimate(rs, "n_true_alarms", "n_alarms", total.precision, keep)
    _, r_lo, r_hi = _ratio_estimate(rs, "n_detected", "n_drops", total.recall, keep)
    _, d_lo, d_hi = _ratio_estimate(rs, "delay_sum", "n_detected", total.mean_delay, keep)
    used = int(keep.sum())
    return {
        **row, "intervals": "two-stage bootstrap",
        "n_boot": n_boot, "n_boot_used": used,
        "boot_dropped_flag": bool(1.0 - used / n_boot > MAX_DROPPED_SHARE),
        "precision_ci_low": p_lo, "precision_ci_high": p_hi,
        "recall_ci_low": r_lo, "recall_ci_high": r_hi,
        "delay_ci_low": d_lo, "delay_ci_high": d_hi,
    }  # fmt: skip


def monitors_table(col: E4Collected, *, n_boot: int = stats.N_BOOT) -> pd.DataFrame:
    rows = []
    for model in col.models:
        never = (model, "never", None)
        for m in MONITORS:
            if never in col.slots:
                rows.append(_quality_row(col, model, m, "observe_never", never, n_boot))
            for key in sorted(k for k in col.slots if k[0] == model and k[1] == f"monitor-{m}"):
                rows.append(_quality_row(col, model, m, "trigger_arm", key, n_boot))
    return pd.DataFrame(rows)


def ledger_table(col: E4Collected) -> pd.DataFrame:
    return pd.DataFrame([{"dataset": col.dataset, **c} for c in col.cells])


__all__ = [
    "E4Collected",
    "add_holm",
    "check_equal_labels",
    "collect",
    "contrasts_table",
    "ledger_table",
    "monitors_table",
    "policies_table",
]
