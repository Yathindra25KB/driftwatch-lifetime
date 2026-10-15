"""The E3 simulation window: selection by uncertainty or credibility under delayed labels.

Same stream order as ``runner._run_sim_window`` (release, retrain, score, select, query), with
the conformal layer added (docs/prereg/addendum-v2.md, ADR-0009):

- The initial detector is fitted on the window **minus a time-ordered hold-out**; the hold-out
  is the initial calibration set, so calibration rows are never rows the scoring model was
  fitted on. Every arm of E3 (random, uncertainty, credibility) does the same, so arms differ
  only in how the non-reserved part of the budget is spent.
- Every slot's budget is spent as a **random reserved slice** (share ``calibration_fraction``)
  plus the selector's choice. Reserved rows, once released through the queue, are the only
  calibration data (plus the hold-out). Rows a selector chose never enter the calibration
  buffer, and (unless ``calibration_in_pool``) calibration rows do not enter the training
  pool. The delay applies to calibration labels like to any other label.
- ``trap_selected_calibration`` (reserved share 0) feeds the calibration buffer from the
  selected rows on purpose: the deliberate exchangeability trap, reported as such.
- Labels spent are asserted equal to the budget in every slot, for every arm.

True labels are used here only through the queue (released rows) and the metric door
(``SealedSlot.score``); the coverage diagnostics use the scored labels, never the selector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from driftwatch.conformal.mondrian import credibility, pvalues
from driftwatch.conformal.nonconformity import CentroidScore, ProbabilityScore
from driftwatch.conformal.recalibrate import (
    ORIGIN_HOLDOUT,
    Calibration,
    CalibrationBuffer,
    RecalibrationRule,
    time_ordered_holdout,
)
from driftwatch.data.slicer import Window, WindowSpec
from driftwatch.models import make_model
from driftwatch.models.base import Detector
from driftwatch.sim.policies import make_policy
from driftwatch.sim.pool import TrainingPool
from driftwatch.sim.queue import LabelQueue, SealedSlot
from driftwatch.sim.selectors import (
    ORIGIN_RANDOM,
    RandomSelector,
    budget_count,
    calibration_count,
    make_selector,
    select_with_reserved_slice,
    selector_rng,
)

SIGNIFICANCE = 0.10  # prediction sets {c : p_c > 0.10}, for the coverage diagnostic only


@dataclass
class _SubTrain:
    """The window's training rows without the hold-out; same attributes the pool reads."""

    X: Any
    y: np.ndarray
    ts: np.ndarray
    row_id: np.ndarray
    fv_hash: np.ndarray | None


def _subset(train: Any, idx: np.ndarray) -> _SubTrain:
    fv = train.fv_hash
    return _SubTrain(
        X=train.X[idx],
        y=np.asarray(train.y)[idx],
        ts=np.asarray(train.ts)[idx],
        row_id=np.asarray(train.row_id)[idx],
        fv_hash=None if fv is None else np.asarray(fv)[idx],
    )


@dataclass
class _State:
    mspec: dict[str, Any]
    det: Detector
    fit_key: str
    queue: LabelQueue
    pool: TrainingPool
    policy: Any
    selector: Any
    buffer: CalibrationBuffer
    score: Any  # ProbabilityScore or a fitted CentroidScore
    cal: Calibration | None = None
    n_released: int = 0
    n_queried: int = 0
    n_ignored: int = 0
    n_retrains: int = 0
    n_noop_retrains: int = 0
    n_fallback_random: int = 0
    retrain_seconds: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)


def _own_scores(st: _State):
    """Nonconformity of each row for its own label under the model and score in force."""

    def fn(X: Any, y: np.ndarray) -> np.ndarray:
        proba = st.det.predict_proba(X, st.fit_key)
        s = st.score.scores(X, proba)
        return s[np.arange(len(y)), np.asarray(y, dtype=np.int64)]

    return fn


def _fit_score(st: _State, nc: dict[str, Any]) -> None:
    if nc["score"] == "centroid":
        st.score = CentroidScore(transform=st.det.feature_space).fit(
            st.pool.X, st.pool.y, st.fit_key
        )


