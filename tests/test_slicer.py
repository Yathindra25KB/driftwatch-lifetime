"""The time slicer on hand-built timelines: windows, gaps, the size gate, C3 logging, manifests.

The slicer works on any time-indexed table, so these tests use plain DataFrames. The
dataset caches are covered in test_slicer_cached.py and random timelines in
test_slicer_properties.py.
"""

from __future__ import annotations

import json
from dataclasses import fields

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp
from slicer_oracle import assert_window_matches_oracle
from timelines import DAY, build_timeline, feature_matrix, to_table

from driftwatch.data.slicer import (
    SliceLog,
    SlicerError,
    WindowSpec,
    plan_slots,
    plan_windows,
    seen_before_mask,
    slice_windows,
)
from driftwatch.data.tables import CalendarMonthScheme, FixedWidthScheme, TableSource

STANDARD = (40, 180)  # 40 malware, 180 benign: 10% needs 20 malware, so 50% are discarded


def spec(**overrides) -> WindowSpec:
    base = {"nT": 3, "nE": 2, "stride": 1, "target_ratio": 0.10, "min_malware": 2, "seed": 0}
    return WindowSpec(**{**base, **overrides})


def source_for(tl, **kwargs) -> TableSource:
    scheme = FixedWidthScheme(
        np.datetime64(tl.anchor, "s").astype("datetime64[ns]"),
        np.timedelta64(tl.width, "s"),
    )
    return TableSource(to_table(tl), scheme, name="synthetic", **kwargs)


class CountingSource:
    """Wraps a source and records every row load, to prove planning is features-free."""

    def __init__(self, inner):
        self.inner, self.loads = inner, []
        self.name, self.sparse = inner.name, inner.sparse

    def slot_table(self):
        return self.inner.slot_table()

    def load_slot(self, slot_id):
        self.loads.append(slot_id)
        return self.inner.load_slot(slot_id)

    def provenance(self):
        return self.inner.provenance()


def ten_slots(**kw):
    return build_timeline({k: STANDARD for k in range(10)}, **kw)


# --- windows --------------------------------------------------------------------------------


def test_window_yields_the_training_window_then_evaluation_slots_in_time_order():
    tl = ten_slots(anchor=5 * DAY)
    windows = list(slice_windows(source_for(tl), spec()))
    first = windows[0]
    assert [r.index for r in first.plan.train] == [0, 1, 2]
    assert [r.index for r in first.plan.eval] == [3, 4]
    assert len(first.train.slots) == 3
    evals = list(first.eval_slots())
    assert [e.ref.slot_id for e in evals] == [r.slot_id for r in first.plan.eval]
    assert evals[0].ts.max() < evals[1].ts.min()
    assert_window_matches_oracle(first, tl, ratio=0.10)


def test_evaluation_slots_are_loaded_one_at_a_time():
    src = CountingSource(source_for(ten_slots()))
    window = next(iter(slice_windows(src, spec())))
    assert len(src.loads) == 3  # only the training window so far
    slots = window.eval_slots()
    first = next(slots)
    assert len(src.loads) == 4 and first.ref == window.plan.eval[0]
    next(slots)
    assert len(src.loads) == 5


def test_planning_never_loads_features():
    src = CountingSource(source_for(ten_slots()))
    planned = plan_slots(src, spec())
    schedule = plan_windows(planned, spec())
    assert schedule.windows and src.loads == []


def test_rolling_windows_follow_nT_nE_and_stride():
    tl = ten_slots()
    windows = list(slice_windows(source_for(tl), spec(nT=3, nE=2, stride=2)))
    starts = [w.plan.train[0].index for w in windows]
    assert starts == [0, 2, 4]  # a window at start 6 would need slot 10, which does not exist
    for w in windows:
        assert len(w.plan.train) == 3 and len(w.plan.eval) == 2
        assert_window_matches_oracle(w, tl, ratio=0.10)


def test_single_run_protocol_trains_once_then_evaluates_to_the_end_of_the_run():
    tl = ten_slots()
    windows = list(slice_windows(source_for(tl), spec(nT=4, nE=None, stride=1)))
    assert len(windows) == 1
    assert len(windows[0].plan.train) == 4 and len(windows[0].plan.eval) == 6


