"""The experiment runner: the E0 baseline (Phase 4) and the label-delay simulator (Phase 5).

For each variant, seed and window (one *unit*, checkpointed so a killed run resumes) the
runner

1. fits every model once on the window's raw training rows (labels allowed there); the fit
   comes from :class:`InitialModelCache`, keyed by (dataset, training window, model, seed);
2. streams the evaluation slots in time order and scores each on
   :meth:`~driftwatch.data.slicer.EvalSlot.public` only, through
   :class:`~driftwatch.sim.queue.SealedSlot`, the single door to true labels;
3. computes per-slot F1, FPR and FNR from the true labels (metric code only) and the
   window's AUT;
4. optionally refits on a random split of the same pooled rows (same training size, malware
   test rows subsampled to the same ratio) to get the random-split F1 a time-blind evaluation
   would report, and, for E1, that comparator's predictions per evaluation slot.

Two loops share the units, the store and the hashing:

- baseline (``selector`` null): one fixed model per window, never retrained (E0, E1);
- simulation (``selector`` set): per slot, release arrived labels (queue), retrain if the
  policy says so and new labels exist (pool), score, then spend the budget (selector, queue).
  ``never`` under a simulation config equals the baseline, whatever delay and budget say.

Variants (ADR-0005, ADR-0006): ``rolling`` (ADR-0005 stride, headline), ``rolling_chow``
(stride ``min(nT, nE)`` as in Chow et al.), ``sensitivity`` (rolling windows planned at the
sensitivity ratio) and ``single_run`` (train on the first nT slots of a run, evaluate the
rest). A fit is identified by (model, seed if the model uses it, training slots), so the same
training window under another variant, seed or run is not refitted when the fit cannot differ.

Parallelism is across runs (:func:`run_many`, one thread per run), never inside one. The
label delay lives only in sim/queue.py (hard rule 3).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import threading
import time
import traceback
import zlib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import psutil

from driftwatch.data import constraints
from driftwatch.data.cache import code_version
from driftwatch.data.memory import MemoryWatchdog
from driftwatch.data.slicer import (
    SlotSource,
    Window,
    WindowSpec,
    _stack,
    slice_windows,
)
from driftwatch.metrics.aut import aut, chow_stride
from driftwatch.metrics.slot import SlotScores, drop_events, score_slot
from driftwatch.models import make_model
from driftwatch.models.base import Detector
from driftwatch.sim.config import RunConfig, config_hash, lock_sha256, package_versions
from driftwatch.sim.policies import Policy, make_policy
from driftwatch.sim.pool import TrainingPool
from driftwatch.sim.queue import LabelQueue, SealedSlot
from driftwatch.sim.results import ARM_DEFAULTS, PredictionHasher, ResultStore
from driftwatch.sim.selectors import (
    Selector,
    budget_count,
    calibration_count,
    make_selector,
    selector_rng,
)

log = logging.getLogger(__name__)

_RANDOM_TAG = 0x72616E64  # separates the random-split draw from every other seeded draw
DEFAULT_MEMORY_CAP = int(1.5 * 1024**3)  # approved for this 8 GB laptop in Phase 2


@dataclass(frozen=True)
class RunSummary:
    dir: Path
    config_hash: str
    predictions_sha256: str
    n_windows: int
    n_slot_rows: int
    n_prediction_rows: int
    wall_s: float


class InitialModelCache:
    """Initial models by sub-hash of (dataset, training window, model spec, seed).

    In-process and thread-safe with single-flight fitting: when two runs ask for the same
    initial model at once, one fits and the other waits. Models are never pickled to disk.
    The seed is part of the key only for models that use it.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._models: dict[str, Detector] = {}
        self._key_locks: dict[str, threading.Lock] = {}

    @staticmethod
    def key(
        dataset: str,
        train_key: str,
        model_spec: dict[str, Any],
        seed: int | None,
        rows_digest: str = "",
    ) -> str:
        """``rows_digest`` binds the key to the training rows, not only to their slot ids."""
        body = json.dumps(
            [dataset, train_key, model_spec, seed, rows_digest], sort_keys=True, default=str
        )
        return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]

    def get_or_fit(self, key: str, fit: Callable[[], Detector]) -> tuple[Detector, bool]:
        """(detector, reused). ``fit`` runs at most once per key."""
        with self._lock:
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:
            cached = self._models.get(key)
            if cached is not None:
                return cached, True
            det = fit()
            self._models[key] = det
            return det, False


