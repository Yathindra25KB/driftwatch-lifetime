"""Deliberate breakages of the slicer and the constraints, to prove the tests can fail.

Each mutant patches one behaviour through ``pytest.MonkeyPatch``. Two uses:

- ``test_mutants_detected.py`` applies each one in-process and requires a declared detector
  to fail. That keeps the suite honest on every run.
- ``scripts/mutation_check.py`` runs the real test suites in a subprocess with one mutant
  applied (via ``mutation_plugin``) and prints the kill matrix.

A mutant that survives means a rule has no test that would fail if it were broken.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pytest

from driftwatch.data import constraints, slicer, tables
from driftwatch.data.slicer import SlotRows


@dataclass(frozen=True)
class Mutant:
    name: str
    breaks: str  # the rule the mutation violates
    apply: Callable[[pytest.MonkeyPatch], None]


# --- slicer mutants -------------------------------------------------------------------------


def _shift_boundary(mp: pytest.MonkeyPatch) -> None:
    """A row exactly at a slot's end now belongs to that slot (its window is [start, end])."""

    def bounds(ts_sorted: np.ndarray, edges: np.ndarray) -> np.ndarray:
        return np.searchsorted(ts_sorted, edges, side="right")

    mp.setattr(tables, "_slot_bounds", bounds)


def _shuffle_timestamps(mp: pytest.MonkeyPatch) -> None:
    """The slicer reads permuted timestamps: self-consistent, but not the true time."""
    original = tables._read_timestamps

    def shuffled(table, ts_col):
        return np.random.default_rng(0).permutation(original(table, ts_col))

    mp.setattr(tables, "_read_timestamps", shuffled)


def _leak_one_sample(mp: pytest.MonkeyPatch) -> None:
    """The newest row of the first evaluation slot is added to the training window."""
    original = slicer._train_rows

    def leaky(source, planned, plan):
        rows = list(original(source, planned, plan))
        future = source.load_slot(plan.eval[0].slot_id)
        j = int(np.argmax(future.ts))
        last = rows[-1]
        x = None
        if last.X is not None and future.X is not None:
            x = slicer._stack([last.X, future.X[[j]]])
        fv = None
        if last.fv_hash is not None and future.fv_hash is not None:
            fv = np.concatenate([last.fv_hash, future.fv_hash[[j]]])
        rows[-1] = SlotRows(
            ref=last.ref,
            y=np.concatenate([last.y, future.y[[j]]]),
            ts=np.concatenate([last.ts, future.ts[[j]]]),
            row_id=np.concatenate([last.row_id, future.row_id[[j]]]),
            X=x,
            fv_hash=fv,
        )
        return tuple(rows)

    mp.setattr(slicer, "_train_rows", leaky)


def _span_gap(mp: pytest.MonkeyPatch) -> None:
    """Usable slots are joined into one run even when a gap or skipped slot lies between."""

    def one_run(planned):
        usable = [p for p in planned if p.usable]
        return [usable] if usable else []

    mp.setattr(slicer, "_usable_runs", one_run)


def _gate_off(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(slicer, "_fails_size_gate", lambda kept, spec: False)


def _stride_ignored(mp: pytest.MonkeyPatch) -> None:
    original = slicer._window_starts

    def starts(length, spec):
        return original(length, dataclasses.replace(spec, stride=1))

    mp.setattr(slicer, "_window_starts", starts)


def _eval_overlaps_train(mp: pytest.MonkeyPatch) -> None:
    """The first evaluation slot of every window is the last training slot."""
    original = slicer.plan_windows

    def overlapping(planned, spec):
        schedule = original(planned, spec)
        windows = tuple(
            dataclasses.replace(w, eval=(w.train[-1], *w.eval[:-1])) for w in schedule.windows
        )
        return dataclasses.replace(schedule, windows=windows)

    mp.setattr(slicer, "plan_windows", overlapping)


# --- constraint mutants ---------------------------------------------------------------------


def _c1_non_strict(mp: pytest.MonkeyPatch) -> None:
    def lax(train_ts, eval_ts):
        train, evaluation = np.asarray(train_ts), np.asarray(eval_ts)
        if train.size == 0 or evaluation.size == 0 or not train.max() <= evaluation.min():
            raise constraints.C1Violation("lax C1")

    mp.setattr(constraints, "check_c1", lax)


def _c2_inclusive_end(mp: pytest.MonkeyPatch) -> None:
    def lax(ts, y, start, end):
        ts, y = np.asarray(ts), np.asarray(y)
        both = (y == 1).any() and (y == 0).any()
        if ts.size == 0 or not both or (ts < start).any() or (ts > end).any():
            raise constraints.C2Violation("lax C2")

    mp.setattr(constraints, "check_c2", lax)


def _c3_drop_benign(mp: pytest.MonkeyPatch) -> None:
    """Subsampling also drops one benign row."""
    original = constraints.subsample_malware

    def thin(y, ratio, seed, slot_id):
        kept = original(y, ratio, seed, slot_id)
        benign = kept[np.asarray(y)[kept] == 0]
        return kept[kept != benign[0]] if benign.size else kept

    mp.setattr(constraints, "subsample_malware", thin)


def _c3_unseeded(mp: pytest.MonkeyPatch) -> None:
    """The draw ignores the seed and the slot id."""

    def unseeded(y, ratio, seed, slot_id):
        y = np.asarray(y)
        target = constraints.target_malware_count(int((y == 0).sum()), ratio)
        malware = np.flatnonzero(y == 1)
        if malware.size <= target:
            return np.arange(y.size)
        chosen = np.random.default_rng().choice(malware, size=target, replace=False)
        return np.sort(np.concatenate([np.flatnonzero(y == 0), chosen]))

    mp.setattr(constraints, "subsample_malware", unseeded)


def _no_subsampling(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(constraints, "subsample_malware", lambda y, ratio, seed, slot_id: np.arange(len(y)))


MUTANTS: dict[str, Mutant] = {
    m.name: m
    for m in (
        Mutant("shift_boundary", "C2: slot window is [start, end)", _shift_boundary),
        Mutant("shuffle_timestamps", "C1/C2 against true time", _shuffle_timestamps),
        Mutant("leak_one_sample", "C1: training strictly older", _leak_one_sample),
        Mutant("span_gap", "windows never span a gap or skipped slot", _span_gap),
        Mutant("gate_off", "failing slots are skipped (size gate)", _gate_off),
        Mutant("stride_ignored", "rolling windows follow the stride", _stride_ignored),
        Mutant("eval_overlaps_train", "C1: evaluation slots follow training", _eval_overlaps_train),
        Mutant("c1_non_strict", "C1 is strict", _c1_non_strict),
        Mutant("c2_inclusive_end", "C2 window is half-open", _c2_inclusive_end),
        Mutant("c3_drop_benign", "C3 subsamples malware only", _c3_drop_benign),
        Mutant("c3_unseeded", "C3 draw is seeded and slot-scoped", _c3_unseeded),
        Mutant("no_subsampling", "C3 reaches the target ratio", _no_subsampling),
    )
}