def test_a_window_never_spans_a_gap():
    per_slot = {k: STANDARD for k in range(11) if k != 5}  # slot 5 has no rows
    tl = build_timeline(per_slot)
    log = SliceLog()
    windows = list(slice_windows(source_for(tl), spec(nT=3, nE=2, stride=1), log))
    for w in windows:
        idx = [r.index for r in (*w.plan.train, *w.plan.eval)]
        assert idx == list(range(idx[0], idx[0] + len(idx)))
        assert 5 not in idx
    assert [w.plan.train[0].index for w in windows] == [0, 6]
    gap = next(r for r in log.slot_rows if r["index"] == 5)
    assert gap["usable"] is False and gap["skip_reason"] == "gap"


def test_runs_shorter_than_a_window_are_skipped_and_logged():
    tl = build_timeline({k: STANDARD for k in range(11) if k != 5})
    log = SliceLog()
    windows = list(slice_windows(source_for(tl), spec(nT=3, nE=3, stride=1), log))
    assert windows == []
    assert len(log.skipped_runs) == 2
    assert {r["reason"] for r in log.skipped_runs} == {"shorter_than_window"}


def test_slot_failing_the_size_gate_is_skipped_logged_and_splits_the_run():
    per_slot = {k: STANDARD for k in range(10)}
    per_slot[4] = (1, 180)  # one malware: below M = 2
    tl = build_timeline(per_slot)
    log = SliceLog()
    windows = list(slice_windows(source_for(tl), spec(nT=2, nE=2, stride=1), log))
    for w in windows:
        assert 4 not in [r.index for r in (*w.plan.train, *w.plan.eval)]
    bad = next(r for r in log.slot_rows if r["index"] == 4)
    assert bad["skip_reason"] == "size_gate" and bad["n_malware"] == 1 and bad["usable"] is False


def test_gate_uses_malware_kept_at_the_target_ratio():
    # 500 malware but only 18 benign: 10% allows 2 malware, which is below M = 3.
    tl = build_timeline({0: (500, 18), 1: STANDARD})
    planned = plan_slots(source_for(tl), spec(min_malware=3))
    assert planned[0].n_malware_kept == 2 and planned[0].skip_reason == "size_gate"
    assert planned[1].usable


def test_slot_already_below_target_is_kept_flagged_and_logged():
    per_slot = {k: STANDARD for k in range(5)}
    per_slot[3] = (12, 180)  # 6.25%: 10% cannot be reached by dropping malware
    tl = build_timeline(per_slot)
    log = SliceLog()
    (window,) = slice_windows(source_for(tl), spec(nT=3, nE=2, stride=1), log)
    slots = list(window.eval_slots())
    low = next(s for s in slots if s.ref.index == 3)
    assert low.c3.status == "below_target"
    assert int((low.y == 1).sum()) == 12 and low.c3.share_malware_discarded == 0.0
    assert low.c3.achieved_ratio == pytest.approx(12 / 192)
    ok = next(s for s in slots if s.ref.index == 4)
    assert ok.c3.status == "at_target" and int((ok.y == 1).sum()) == 20


def test_c3_counts_before_and_after_are_logged_per_evaluation_slot():
    log = SliceLog()
    (window,) = slice_windows(source_for(ten_slots()), spec(nT=8, nE=2, stride=1), log)
    list(window.eval_slots())
    rows = [r for r in log.window_rows if r["role"] == "eval"]
    assert len(rows) == 2
    for r in rows:
        assert (r["n_malware_before"], r["n_benign_before"]) == STANDARD
        assert (r["n_malware_after"], r["n_benign_after"]) == (20, 180)
        assert r["share_malware_discarded"] == pytest.approx(0.5)
        assert r["c3_status"] == "at_target" and r["target_ratio"] == 0.10


def test_training_slots_are_raw_rows_not_subsampled():
    window = next(iter(slice_windows(source_for(ten_slots()), spec(nT=3, nE=1, stride=1))))
    assert int((window.train.y == 1).sum()) == 3 * 40  # the raw 40 malware per slot
    assert len(window.train.y) == 3 * 220