@dataclass
class _Ctx:
    cfg: RunConfig
    source: SlotSource
    store: ResultStore
    write: Any
    hasher: PredictionHasher
    cell_hashers: dict[str, PredictionHasher]
    cache: InitialModelCache
    n_windows: int = 0
    n_slot_rows: int = 0


def _spec_for(cfg: RunConfig, variant: str, seed: int) -> WindowSpec:
    common = {"min_malware": cfg.min_malware, "seed": seed}
    if variant == "rolling":
        return WindowSpec(cfg.nT, cfg.nE, cfg.stride, cfg.target_ratio, **common)
    if variant == "rolling_chow":
        return WindowSpec(cfg.nT, cfg.nE, chow_stride(cfg.nT, cfg.nE), cfg.target_ratio, **common)
    if variant == "sensitivity":
        assert cfg.sensitivity_ratio is not None
        return WindowSpec(cfg.nT, cfg.nE, cfg.stride, cfg.sensitivity_ratio, **common)
    if variant == "single_run":
        return WindowSpec(cfg.nT, None, 1, cfg.target_ratio, **common)
    raise ValueError(variant)


# --- cells, hashing, emitting ----------------------------------------------------------------


def _arm(cfg: RunConfig, series: str = "time_aware") -> dict[str, Any]:
    """The columns that say which simulator settings (if any) a row belongs to."""
    if not cfg.is_simulation:
        return {**ARM_DEFAULTS, "series": series}
    return {
        "series": series,
        "policy": cfg.policy,
        "selector": cfg.selector,
        "delay": cfg.delay,
        "budget_pct": cfg.budget_pct,
    }


def _cell(key: dict[str, Any]) -> str:
    """Hash-cell label. Baseline rows keep the Phase 4 form so E0 hashes stay comparable."""
    base = f"{key['variant']}|{key['model']}|{key['ratio']}|{key['seed']}"
    delay = key.get("delay")
    arm = (
        key.get("series", ARM_DEFAULTS["series"]),
        key.get("policy", ARM_DEFAULTS["policy"]),
        key.get("selector"),
        None if delay is None else int(delay),
        key.get("budget_pct"),
    )
    if arm == tuple(ARM_DEFAULTS.values()):
        return base
    return base + "|" + "|".join(str(x) for x in arm)


def _feed(ctx: _Ctx, key: dict[str, Any], row_id: np.ndarray, pred: np.ndarray, proba) -> None:
    cell = _cell(key)
    for hasher in (ctx.hasher, ctx.cell_hashers.setdefault(cell, PredictionHasher())):
        hasher.update(cell, key["window_id"], key["slot_id"], row_id, pred, proba)


def _emit(
    ctx: _Ctx,
    key: dict[str, Any],
    *,
    row_id: np.ndarray,
    y_true: np.ndarray,
    proba: np.ndarray,
    pred: np.ndarray,
) -> None:
    ctx.write(key, row_id=row_id, y_true=y_true, proba=proba, pred=pred)
    _feed(ctx, key, row_id, pred, proba)


def _replay(ctx: _Ctx) -> None:
    """A unit finished in an earlier run: rebuild its hashes and counters, compute nothing."""
    for block in ctx.store.unit_blocks():
        _feed(ctx, block.key, block.row_id, block.pred, block.proba)
    ctx.n_slot_rows += ctx.store.unit_n_slots
    ctx.n_windows += ctx.store.unit_n_windows


# --- random-split comparator -----------------------------------------------------------------

PerSlot = Callable[..., None]