def run_window(ctx: Any, variant: str, spec: WindowSpec, seed: int, window: Window) -> None:
    """One window of an E3 simulation; mirrors ``runner._run_sim_window``."""
    from driftwatch.sim import runner as R  # noqa: PLC0415 - runner imports this module lazily

    cfg = ctx.cfg
    nc = cfg.nonconf
    assert nc is not None
    plan = window.plan
    train = window.train
    keep, hold = time_ordered_holdout(np.asarray(train.ts), nc["holdout_fraction"])
    proper = _subset(train, keep)
    X_hold = train.X[hold]
    y_hold = np.asarray(train.y)[hold]
    train_key = f"{plan.train[0].slot_id}+{len(plan.train)}|holdout{nc['holdout_fraction']}"
    n_train_rows, n_train_mal = int(len(proper.y)), int((proper.y == 1).sum())

    trap = bool(nc["trap_selected_calibration"])
    rule = RecalibrationRule(nc["holdout_fraction"], nc["min_per_class"], nc["buffer_size"])
    fitted = R._initial_detectors(ctx, window, seed, train_key, train=proper)
    n_eval = len(plan.eval)
    states: dict[int, _State] = {}
    for mi, det, _ in fitted:
        st = _State(
            mspec=cfg.models[mi],
            det=det,
            fit_key=train_key,
            queue=LabelQueue(delay=cfg.delay, n_slots=n_eval),  # type: ignore[arg-type]
            pool=TrainingPool(proper),  # type: ignore[arg-type]
            policy=make_policy(cfg.policy, cfg.policy_period or 3),
            selector=make_selector(cfg.selector),  # type: ignore[arg-type]
            buffer=CalibrationBuffer(rule, allow_selected=trap),
            score=ProbabilityScore(),
        )
        st.buffer.add(X_hold, y_hold, ORIGIN_HOLDOUT)
        _fit_score(st, nc)
        st.cal = st.buffer.recalibrate(_own_scores(st), -1)
        states[mi] = st

    f1s: dict[int, list[float]] = {mi: [] for mi in states}
    fprs: dict[int, list[float]] = {mi: [] for mi in states}
    fnrs: dict[int, list[float]] = {mi: [] for mi in states}
    ratios: list[float] = []
    below = 0
    arm = R._arm(cfg)
    fallback = RandomSelector()
    for s, eval_slot in enumerate(window.eval_slots()):
        slot = SealedSlot(eval_slot)
        public = slot.public()
        ratios.append(slot.c3.achieved_ratio)
        below += int(slot.c3.status == "below_target")
        n_budget = budget_count(slot.n, cfg.budget_pct)  # type: ignore[arg-type]
        n_cal = calibration_count(n_budget, cfg.calibration_fraction or 0.0)
        for mi, st in states.items():
            released = st.queue.release(s)
            n_new_cal = 0
            if len(released):
                if trap or released.origin is None:
                    to_cal = (
                        np.ones(len(released), dtype=bool)
                        if trap
                        else np.zeros(len(released), dtype=bool)
                    )
                else:
                    to_cal = np.asarray(released.origin == ORIGIN_RANDOM, dtype=bool)
                cal_rows = released.take(to_cal)
                if len(cal_rows):
                    # the buffer sees each row's true origin, so a selected row cannot slip in
                    st.buffer.add(cal_rows.X, cal_rows.y, cal_rows.origin)
                    n_new_cal = len(cal_rows)
                train_rows = released if nc["calibration_in_pool"] else released.take(~to_cal)
                st.pool.add(train_rows)
            st.n_released += len(released)
            slot.assert_c1(st.pool.ts)  # C1 with the released rows in the pool
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
                _fit_score(st, nc)
            elif event:
                st.n_noop_retrains += 1
            if refit or n_new_cal:  # the calibration is recomputed under the model in force
                st.cal = st.buffer.recalibrate(_own_scores(st), s)
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
            R._emit(ctx, key, row_id=scored.row_id, y_true=scored.y_true, proba=proba, pred=pred)
            n_pool = st.pool.n

            # conformal quantities of this slot: from the model, the features and the calibration
            cred = None
            p = None
            if st.cal is not None:
                p = pvalues(st.cal.classes, st.score.scores(public.X, proba))
                cred = credibility(p, pred)
            diag = _coverage(p, cred, scored.y_true)
            used_fallback = False
            if st.selector.name == "uncertainty":
                priority, selector = proba, st.selector
            elif st.selector.name == "credibility":
                if cred is None:
                    priority, selector, used_fallback = None, fallback, True
                    st.n_fallback_random += 1
                else:
                    priority, selector = cred, st.selector
            else:
                priority, selector = None, st.selector
            selection = select_with_reserved_slice(
                selector,
                public,
                n_budget,
                n_cal,
                seed,
                selector_rng(seed, public.slot_id),
                priority,
            )
            receipt = st.queue.query(s, slot, selection)
            if receipt.n_queried != min(n_budget, slot.n):
                raise ValueError(
                    f"labels spent {receipt.n_queried} differ from the budget "
                    f"{min(n_budget, slot.n)} in slot {slot.slot_id} (equal labels spent)"
                )
            st.n_queried += receipt.n_queried
            st.n_ignored += receipt.n_ignored
            n_reserved = int((selection.origin == ORIGIN_RANDOM).sum())
            n0, n1 = st.buffer.class_counts()
            ctx.store.add_slot(
                {
                    **R._slot_row(variant, st.det.name, spec, seed, plan.window_id, slot, sc),
                    **arm,
                    "n_budget": n_budget,
                    "n_calibration": n_cal,
                    "n_selected": receipt.n_queried - n_reserved,
                    "n_queried": receipt.n_queried,
                    "n_released": len(released),
                    "n_released_to_calibration": n_new_cal,
                    "n_pool": n_pool,
                    "n_pool_new_labels": n_pool - n_train_rows,
                    "n_seen_in_pool": n_seen_pool,
                    "retrain_event": bool(event),
                    "retrained": bool(refit),
                    "n_ignored_after_end": receipt.n_ignored,
                    "retrain_seconds": fit_seconds,
                    "fit_seconds": fit_seconds,
                    "cal_rows": len(st.buffer),
                    "cal_class0": n0,
                    "cal_class1": n1,
                    "cal_skipped_total": st.buffer.n_skipped,
                    "cal_built_at": None if st.cal is None else st.cal.built_at,
                    "selection_fell_back_to_random": used_fallback,
                    **diag,
                }
            )  # fmt: skip
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
            "cal_recalibrations": st.buffer.n_recalibrations,
            "cal_skipped_total": st.buffer.n_skipped,
            "n_fallback_random": st.n_fallback_random,
        }
    random = R._random_for(ctx, variant, spec, seed, window, n_train_mal)
    R._finish_window(
        ctx, variant, spec, seed, window, train_key, fitted, f1s, fprs, fnrs, ratios, below,
        n_train_rows, n_train_mal, random, {mi: st.extra for mi, st in states.items()}, arm,
    )  # fmt: skip


def _coverage(p: np.ndarray | None, cred: np.ndarray | None, y_true: np.ndarray) -> dict[str, Any]:
    """Scoring-side diagnostics of the Mondrian p-values of one slot (labels only to score)."""
    if p is None or cred is None:
        return {
            "set_coverage": None,
            "set_size_mean": None,
            "set_empty_share": None,
            "credibility_mean": None,
        }
    in_set = p > SIGNIFICANCE
    y = np.asarray(y_true, dtype=np.int64)
    return {
        "set_coverage": float(in_set[np.arange(len(y)), y].mean()),
        "set_size_mean": float(in_set.sum(axis=1).mean()),
        "set_empty_share": float((in_set.sum(axis=1) == 0).mean()),
        "credibility_mean": float(cred.mean()),
    }


__all__ = ["run_window"]