def test_training_window_splits_at_slot_boundaries_only():
    tl = ten_slots()
    window = next(iter(slice_windows(source_for(tl), spec())))
    older, newer = window.train.split_at_slot(2)
    assert [s.ref.index for s in older.slots] == [0, 1]
    assert [s.ref.index for s in newer.slots] == [2]
    assert older.ts.max() < newer.ts.min()
    with pytest.raises(ValueError):
        window.train.split_at_slot(0)
    with pytest.raises(ValueError):
        window.train.split_at_slot(3)


# --- label-free view, features, determinism -------------------------------------------------


def test_public_view_carries_only_features_and_opaque_row_ids():
    tl = ten_slots()
    src = source_for(tl, x=feature_matrix(tl))
    slot = next(next(iter(slice_windows(src, spec()))).eval_slots())
    public = slot.public()
    assert {f.name for f in fields(public)} == {"dataset", "slot_id", "X", "row_id"}
    assert public.dataset == "synthetic" and public.slot_id == slot.ref.slot_id
    # Handles, not dataset row ids: contiguous, and only the slot can map them back.
    assert np.array_equal(public.row_id, np.arange(len(slot.y)))
    assert np.array_equal(np.sort(slot.row_id[slot.resolve(public.row_id)]), np.sort(slot.row_id))


def test_feature_rows_follow_the_rows_that_survive_subsampling():
    tl = ten_slots()
    src = source_for(tl, x=feature_matrix(tl))
    slot = next(next(iter(slice_windows(src, spec()))).eval_slots())
    assert slot.X.shape[0] == len(slot.row_id) == len(slot.y)
    assert np.array_equal(slot.X[:, 0].astype(np.int64) - 1, slot.row_id)
    assert np.array_equal(slot.X[:, 1].astype(np.int8), slot.y)


def test_sparse_features_stay_sparse_and_dense_features_in_a_sparse_source_raise():
    tl = ten_slots()
    sparse_src = source_for(tl, x=feature_matrix(tl, sparse=True))
    assert sparse_src.sparse
    slot = next(next(iter(slice_windows(sparse_src, spec()))).eval_slots())
    assert sp.issparse(slot.X)

    liar = source_for(tl, x=feature_matrix(tl))
    liar.sparse = True  # a sparse source that hands back a dense array is densified: refuse
    with pytest.raises(SlicerError, match="dens"):
        next(iter(slice_windows(liar, spec())))


def test_output_is_deterministic_and_independent_of_input_row_order():
    tl = ten_slots(seed=3)
    a = list(slice_windows(source_for(tl), spec(seed=11)))
    shuffled = to_table(tl).sample(frac=1.0, random_state=1).reset_index(drop=True)
    scheme = FixedWidthScheme(
        np.datetime64(0, "s").astype("datetime64[ns]"), np.timedelta64(DAY, "s")
    )
    b = list(slice_windows(TableSource(shuffled, scheme, name="synthetic"), spec(seed=11)))
    assert [w.plan for w in a] == [w.plan for w in b]
    for wa, wb in zip(a, b, strict=True):
        assert np.array_equal(wa.train.row_id, wb.train.row_id)
        for sa, sb in zip(wa.eval_slots(), wb.eval_slots(), strict=True):
            assert np.array_equal(sa.row_id, sb.row_id)


def test_a_slots_subsample_is_the_same_in_every_window_that_contains_it():
    tl = ten_slots()
    seen: dict[str, np.ndarray] = {}
    for w in slice_windows(source_for(tl), spec(nT=2, nE=3, stride=1)):
        for s in w.eval_slots():
            if s.ref.slot_id in seen:
                assert np.array_equal(seen[s.ref.slot_id], s.row_id)
            seen[s.ref.slot_id] = s.row_id
    assert len(seen) >= 4


def test_a_different_seed_draws_different_malware():
    tl = ten_slots()
    a = next(next(iter(slice_windows(source_for(tl), spec(seed=1)))).eval_slots())
    b = next(next(iter(slice_windows(source_for(tl), spec(seed=2)))).eval_slots())
    assert not np.array_equal(a.row_id, b.row_id)


# --- past-only duplicate accounting (ADR-0004 item 6) ---------------------------------------