def _random_split(
    ctx: Any,
    window: Window,
    spec: WindowSpec,
    seed: int,
    n_train_malware: int,
    per_slot: PerSlot | None = None,
) -> dict[str, dict[int, dict[str, Any]]]:
    """Random-split comparators on the window's pooled rows (they violate C1 by design).

    Two draws, both with the time-aware window's training size, both tested on the rest of
    the pool with malware subsampled to the target ratio (C3, checked):

    - ``matched`` (headline): the training set holds the same number of malware and benign
      rows as the time-aware window, so the class prior is the same and only time differs.
    - ``pooled``: a plain random subset of the pool, so its prior is the pool's.

    With ``per_slot`` (E1) the matched model's held-out rows are also scored per evaluation
    slot, each slot subsampled to the target ratio on its own (C3, checked), which makes the
    comparator per-slot matched. Returns comparator -> model index -> counts and F1.
    """
    plan = window.plan
    raw = [*window.train.slots, *(ctx.source.load_slot(r.slot_id) for r in plan.eval)]
    X = _stack([r.X for r in raw])
    y = np.concatenate([r.y for r in raw])
    row_id = np.concatenate([r.row_id for r in raw]) if per_slot is not None else None
    origin = (
        np.repeat(np.arange(len(raw)), [len(r.y) for r in raw]) if per_slot is not None else None
    )
    del raw  # the pooled matrix is a copy; keep one pooled set in memory, not two
    n_train = sum(len(s) for s in window.train.slots)
    entropy = [seed, zlib.crc32(plan.window_id.encode("utf-8")), _RANDOM_TAG]
    perm = np.random.default_rng(np.random.SeedSequence(entropy)).permutation(len(y))
    draws = {"pooled": (perm[:n_train], perm[n_train:])}
    rng = np.random.default_rng(np.random.SeedSequence([*entropy, 1]))
    malware, benign = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    chosen = np.concatenate(
        [
            rng.permutation(malware)[:n_train_malware],
            rng.permutation(benign)[: n_train - n_train_malware],
        ]
    )
    held_out = np.ones(len(y), dtype=bool)
    held_out[chosen] = False
    draws["matched"] = (np.sort(chosen), np.flatnonzero(held_out))

    out: dict[str, dict[int, dict[str, Any]]] = {}
    for name, (train_idx, test_idx) in draws.items():
        held = test_idx
        kept = constraints.subsample_malware(
            y[test_idx], spec.target_ratio, seed, f"e0-random-{name}:{plan.window_id}"
        )
        c3 = constraints.check_c3(y[test_idx], kept, spec.target_ratio)
        test_idx = test_idx[kept]
        X_train, y_train, X_test, y_test = X[train_idx], y[train_idx], X[test_idx], y[test_idx]
        out[name] = {}
        for mi, mspec in enumerate(ctx.cfg.models):
            key = f"{plan.window_id}|random-{name}"
            det = make_model(mspec, seed).fit(X_train, y_train, key)
            sc = score_slot(y_test, det.decide(det.predict_proba(X_test, key)))
            out[name][mi] = {
                "f1": sc.f1,
                "fit_seconds": float(det.fit_info["fit_seconds"]),
                "n_train_malware": int((y_train == 1).sum()),
                "n_test": sc.n,
                "n_test_malware": sc.n_malware,
                "n_test_malware_before": c3.n_malware_before,
                "achieved_ratio": c3.achieved_ratio,
                "c3_status": c3.status,
                "tp": sc.tp,
                "fp": sc.fp,
                "fn": sc.fn,
            }
            if per_slot is not None and name == "matched":
                per_slot(mi, det, key, X, y, row_id, origin, held, len(window.train.slots))
        del X_train, y_train, X_test, y_test
    return out


def _per_slot_writer(ctx: _Ctx, variant: str, spec: WindowSpec, seed: int, window: Window):
    """The E1 comparator's per-slot scoring: C3 on each held-out slot, then rows and metrics."""
    plan = window.plan

    def per_slot(mi, det, fit_key, X, y, row_id, origin, held, n_train_slots) -> None:
        for j, ref in enumerate(plan.eval):
            idx = held[origin[held] == n_train_slots + j]
            kept = constraints.subsample_malware(
                y[idx], spec.target_ratio, seed, f"e1-random:{plan.window_id}:{ref.slot_id}"
            )
            c3 = constraints.check_c3(y[idx], kept, spec.target_ratio)
            idx = idx[kept]
            proba = det.predict_proba(X[idx], fit_key)
            pred = det.decide(proba)
            sc = score_slot(y[idx], pred)
            key = {
                **_arm(ctx.cfg, "random_split"),
                "variant": variant,
                "model": det.name,
                "ratio": spec.target_ratio,
                "seed": seed,
                "window_id": plan.window_id,
                "slot_id": ref.slot_id,
            }
            _emit(ctx, key, row_id=row_id[idx], y_true=y[idx], proba=proba, pred=pred)
            ctx.store.add_slot(
                {
                    **_slot_base(variant, det.name, spec, seed, plan.window_id, ref, c3, None),
                    **_score_columns(sc),
                    **_arm(ctx.cfg, "random_split"),
                }
            )
            ctx.n_slot_rows += 1

    return per_slot


# --- initial fits ----------------------------------------------------------------------------


