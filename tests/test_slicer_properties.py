"""Property-based tests: random synthetic timelines against the independent oracle.

Timelines have random slot widths and grid phase, empty slots (gaps), tiny and large slots
(so the size gate fires), a malware share from 1% to 90%, and rows pinned to slot
boundaries. For every one of them the slicer must produce exactly the windows the protocol
allows, and every row it yields must satisfy C1-C3 when recomputed from raw timestamps.
"""

from __future__ import annotations

import numpy as np
from hypothesis import assume, event, given, settings
from hypothesis import strategies as st
from slicer_oracle import RawTimeline, assert_window_matches_oracle, expected_windows, slot_index_of
from timelines import DAY, build_timeline, to_table

from driftwatch.data.slicer import SliceLog, WindowSpec, slice_windows
from driftwatch.data.tables import FixedWidthScheme, TableSource

HEALTHY = st.tuples(st.sampled_from([6, 12, 40, 80, 200]), st.sampled_from([120, 200, 400]))
TINY = st.tuples(st.integers(0, 2), st.integers(0, 5))
# About 3 in 4 slots are healthy; the rest are tiny (fail the gate) or empty (a gap).
SLOT = st.one_of(HEALTHY, HEALTHY, HEALTHY, HEALTHY, HEALTHY, HEALTHY, TINY, st.just((0, 0)))


@st.composite
def scenarios(draw) -> tuple[RawTimeline, WindowSpec]:
    width = draw(st.sampled_from([DAY, 2 * DAY, 7 * DAY]))
    anchor = draw(st.integers(0, width - 1))
    n_slots = draw(st.integers(4, 14))
    counts = draw(st.lists(SLOT, min_size=n_slots, max_size=n_slots))
    per_slot = {k: c for k, c in enumerate(counts) if sum(c) > 0}
    assume(per_slot)
    tl = build_timeline(
        per_slot,
        width=width,
        anchor=anchor,
        seed=draw(st.integers(0, 2**16)),
        pin_boundaries=draw(st.booleans()),
    )
    nE = draw(st.one_of(st.none(), st.integers(1, 3)))
    spec = WindowSpec(
        nT=draw(st.integers(1, 2)),
        nE=nE,
        stride=draw(st.integers(1, 3)),
        target_ratio=draw(st.sampled_from([0.05, 0.10, 0.20, 0.40])),
        min_malware=draw(st.integers(1, 5)),
        seed=draw(st.integers(0, 5)),
    )
    return tl, spec


def source_for(tl: RawTimeline, table=None) -> TableSource:
    scheme = FixedWidthScheme(
        np.datetime64(tl.anchor, "s").astype("datetime64[ns]"), np.timedelta64(tl.width, "s")
    )
    return TableSource(to_table(tl) if table is None else table, scheme, name="synthetic")


def keys_of(tl: RawTimeline, window) -> tuple[tuple[int, ...], tuple[int, ...]]:
    train = tuple(slot_index_of(tl, r.start, r.end) for r in window.plan.train)
    evaluation = tuple(slot_index_of(tl, r.start, r.end) for r in window.plan.eval)
    return train, evaluation


@settings(max_examples=200)
@given(scenarios())
def test_slicer_yields_exactly_the_windows_the_protocol_allows(scenario):
    tl, spec = scenario
    windows = list(slice_windows(source_for(tl), spec))
    want = expected_windows(
        tl,
        nT=spec.nT,
        nE=spec.nE,
        stride=spec.stride,
        ratio=spec.target_ratio,
        min_malware=spec.min_malware,
    )
    assert [keys_of(tl, w) for w in windows] == want
    event(f"windows={min(len(windows), 4)}")  # shows in --hypothesis-show-statistics
    for window in windows:
        slots = list(window.eval_slots())
        event(f"below_target_slots={min(sum(s.c3.status == 'below_target' for s in slots), 2)}")
        assert_window_matches_oracle(window, tl, ratio=spec.target_ratio)


@settings(max_examples=60)
@given(scenarios(), st.integers(0, 2**16))
def test_input_row_order_does_not_change_the_output(scenario, shuffle_seed):
    tl, spec = scenario
    shuffled = to_table(tl).sample(frac=1.0, random_state=shuffle_seed).reset_index(drop=True)
    a = list(slice_windows(source_for(tl), spec))
    b = list(slice_windows(source_for(tl, shuffled), spec))
    assert [w.plan for w in a] == [w.plan for w in b]
    for wa, wb in zip(a, b, strict=True):
        assert np.array_equal(np.sort(wa.train.row_id), np.sort(wb.train.row_id))
        for sa, sb in zip(wa.eval_slots(), wb.eval_slots(), strict=True):
            assert np.array_equal(sa.row_id, sb.row_id)


@settings(max_examples=60)
@given(scenarios())
def test_same_seed_same_output_and_every_slot_subsample_is_window_independent(scenario):
    tl, spec = scenario
    first_run: dict[str, bytes] = {}
    for window in slice_windows(source_for(tl), spec):
        for slot in window.eval_slots():
            seen = first_run.setdefault(slot.ref.slot_id, slot.row_id.tobytes())
            assert seen == slot.row_id.tobytes()  # the same slot, in another window, same draw
    again: dict[str, bytes] = {}
    for window in slice_windows(source_for(tl), spec):
        for slot in window.eval_slots():
            again[slot.ref.slot_id] = slot.row_id.tobytes()
    assert again == first_run


@settings(max_examples=80)
@given(scenarios())
def test_every_slot_is_accounted_for_and_every_skip_has_a_reason(scenario):
    tl, spec = scenario
    log = SliceLog()
    list(slice_windows(source_for(tl), spec, log))
    populated = {int(k) for k in np.unique(tl.cell_of(tl.ts))}
    assert len(log.slot_rows) == max(populated) - min(populated) + 1  # gaps are listed too
    assert sum(r["n_rows"] for r in log.slot_rows) == len(tl.row_id)
    for row in log.slot_rows:
        if row["usable"]:
            assert row["skip_reason"] == ""
        else:
            assert row["skip_reason"] in {"gap", "size_gate"}
            assert (row["skip_reason"] == "gap") == (row["n_rows"] == 0)


@settings(max_examples=60)
@given(scenarios())
def test_no_window_ever_contains_an_unusable_slot_or_a_row_twice(scenario):
    tl, spec = scenario
    log = SliceLog()
    unusable = set()
    windows = list(slice_windows(source_for(tl), spec, log))
    for row in log.slot_rows:
        if not row["usable"]:
            unusable.add(row["slot_id"])
    for window in windows:
        ids = [r.slot_id for r in (*window.plan.train, *window.plan.eval)]
        assert not unusable & set(ids)
        pool = np.concatenate([window.train.row_id] + [s.row_id for s in window.eval_slots()])
        assert pool.size == np.unique(pool).size
