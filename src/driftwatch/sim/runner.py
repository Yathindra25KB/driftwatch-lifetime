"""E0: the never-retrain baseline under the time-aware protocol (Phase 4).

For each variant, seed and window the runner

1. fits every model once on the window's raw training rows (labels allowed there);
2. scores each evaluation slot on :meth:`EvalSlot.public` only (features in a seeded,
   label-free order) and maps predictions back with the slot-bound handles;
3. computes per-slot F1, FPR and FNR from the true labels (metric code only) and the
   window's AUT;
4. optionally refits on a random split of the same pooled rows (same training size, malware
   test rows subsampled to the same ratio) to get the random-split F1 a time-blind
   evaluation would report.

Variants (ADR-0005, ADR-0006): ``rolling`` (ADR-0005 stride, headline), ``rolling_chow``
(stride ``min(nT, nE)`` as in Chow et al.), ``sensitivity`` (rolling windows planned at the
sensitivity ratio) and ``single_run`` (train on the first nT slots of a run, evaluate the
rest). A fit is identified by (model, seed if the model uses it, training slots), so the same
training window under another variant or seed is not refitted when the fit cannot differ.

No simulator, label queue, selector, conformal layer or monitor exists here. The label
delay of E1 and later lives in sim/queue.py (hard rule 3).
"""

from __future__ import annotations

import logging
import os
import platform
import time
import traceback
import zlib
from dataclasses import dataclass
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
from driftwatch.sim.queue import SealedSlot
from driftwatch.sim.results import PredictionHasher, ResultStore

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


@dataclass
class _Ctx:
    cfg: RunConfig
    source: SlotSource
    store: ResultStore
    write: Any
    hasher: PredictionHasher
    cell_hashers: dict[str, PredictionHasher]
    fit_cache: dict[tuple[int, int | None, str], Detector]
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


def _random_split(
    ctx: _Ctx, window: Window, spec: WindowSpec, seed: int, n_train_malware: int
) -> dict[str, dict[int, dict[str, Any]]]:
    """Random-split comparators on the window's pooled rows (they violate C1 by design).

    Two draws, both with the time-aware window's training size, both tested on the rest of
    the pool with malware subsampled to the target ratio (C3, checked):

    - ``matched`` (headline): the training set holds the same number of malware and benign
      rows as the time-aware window, so the class prior is the same and only time differs.
    - ``pooled``: a plain random subset of the pool, so its prior is the pool's.

    Returns comparator -> model index -> counts and F1.
    """
    plan = window.plan
    raw = [*window.train.slots, *(ctx.source.load_slot(r.slot_id) for r in plan.eval)]
    X = _stack([r.X for r in raw])
    y = np.concatenate([r.y for r in raw])
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
        del X_train, y_train, X_test, y_test
    return out