def _rows_digest(train: Any) -> str:
    """Digest of the training rows' ids, labels and feature values (not just slot ids)."""
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(train.row_id, dtype=np.int64).tobytes())
    h.update(np.ascontiguousarray(train.y, dtype=np.int8).tobytes())
    X = train.X
    if hasattr(X, "indptr"):  # CSR: values, column indices, row pointers
        for part in (X.data, X.indices, X.indptr):
            h.update(np.ascontiguousarray(part).tobytes())
    else:
        h.update(np.ascontiguousarray(X).tobytes())
    return h.hexdigest()[:20]


def _initial_detectors(
    ctx: _Ctx, window: Window, seed: int, train_key: str
) -> list[tuple[int, Detector, bool]]:
    """One fitted detector per configured model on the window's raw training rows."""
    train = window.train
    rows = _rows_digest(train)
    fitted: list[tuple[int, Detector, bool]] = []
    for mi, mspec in enumerate(ctx.cfg.models):
        det = make_model(mspec, seed)
        key = InitialModelCache.key(
            ctx.cfg.dataset, train_key, mspec, seed if det.seed_sensitive else None, rows
        )

        def fit(d: Detector = det) -> Detector:
            return d.fit(train.X, train.y, train_key)

        det, reused = ctx.cache.get_or_fit(key, fit)
        fitted.append((mi, det, reused))
    return fitted


# --- baseline loop (E0, E1) ------------------------------------------------------------------


def _run_window(ctx: _Ctx, variant: str, spec: WindowSpec, seed: int, window: Window) -> None:
    plan = window.plan
    train_key = f"{plan.train[0].slot_id}+{len(plan.train)}"
    ytr = window.train.y
    n_train_rows, n_train_mal = int(len(ytr)), int((ytr == 1).sum())
    del ytr

    fitted = _initial_detectors(ctx, window, seed, train_key)

    f1s: dict[int, list[float]] = {mi: [] for mi, _, _ in fitted}
    fprs: dict[int, list[float]] = {mi: [] for mi, _, _ in fitted}
    fnrs: dict[int, list[float]] = {mi: [] for mi, _, _ in fitted}
    ratios: list[float] = []
    below = 0
    arm = _arm(ctx.cfg)
    for eval_slot in window.eval_slots():
        slot = SealedSlot(eval_slot)  # the one door to true labels (sim/queue.py)
        public = slot.public()
        ratios.append(slot.c3.achieved_ratio)
        below += int(slot.c3.status == "below_target")
        for mi, det, _ in fitted:
            proba = det.predict_proba(public.X, train_key)
            pred = det.decide(proba)
            scored = slot.score(pred)
            sc = scored.scores
            f1s[mi].append(sc.f1)
            fprs[mi].append(sc.fpr)
            fnrs[mi].append(sc.fnr)
            key = {
                **arm,
                "variant": variant,
                "model": det.name,
                "ratio": spec.target_ratio,
                "seed": seed,
                "window_id": plan.window_id,
                "slot_id": slot.ref.slot_id,
            }
            _emit(ctx, key, row_id=scored.row_id, y_true=scored.y_true, proba=proba, pred=pred)
            ctx.store.add_slot(
                {**_slot_row(variant, det.name, spec, seed, plan.window_id, slot, sc), **arm}
            )
            ctx.n_slot_rows += 1

    random = _random_for(ctx, variant, spec, seed, window, n_train_mal)
    _finish_window(
        ctx, variant, spec, seed, window, train_key, fitted, f1s, fprs, fnrs, ratios, below,
        n_train_rows, n_train_mal, random, {mi: {} for mi, _, _ in fitted}, arm,
    )  # fmt: skip


def _random_for(
    ctx: _Ctx, variant: str, spec: WindowSpec, seed: int, window: Window, n_train_mal: int
) -> dict[str, dict[int, dict[str, Any]]]:
    if not _wants_random(ctx.cfg, variant):
        return {}
    per_slot = (
        _per_slot_writer(ctx, variant, spec, seed, window)
        if ctx.cfg.per_slot_random_split
        else None
    )
    return _random_split(ctx, window, spec, seed, n_train_mal, per_slot)


# --- simulation loop (Phase 5) ---------------------------------------------------------------


