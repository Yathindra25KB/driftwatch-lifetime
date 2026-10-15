"""Uncertainty for the grid contrasts: two-stage bootstrap, Wilcoxon check, effect sizes.

Everything here works on matrices of AUT with one row per rolling window (time order) and one
column per seed. Arms of a comparison share windows and seeds (the same C3 draws), so every
contrast is paired cell by cell before anything is resampled.

The interval follows the pre-registration (docs/PREREG.md, RQ2): windows first, then seeds
within windows.

1. **Windows.** Rolling windows overlap (each evaluation slot sits in about ``nE / stride``
   windows), so a plain resample of windows would understate the spread. Windows are resampled
   in moving blocks of consecutive windows, block length ``ceil(nE / stride)``.
2. **Seeds.** Inside every selected window the seed columns are resampled with replacement,
   independently per window and replicate.

Resampling both levels counts the within-window variance twice, so for independent cells the
interval is conservative (about sqrt(2) wider when seed noise dominates); it is never
narrower than the plain standard error (tests/test_stats.py). That is the pre-registered
design, kept as specified; a narrower interval would need an addendum.

The same indices are used for every arm of one call, so differences, slopes and ratios of arm
means are paired in each replicate. The Wilcoxon signed-rank test is a supporting check on the
per-seed paired means, never a decision rule. Nothing here fits a model or reads a label.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from driftwatch.metrics.aut import aut

BOOT_SEED = 20261215  # fixed before any grid result; PREREG records it
N_BOOT = 10_000
LEVEL = 0.95


def block_length(n_eval: int, stride: int) -> int:
    """Windows that share an evaluation slot: ``ceil(nE / stride)``, at least 1."""
    if n_eval < 1 or stride < 1:
        raise ValueError("nE and stride must be at least 1")
    return max(1, -(-n_eval // stride))


# --- from stored predictions to AUT matrices --------------------------------------------------


def window_key(window_id: pd.Series) -> pd.Series:
    """``window_id`` embeds a spec digest that depends on the seed; the key is what follows."""
    return window_id.str.split("|", n=1).str[1]


def f1_per_slot(preds: pd.DataFrame, order: pd.DataFrame) -> pd.DataFrame:
    """Per-slot F1 per (model, seed, window, slot) from stored labels and decisions.

    ``preds`` needs ``model, seed, window_id, slot_id, y_true, pred``; ``order`` maps
    ``(window_id, slot_id)`` to ``slot_index`` (from the slot table), which fixes the time order.
    """
    flag = pd.DataFrame(
        {
            "model": preds["model"].to_numpy(),
            "seed": preds["seed"].to_numpy(),
            "window_id": preds["window_id"].to_numpy(),
            "slot_id": preds["slot_id"].to_numpy(),
            "tp": ((preds["y_true"] == 1) & (preds["pred"] == 1)).to_numpy(np.int64),
            "fp": ((preds["y_true"] == 0) & (preds["pred"] == 1)).to_numpy(np.int64),
            "fn": ((preds["y_true"] == 1) & (preds["pred"] == 0)).to_numpy(np.int64),
        }
    )
    keys = ["model", "seed", "window_id", "slot_id"]
    g = flag.groupby(keys, sort=False)[["tp", "fp", "fn"]].sum().reset_index()
    denom = 2 * g["tp"] + g["fp"] + g["fn"]
    g["f1"] = (2 * g["tp"] / denom.where(denom > 0)).fillna(0.0)
    g = g.merge(
        order[["window_id", "slot_id", "slot_index"]].drop_duplicates(),
        on=["window_id", "slot_id"],
        how="left",
        validate="m:1",
    )
    if g["slot_index"].isna().any():
        raise ValueError("stored predictions hold slots that the slot table does not list")
    g["window_key"] = window_key(g["window_id"])
    return g


@dataclass(frozen=True)
class AutMatrix:
    """AUT per (window, seed) of one model in one arm, windows in time order."""

    values: pd.DataFrame  # index: window_key (time order), columns: seed
    n_windows_undefined: int  # windows with fewer than two evaluation slots (excluded)


def aut_matrix(f1_cells: pd.DataFrame, model: str) -> AutMatrix:
    """AUT of each (window, seed) from per-slot F1 in time order; undefined windows are counted."""
    c = f1_cells[f1_cells["model"] == model]
    if c.empty:
        raise ValueError(f"no per-slot F1 for model {model!r}")
    rows: dict[tuple[str, int], float] = {}
    undefined: set[str] = set()
    for (wkey, seed), g in c.groupby(["window_key", "seed"], sort=False):
        f = g.sort_values("slot_index")["f1"].to_numpy()
        if f.size < 2:
            undefined.add(str(wkey))
            continue
        rows[(str(wkey), int(seed))] = aut(f)
    ser = pd.Series(rows, dtype=float)
    mat = ser.unstack(level=1)
    first_slot = c.groupby("window_key")["slot_index"].min()
    mat = mat.loc[first_slot.loc[mat.index].sort_values(kind="stable").index]
    mat = mat.reindex(sorted(mat.columns), axis=1)
    return AutMatrix(mat, len(undefined))


def align_arms(
    arms: Mapping[str, AutMatrix | pd.DataFrame], seeds: Sequence[int] | None = None
) -> tuple[dict[str, np.ndarray], list[str], list[int]]:
    """Common windows (time order of the first arm) and seeds as plain arrays, strictly.

    Arms must cover the same windows: a window present in one arm and missing in another is an
    error, not something to compress away. Seeds are cut to ``seeds`` (or the intersection).
    """
    frames = {k: (v.values if isinstance(v, AutMatrix) else v) for k, v in arms.items()}
    first = next(iter(frames.values()))
    windows = list(first.index)
    for name, frame in frames.items():
        if set(frame.index) != set(windows):
            raise ValueError(
                f"arm {name!r} covers other windows than the first arm: "
                f"{sorted(set(frame.index) ^ set(windows))}"
            )
    if seeds is None:
        common = set(first.columns)
        for frame in frames.values():
            common &= set(frame.columns)
        seeds = sorted(common)
    seeds = list(seeds)
    out: dict[str, np.ndarray] = {}
    for name, frame in frames.items():
        missing = [s for s in seeds if s not in frame.columns]
        if missing:
            raise ValueError(f"arm {name!r} has no seed(s) {missing}")
        block = frame.loc[windows, seeds].to_numpy(dtype=np.float64)
        if not np.isfinite(block).all():
            raise ValueError(f"arm {name!r} has missing AUT cells inside the window x seed grid")
        out[name] = block
    return out, windows, seeds


# --- resampling -------------------------------------------------------------------------------


def resample_means(
    arms: Mapping[str, np.ndarray],
    block_len: int,
    *,
    n_boot: int = N_BOOT,
    seed: int = BOOT_SEED,
) -> dict[str, np.ndarray]:
    """Mean of each arm in every replicate: moving blocks of windows, then seeds within windows.

    All arms are cut with the same indices, so a statistic built from the arm means is paired.
    """
    names = list(arms)
    shape = arms[names[0]].shape
    if len(shape) != 2:
        raise ValueError("arms must be (windows, seeds) matrices")
    for name in names:
        if arms[name].shape != shape:
            raise ValueError(f"arm {name!r} has shape {arms[name].shape}, expected {shape}")
    n_w, n_s = shape
    if n_w < 1 or n_s < 1:
        raise ValueError("need at least one window and one seed")
    rng = np.random.default_rng(seed)
    b = int(min(max(block_len, 1), n_w))
    n_blocks = -(-n_w // b)
    starts = rng.integers(0, n_w - b + 1, size=(n_boot, n_blocks))
    win = (starts[:, :, None] + np.arange(b)[None, None, :]).reshape(n_boot, -1)[:, :n_w]
    cols = rng.integers(0, n_s, size=(n_boot, n_w, n_s))
    return {name: arms[name][win[:, :, None], cols].mean(axis=(1, 2)) for name in names}


def interval(samples: np.ndarray, level: float = LEVEL) -> tuple[float, float]:
    """Percentile interval of bootstrap replicates."""
    tail = (1.0 - level) / 2.0 * 100.0
    low, high = np.percentile(samples, [tail, 100.0 - tail])
    return float(low), float(high)


def arm_means(arms: Mapping[str, np.ndarray]) -> dict[str, float]:
    """Point estimate: mean over windows of the mean over seeds."""
    return {k: float(v.mean(axis=1).mean()) for k, v in arms.items()}


# --- contrasts and effect sizes ---------------------------------------------------------------


@dataclass(frozen=True)
class Estimate:
    point: float
    low: float
    high: float

    @property
    def half_width(self) -> float:
        return (self.high - self.low) / 2.0

    def excludes_zero(self) -> bool:
        return self.low > 0.0 or self.high < 0.0


def estimate(point: float, samples: np.ndarray, level: float = LEVEL) -> Estimate:
    low, high = interval(samples, level)
    return Estimate(float(point), low, high)


def difference(
    arms: Mapping[str, np.ndarray], plus: str, minus: str, *, block_len: int, **kw
) -> Estimate:
    """Mean of ``plus`` minus mean of ``minus``, paired, with its two-stage interval."""
    rs = resample_means({plus: arms[plus], minus: arms[minus]}, block_len, **kw)
    pt = arm_means({plus: arms[plus], minus: arms[minus]})
    return estimate(pt[plus] - pt[minus], rs[plus] - rs[minus])


def slope(
    arms: Mapping[str, np.ndarray],
    x: Mapping[str, float],
    *,
    block_len: int,
    **kw,
) -> Estimate:
    """OLS slope of the arm means against ``x`` (for example AUT per slot of delay)."""
    names = list(x)
    xs = np.array([x[n] for n in names], dtype=np.float64)
    if np.ptp(xs) == 0:
        raise ValueError("a slope needs at least two distinct x values")
    w = (xs - xs.mean()) / ((xs - xs.mean()) ** 2).sum()
    rs = resample_means({n: arms[n] for n in names}, block_len, **kw)
    pt = arm_means({n: arms[n] for n in names})
    point = float(sum(w[i] * pt[n] for i, n in enumerate(names)))
    samples = sum(w[i] * rs[n] for i, n in enumerate(names))
    return estimate(point, np.asarray(samples))


def scale(est: Estimate, factor: float) -> Estimate:
    """Change units (per slot of delay, per 100 labels): a positive factor keeps the order."""
    if factor < 0:
        low, high = est.high * factor, est.low * factor
    else:
        low, high = est.low * factor, est.high * factor
    return Estimate(est.point * factor, low, high)


def seed_paired_means(arms: Mapping[str, np.ndarray], plus: str, minus: str) -> np.ndarray:
    """Per-seed paired difference averaged over windows (the units of the Wilcoxon check)."""
    return (arms[plus] - arms[minus]).mean(axis=0)


def wilcoxon_p(differences: np.ndarray) -> float:
    """Two-sided Wilcoxon signed-rank p-value; 1.0 when every difference is exactly zero."""
    d = np.asarray(differences, dtype=np.float64)
    if d.size == 0:
        raise ValueError("no paired differences")
    if not np.any(d != 0.0):
        return 1.0
    return float(scipy_stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided").pvalue)


def holm(p_values: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values, returned in the input order."""
    p = np.asarray(p_values, dtype=np.float64)
    m = p.size
    order = np.argsort(p, kind="stable")
    adjusted = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adjusted[idx] = min(1.0, running)
    return [float(v) for v in adjusted]


def min_wilcoxon_p(n_pairs: int) -> float:
    """Smallest two-sided p an exact signed-rank test can return with ``n_pairs`` pairs."""
    if n_pairs < 1:
        raise ValueError("need at least one pair")
    return 2.0 / (2.0**n_pairs) if n_pairs < 1024 else math.nan