def test_seen_before_mask_marks_rows_whose_vector_is_in_the_given_past_pool():
    pool = np.array(["a", "b", "c"])
    now = np.array(["x", "b", "a", "y"])
    assert seen_before_mask(now, pool).tolist() == [False, True, True, False]


def test_manifest_counts_evaluation_rows_whose_vector_was_in_the_training_window():
    tl = ten_slots()
    table = to_table(tl)
    hashes = np.array([f"v{i}" for i in tl.row_id])
    in_train = np.flatnonzero(tl.ts < 3 * DAY)[:3]  # rows of the three training slots
    # Three benign rows of the first evaluation slot (never dropped by C3) repeat those vectors.
    in_eval = np.flatnonzero((tl.ts >= 3 * DAY) & (tl.ts < 4 * DAY) & (tl.y == 0))[:3]
    hashes[in_eval] = hashes[in_train]
    table["fv"] = hashes
    scheme = FixedWidthScheme(
        np.datetime64(0, "s").astype("datetime64[ns]"), np.timedelta64(DAY, "s")
    )
    src = TableSource(table, scheme, fv_col="fv", name="synthetic")
    log = SliceLog()
    window = next(iter(slice_windows(src, spec(nT=3, nE=1, stride=1), log)))
    slot = next(window.eval_slots())
    assert slot.n_seen_in_initial_train == 3
    row = next(r for r in log.window_rows if r["role"] == "eval")
    assert row["n_seen_in_initial_train"] == 3


# --- schemes and parameters -----------------------------------------------------------------


def test_calendar_month_scheme_names_and_bounds_slots_like_the_cache():
    days = pd.date_range("2020-01-10", "2020-04-20", freq="D")
    table = pd.DataFrame(
        {"ts": days, "label": (np.arange(len(days)) % 3 == 0).astype(np.int8)}
    ).assign(row_id=lambda d: np.arange(len(d), dtype=np.int64))
    src = TableSource(table, CalendarMonthScheme(), name="synthetic")
    refs = [row.ref for row in src.slot_table()]
    assert [r.slot_id for r in refs] == [
        "month:2020-01",
        "month:2020-02",
        "month:2020-03",
        "month:2020-04",
    ]
    assert refs[1].start == np.datetime64("2020-02-01") and refs[1].end == np.datetime64(
        "2020-03-01"
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"nT": 0},
        {"nE": 0},
        {"stride": 0},
        {"target_ratio": 0.0},
        {"target_ratio": 1.0},
        {"min_malware": 0},
        {"seed": -1},
    ],
)
def test_window_spec_rejects_invalid_values(bad):
    with pytest.raises(ValueError):
        spec(**bad)


def test_window_spec_digest_is_stable_and_sensitive_to_every_field():
    base = spec()
    assert base.digest() == spec().digest()
    for change in ({"nT": 4}, {"nE": 3}, {"stride": 2}, {"target_ratio": 0.05}, {"seed": 1}):
        assert base.digest() != spec(**change).digest()
    assert json.loads(base.to_json())["nT"] == 3


# --- manifests ------------------------------------------------------------------------------


def test_manifest_is_written_with_every_run(tmp_path):
    tl = build_timeline({k: STANDARD for k in range(8) if k != 4})
    src = source_for(tl)
    log = SliceLog()
    ws = spec(nT=2, nE=2, stride=1)
    for window in slice_windows(src, ws, log):
        list(window.eval_slots())
    paths = log.write(tmp_path, spec=ws, source=src)
    slot_manifest = pd.read_csv(paths["slot_manifest"])
    window_manifest = pd.read_csv(paths["window_manifest"])
    run = json.loads(paths["run"].read_text(encoding="utf-8"))
    assert {"slot_id", "start", "end", "n_rows", "n_malware", "n_benign", "usable"} <= set(
        slot_manifest.columns
    )
    assert {"window_id", "role", "slot_id", "n_malware_after", "share_malware_discarded"} <= set(
        window_manifest.columns
    )
    assert slot_manifest["n_rows"].sum() == len(tl.row_id)
    assert run["spec_digest"] == ws.digest() and run["spec"]["seed"] == 0
    assert run["source"]["name"] == "synthetic"
    assert {"python", "numpy", "pandas"} <= set(run["packages"])
    assert run["counts"]["windows"] == len(set(window_manifest["window_id"]))