@dataclass
class _ModelState:
    mspec: dict[str, Any]
    det: Detector
    fit_key: str
    queue: LabelQueue
    pool: TrainingPool
    policy: Policy
    selector: Selector
    n_released: int = 0
    n_queried: int = 0
    n_ignored: int = 0
    n_retrains: int = 0
    n_noop_retrains: int = 0
    retrain_seconds: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _run_sim_window(ctx: _Ctx, variant: str, spec: WindowSpec, seed: int, window: Window) -> None:
    cfg = ctx.cfg
    plan = window.plan
    train_key = f"{plan.train[0].slot_id}+{len(plan.train)}"
    ytr = window.train.y
    n_train_rows, n_train_mal = int(len(ytr)), int((ytr == 1).sum())
    del ytr

    fitted = _initial_detectors(ctx, window, seed, train_key)
    n_eval = len(plan.eval)
    states = {
        mi: _ModelState(
            mspec=cfg.models[mi],
            det=det,
            fit_key=train_key,
            queue=LabelQueue(delay=cfg.delay, n_slots=n_eval),  # type: ignore[arg-type]
            pool=TrainingPool(window.train),
            policy=make_policy(cfg.policy, cfg.policy_period or 3),
            selector=make_selector(cfg.selector),  # type: ignore[arg-type]
        )
        for mi, det, _ in fitted
    }
    f1s: dict[int, list[float]] = {mi: [] for mi in states}
    fprs: dict[int, list[float]] = {mi: [] for mi in states}
    fnrs: dict[int, list[float]] = {mi: [] for mi in states}
    ratios: list[float] = []
    below = 0
    arm = _arm(cfg)
    for s, eval_slot in enumerate(window.eval_slots()):
        slot = SealedSlot(eval_slot)
        public = slot.public()
        ratios.append(slot.c3.achieved_ratio)
        below += int(slot.c3.status == "below_target")
        n_budget = budget_count(slot.n, cfg.budget_pct)  # type: ignore[arg-type]
        n_cal = calibration_count(n_budget, cfg.calibration_fraction or 0.0)
        for mi, st in states.items():
            released = st.queue.release(s)  # labels queried in slot s - 1 - d arrive now
            st.pool.add(released)
            st.n_released += len(released)
            slot.assert_c1(st.pool.ts)  # C1 with the released rows in the pool
            # repeats of a vector the pool already holds (initial rows and arrived labels):
            # a count of the metric side, taken before this slot's own query
            n_seen_pool = slot.n_seen_in(st.pool.fv_hash)
            event = st.policy.should_retrain(s)
            n_new = st.pool.n_new_since_fit
            fit_seconds = 0.0
            refit = event and n_new > 0
            if refit:
                fit_key = f"{train_key}@{s}"
                st.det = make_model(st.mspec, seed).fit(st.pool.X, st.pool.y, fit_key)
                st.fit_key = fit_key
                st.pool.mark_fitted()
                fit_seconds = float(st.det.fit_info["fit_seconds"])
                st.n_retrains += 1
                st.retrain_seconds += fit_seconds
            elif event:
                st.n_noop_retrains += 1  # scheduled, but no label has arrived since the fit
            proba = st.det.predict_proba(public.X, st.fit_key)
            pred = st.det.decide(proba)
            scored = slot.score(pred)
            sc = scored.scores
            f1s[mi].append(sc.f1)
            fprs[mi].append(sc.fpr)
            fnrs[mi].append(sc.fnr)
            key = {
                **arm,
                "variant": variant,
                "model": st.det.name,
                "ratio": spec.target_ratio,
                "seed": seed,
                "window_id": plan.window_id,
                "slot_id": slot.ref.slot_id,
            }
            _emit(ctx, key, row_id=scored.row_id, y_true=scored.y_true, proba=proba, pred=pred)
            n_pool = st.pool.n
            # spend the budget now; the labels come back through the queue after the delay
            selection = st.selector.select(public, n_budget, selector_rng(seed, public.slot_id))
            if len(selection.handles) > n_budget:
                raise ValueError(
                    f"selector {st.selector.name!r} returned {len(selection.handles)} handles "
                    f"for a budget of {n_budget} in slot {slot.slot_id}"
                )
            receipt = st.queue.query(s, slot, selection)
            st.n_queried += receipt.n_queried
            st.n_ignored += receipt.n_ignored
            ctx.store.add_slot(
                {
                    **_slot_row(variant, st.det.name, spec, seed, plan.window_id, slot, sc),
                    **arm,
                    "n_budget": n_budget,
                    "n_calibration": n_cal,
                    "n_queried": receipt.n_queried,
                    "n_released": len(released),
                    "n_pool": n_pool,
                    "n_pool_new_labels": n_pool - n_train_rows,
                    "n_seen_in_pool": n_seen_pool,
                    "retrain_event": bool(event),
                    "retrained": bool(refit),
                    "n_ignored_after_end": receipt.n_ignored,
                    "retrain_seconds": fit_seconds,
                    "fit_seconds": fit_seconds,
                }
            )
            ctx.n_slot_rows += 1

    for st in states.values():
        st.extra = {
            "n_queried_total": st.n_queried,
            "n_released_total": st.n_released,
            "n_ignored_total": st.n_ignored,
            "n_retrains": st.n_retrains,
            "n_noop_retrains": st.n_noop_retrains,
            "retrain_seconds_total": st.retrain_seconds,
            "n_pool_final": st.pool.n,
            "n_arrived_final": st.pool.n_arrived,
        }
    random = _random_for(ctx, variant, spec, seed, window, n_train_mal)
    _finish_window(
        ctx, variant, spec, seed, window, train_key, fitted, f1s, fprs, fnrs, ratios, below,
        n_train_rows, n_train_mal, random, {mi: st.extra for mi, st in states.items()}, arm,
    )  # fmt: skip