def _run_window(ctx: _Ctx, variant: str, spec: WindowSpec, seed: int, window: Window) -> None:
    plan = window.plan
    train_key = f"{plan.train[0].slot_id}+{len(plan.train)}"
    Xtr, ytr = window.train.X, window.train.y
    n_train_rows, n_train_mal = int(len(ytr)), int((ytr == 1).sum())

    fitted: list[tuple[int, Detector, bool]] = []
    for mi, mspec in enumerate(ctx.cfg.models):
        det = make_model(mspec, seed)
        key = (mi, seed if det.seed_sensitive else None, train_key)
        cached = ctx.fit_cache.get(key)
        if cached is None:
            det.fit(Xtr, ytr, train_key)
            ctx.fit_cache[key] = det
        else:
            det = cached
        fitted.append((mi, det, cached is not None))
    del Xtr, ytr

    f1s: dict[int, list[float]] = {mi: [] for mi, _, _ in fitted}
    fprs: dict[int, list[float]] = {mi: [] for mi, _, _ in fitted}
    fnrs: dict[int, list[float]] = {mi: [] for mi, _, _ in fitted}
    ratios: list[float] = []
    below = 0
    for eval_slot in window.eval_slots():
        slot = SealedSlot(eval_slot)  # the one door to true labels (sim/queue.py)
        public = slot.public()
        ratios.append(slot.c3.achieved_ratio)
        below += int(slot.c3.status == "below_target")
        for mi, det, _ in fitted:
            proba = det.predict_proba(public.X, train_key)
            pred = det.decide(proba)
            scored = slot.score(pred)
            y_true, sc, row_id = scored.y_true, scored.scores, scored.row_id
            f1s[mi].append(sc.f1)
            fprs[mi].append(sc.fpr)
            fnrs[mi].append(sc.fnr)
            model = det.name
            cell = f"{variant}|{model}|{spec.target_ratio}|{seed}"
            ctx.write(
                {
                    "variant": variant,
                    "model": model,
                    "ratio": spec.target_ratio,
                    "seed": seed,
                    "window_id": plan.window_id,
                    "slot_id": slot.ref.slot_id,
                },
                row_id=row_id,
                y_true=y_true,
                proba=proba,
                pred=pred,
            )
            for hasher in (ctx.hasher, ctx.cell_hashers.setdefault(cell, PredictionHasher())):
                hasher.update(cell, plan.window_id, slot.ref.slot_id, row_id, pred, proba)
            ctx.store.add_slot(_slot_row(variant, model, spec, seed, plan.window_id, slot, sc))
            ctx.n_slot_rows += 1

    random = (
        _random_split(ctx, window, spec, seed, n_train_mal)
        if _wants_random(ctx.cfg, variant)
        else {}
    )
    if len(f1s[fitted[0][0]]) < 2:
        log.warning(
            "%s: %d evaluation slot(s); AUT is undefined and the window is not counted",
            plan.window_id,
            len(f1s[fitted[0][0]]),
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
            }
        )
        ctx.n_windows += 1
    log.info(
        "%s seed %d %s: %d eval slots, models %s",
        variant,
        seed,
        plan.window_id.split("|", 1)[-1],
        len(f1s[fitted[0][0]]),
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


def _slot_row(
    variant: str,
    model: str,
    spec: WindowSpec,
    seed: int,
    window_id: str,
    slot: SealedSlot,
    sc: SlotScores,
) -> dict[str, Any]:
    c3 = slot.c3
    return {
        "variant": variant,
        "model": model,
        "ratio": spec.target_ratio,
        "seed": seed,
        "window_id": window_id,
        "slot_id": slot.ref.slot_id,
        "slot_start": str(np.datetime64(slot.ref.start, "s")),
        "slot_index": slot.ref.index,
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
        "achieved_ratio": c3.achieved_ratio,
        "target_ratio": c3.target_ratio,
        "c3_status": c3.status,
        "n_malware_before": c3.n_malware_before,
        "n_benign_before": c3.n_benign_before,
        "n_seen_in_initial_train": slot.n_seen_in_initial_train,
    }


def _machine() -> dict[str, Any]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "physical_cores": psutil.cpu_count(logical=False),
        "ram_total_bytes": psutil.virtual_memory().total,
    }


def run(
    cfg: RunConfig,
    source: SlotSource,
    out_root: Path | str,
    *,
    repo_root: Path | str,
    memory_cap_bytes: int = DEFAULT_MEMORY_CAP,
    overwrite: bool = False,
    require_clean: bool = False,
) -> RunSummary:
    """Run E0 for ``cfg`` on ``source`` and write the result store under ``out_root``.

    ``require_clean`` refuses a working tree with uncommitted changes: two different dirty
    trees would otherwise share one config hash. Evidence runs use it.
    """
    repo = Path(repo_root)
    version = code_version(repo)
    if require_clean and version.endswith("-dirty"):
        raise RuntimeError(f"the working tree is dirty ({version}); commit before an evidence run")
    lock = lock_sha256(repo)
    chash = config_hash(cfg.to_dict(), version, lock)
    store = ResultStore(out_root, chash, overwrite=overwrite)
    hasher = PredictionHasher()
    cells: dict[str, PredictionHasher] = {}
    t0 = time.perf_counter()
    try:
        with MemoryWatchdog(memory_cap_bytes) as watchdog, store.predictions() as write:
            ctx = _Ctx(cfg, source, store, write, hasher, cells, {})
            for variant in cfg.variants:
                for seed in cfg.seeds:
                    spec = _spec_for(cfg, variant, seed)
                    before = ctx.n_windows
                    for window in slice_windows(source, spec):
                        _run_window(ctx, variant, spec, seed, window)
                    if ctx.n_windows == before:
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
    }
    directory = store.finalize(record)
    return RunSummary(
        directory, chash, hasher.hexdigest(), ctx.n_windows, ctx.n_slot_rows, hasher.n_rows, wall
    )


def run_file(
    config_path: Path | str,
    *,
    data_root: Path | str = "data",
    out_root: Path | str | None = None,
    repo_root: Path | str | None = None,
    memory_cap_gb: float = 1.5,
    overwrite: bool = False,
    require_clean: bool = False,
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
    )