# --- shared window row -----------------------------------------------------------------------


def _finish_window(
    ctx: _Ctx,
    variant: str,
    spec: WindowSpec,
    seed: int,
    window: Window,
    train_key: str,
    fitted: list[tuple[int, Detector, bool]],
    f1s: dict[int, list[float]],
    fprs: dict[int, list[float]],
    fnrs: dict[int, list[float]],
    ratios: list[float],
    below: int,
    n_train_rows: int,
    n_train_mal: int,
    random: dict[str, dict[int, dict[str, Any]]],
    extra: dict[int, dict[str, Any]],
    arm: dict[str, Any],
) -> None:
    plan = window.plan
    first = fitted[0][0]
    if len(f1s[first]) < 2:
        log.warning(
            "%s: %d evaluation slot(s); AUT is undefined and the window is not counted",
            plan.window_id,
            len(f1s[first]),
        )
    for mi, det, reused in fitted:
        series = f1s[mi]
        events = drop_events(series)
        info = det.fit_info
        matched = random.get("matched", {}).get(mi)
        pooled = random.get("pooled", {}).get(mi)
        ctx.store.add_window(
            {
                "variant": variant,
                "model": det.name,
                "ratio": spec.target_ratio,
                "seed": seed,
                "window_id": plan.window_id,
                "segment": plan.segment,
                "train_key": train_key,
                "train_first": plan.train[0].slot_id,
                "train_last": plan.train[-1].slot_id,
                "n_train_slots": len(plan.train),
                "n_train_rows": n_train_rows,
                "n_train_malware": n_train_mal,
                "n_eval_slots": len(series),
                "aut": aut(series) if len(series) >= 2 else float("nan"),
                "f1_first": series[0],
                "f1_last": series[-1],
                "mean_fpr": float(np.mean(fprs[mi])),
                "mean_fnr": float(np.mean(fnrs[mi])),
                "mean_achieved_ratio": float(np.mean(ratios)),
                "n_below_target": below,
                "n_drop_events": len(events),
                "n_recovered": sum(e.recovery_slots is not None for e in events),
                "aut_defined": len(series) >= 2,
                **_random_columns(matched, pooled),
                "fit_seconds": float(info["fit_seconds"]),
                "fit_reused": bool(reused),
                "fit_seed": det.seed,
                "converged": info.get("converged"),
                "n_iter": info.get("n_iter"),
                "n_trees": info.get("n_trees"),
                **arm,
                **extra.get(mi, {}),
            }
        )
        ctx.n_windows += 1
    log.info(
        "%s seed %d %s: %d eval slots, models %s",
        variant,
        seed,
        plan.window_id.split("|", 1)[-1],
        len(f1s[first]),
        [d.name for _, d, _ in fitted],
    )


def _wants_random(cfg: RunConfig, variant: str) -> bool:
    return cfg.random_split and variant != "single_run"


def _random_columns(
    matched: dict[str, Any] | None, pooled: dict[str, Any] | None
) -> dict[str, Any]:
    """Window-table columns of the two random-split comparators (NaN when not run)."""
    nan = float("nan")
    m, p = matched or {}, pooled or {}
    return {
        "f1_random_split": m.get("f1", nan),  # prior-matched: the headline comparator
        "random_fit_seconds": m.get("fit_seconds", nan),
        "random_n_train_malware": m.get("n_train_malware"),
        "random_n_test": m.get("n_test"),
        "random_n_test_malware": m.get("n_test_malware"),
        "random_n_test_malware_before": m.get("n_test_malware_before"),
        "random_achieved_ratio": m.get("achieved_ratio", nan),
        "random_c3_status": m.get("c3_status"),
        "random_tp": m.get("tp"),
        "random_fp": m.get("fp"),
        "random_fn": m.get("fn"),
        "f1_random_pooled": p.get("f1", nan),  # pool prior: secondary comparator
        "random_pooled_fit_seconds": p.get("fit_seconds", nan),
        "random_pooled_n_train_malware": p.get("n_train_malware"),
        "random_pooled_n_test": p.get("n_test"),
        "random_pooled_achieved_ratio": p.get("achieved_ratio", nan),
    }


def _slot_base(
    variant: str,
    model: str,
    spec: WindowSpec,
    seed: int,
    window_id: str,
    ref: Any,
    c3: Any,
    n_seen: int | None,
) -> dict[str, Any]:
    return {
        "variant": variant,
        "model": model,
        "ratio": spec.target_ratio,
        "seed": seed,
        "window_id": window_id,
        "slot_id": ref.slot_id,
        "slot_start": str(np.datetime64(ref.start, "s")),
        "slot_index": ref.index,
        "achieved_ratio": c3.achieved_ratio,
        "target_ratio": c3.target_ratio,
        "c3_status": c3.status,
        "n_malware_before": c3.n_malware_before,
        "n_benign_before": c3.n_benign_before,
        "n_seen_in_initial_train": n_seen,
    }


def _score_columns(sc: SlotScores) -> dict[str, Any]:
    return {
        "n": sc.n,
        "n_malware": sc.n_malware,
        "n_benign": sc.n_benign,
        "tp": sc.tp,
        "fp": sc.fp,
        "fn": sc.fn,
        "tn": sc.tn,
        "f1": sc.f1,
        "fpr": sc.fpr,
        "fnr": sc.fnr,
    }


def _slot_row(
    variant: str,
    model: str,
    spec: WindowSpec,
    seed: int,
    window_id: str,
    slot: SealedSlot,
    sc: SlotScores,
) -> dict[str, Any]:
    base = _slot_base(
        variant, model, spec, seed, window_id, slot.ref, slot.c3, slot.n_seen_in_initial_train
    )
    return {**base, **_score_columns(sc)}


def _machine() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "physical_cores": psutil.cpu_count(logical=False),
        "ram_total_bytes": psutil.virtual_memory().total,
    }


# --- runs ------------------------------------------------------------------------------------


def run(
    cfg: RunConfig,
    source: SlotSource,
    out_root: Path | str,
    *,
    repo_root: Path | str,
    memory_cap_bytes: int = DEFAULT_MEMORY_CAP,
    overwrite: bool = False,
    require_clean: bool = False,
    resume: bool = False,
    cache: InitialModelCache | None = None,
    max_windows: int | None = None,
    pinned_version: str | None = None,
) -> RunSummary:
    """Run ``cfg`` on ``source`` and write the result store under ``out_root``.

    ``require_clean`` refuses a working tree with uncommitted changes: two different dirty
    trees would otherwise share one config hash. Evidence runs use it. ``resume`` continues
    an interrupted run of the same config hash from its finished units; it needs a clean tree
    for the same reason, and refuses a run that already finished.

    ``max_windows`` runs only the first windows of each variant and seed (the grid's smoke
    mode, which measures time). It is recorded in ``run.json`` and is never part of an
    evidence run: the grid driver writes smoke results to their own root.
    """
    if max_windows is not None and max_windows < 1:
        raise ValueError(f"max_windows must be at least 1, got {max_windows}")
    only = range(max_windows) if max_windows is not None else None
    repo = Path(repo_root)
    version = pinned_version or code_version(repo)
    if (require_clean or resume) and (version.endswith("-dirty") or version == "unknown"):
        raise RuntimeError(
            f"the working tree is dirty or not a git checkout ({version}); "
            "commit before an evidence run"
        )
    lock = lock_sha256(repo)
    chash = config_hash(cfg.to_dict(), version, lock)
    store = ResultStore(out_root, chash, overwrite=overwrite, resume=resume)
    hasher = PredictionHasher()
    cells: dict[str, PredictionHasher] = {}
    shared = cache if cache is not None else InitialModelCache()
    t0 = time.perf_counter()
    try:
        with MemoryWatchdog(memory_cap_bytes) as watchdog, store.predictions() as write:
            ctx = _Ctx(cfg, source, store, write, hasher, cells, shared)
            for variant in cfg.variants:
                for seed in cfg.seeds:
                    spec = _spec_for(cfg, variant, seed)
                    n_units = 0
                    for window in slice_windows(source, spec, only=only):
                        unit = f"{variant}|{seed}|{window.plan.window_id}"
                        n_units += 1
                        if store.begin_unit(unit):
                            _replay(ctx)
                        else:
                            fn = _run_sim_window if cfg.is_simulation else _run_window
                            fn(ctx, variant, spec, seed, window)
                        store.end_unit()
                    if n_units == 0:
                        raise RuntimeError(
                            f"variant {variant!r} (seed {seed}, spec {spec.digest()}) yields no "
                            "window on this source; an empty result is not a result"
                        )
    except BaseException as exc:
        store.fail(
            {
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
                "code_version": version,
            }
        )
        raise
    wall = time.perf_counter() - t0
    record = {
        "config": cfg.to_dict(),
        "config_hash": chash,
        "code_version": version,
        "lock_sha256": lock,
        "packages": package_versions(),
        "machine": _machine(),
        "seeds": list(cfg.seeds),
        "models": [make_model(m, 0).spec() for m in cfg.models],
        "source": source.provenance(),
        "predictions_sha256": hasher.hexdigest(),
        "cell_predictions_sha256": {k: v.hexdigest() for k, v in sorted(cells.items())},
        "n_prediction_rows": hasher.n_rows,
        "n_windows": ctx.n_windows,
        "n_slot_rows": ctx.n_slot_rows,
        "memory": watchdog.as_record(),
        "wall_s": round(wall, 2),
        "resumed": bool(resume),
        "max_windows": max_windows,
    }
    directory = store.finalize(record)
    return RunSummary(
        directory, chash, hasher.hexdigest(), ctx.n_windows, ctx.n_slot_rows, hasher.n_rows, wall
    )


def run_many(
    jobs: list[tuple[RunConfig, SlotSource]],
    out_root: Path | str,
    *,
    repo_root: Path | str,
    workers: int = 1,
    **kwargs: Any,
) -> list[RunSummary]:
    """Run several configs, one thread per run (never threads inside a run).

    The runs share one :class:`InitialModelCache`, so an initial model that two runs need
    (same dataset, training window, model and seed) is fitted once. Results come back in job
    order. If a run raises, the others finish and the first error is re-raised.
    """
    if workers < 1:
        raise ValueError(f"workers must be at least 1, got {workers}")
    seen: set[str] = set()
    for cfg, _ in jobs:
        canon = json.dumps(cfg.to_dict(), sort_keys=True)
        if canon in seen:
            raise ValueError(f"two jobs have the same configuration ({cfg.name!r}): one result dir")
        seen.add(canon)
    cache = kwargs.pop("cache", None) or InitialModelCache()

    def one(job: tuple[RunConfig, SlotSource]) -> RunSummary:
        cfg, source = job
        return run(cfg, source, out_root, repo_root=repo_root, cache=cache, **kwargs)

    if workers == 1:
        return [one(j) for j in jobs]
    results: list[RunSummary | BaseException] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, j) for j in jobs]
        for f in futures:
            try:
                results.append(f.result())
            except BaseException as exc:  # noqa: BLE001 - re-raised below after all finish
                results.append(exc)
    for r in results:
        if isinstance(r, BaseException):
            raise r
    return [r for r in results if isinstance(r, RunSummary)]


def run_file(
    config_path: Path | str,
    *,
    data_root: Path | str = "data",
    out_root: Path | str | None = None,
    repo_root: Path | str | None = None,
    memory_cap_gb: float = 1.5,
    overwrite: bool = False,
    require_clean: bool = False,
    resume: bool = False,
    cache: InitialModelCache | None = None,
) -> RunSummary:
    """Load a YAML config, build its dataset source and run it (``driftwatch run``)."""
    from driftwatch.data.presets import cached_source

    cfg = RunConfig.from_file(config_path)
    repo = Path(repo_root) if repo_root else Path(__file__).resolve().parents[3]
    source = cached_source(cfg.dataset, data_root)
    return run(
        cfg,
        source,
        out_root if out_root is not None else cfg.output,
        repo_root=repo,
        memory_cap_bytes=int(memory_cap_gb * 1024**3),
        overwrite=overwrite,
        require_clean=require_clean,
        resume=resume,
        cache=cache,
    )
