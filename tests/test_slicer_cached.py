"""The slicer on the dataset caches (built from the committed synthetic fixture).

These tests tie the cache adapter to the independent oracle: the oracle is rebuilt straight
from the cache's meta.parquet files, not from the loaders the adapter uses.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import scipy.sparse as sp
from slicer_oracle import RawTimeline, assert_window_matches_oracle, expected_windows, slot_index_of

from driftwatch.data.cache import Layout
from driftwatch.data.loaders import CachedDataset
from driftwatch.data.presets import PRESETS, CachedSource, placeholder_dates
from driftwatch.data.slicer import WindowSpec, plan_slots, slice_windows

ANCHOR = datetime(2019, 8, 26, tzinfo=UTC)
WEEK = 7 * 86400
SPEC = WindowSpec(nT=1, nE=1, stride=1, target_ratio=0.40, min_malware=2, seed=0)


def raw_timeline(root, dataset: str, *, anchor: datetime, width: int) -> RawTimeline:
    """Rebuild a timeline from the unit meta files, bypassing the loaders."""
    cache = Layout(root).cache(dataset) / "units"
    frames = [pq.read_table(p / "meta.parquet").to_pandas() for p in sorted(cache.iterdir())]
    meta = pd.concat(frames, ignore_index=True)
    ts = meta["ts"].dt.tz_convert("UTC").dt.tz_localize(None).astype("datetime64[s]")
    return RawTimeline(
        ts=ts.astype("int64").to_numpy(),
        y=meta["label"].to_numpy(dtype=np.int8),
        row_id=meta["row_id"].to_numpy(dtype=np.int64),
        anchor=int(anchor.timestamp()),
        width=width,
    )


def keys_of(tl, window):
    return (
        tuple(slot_index_of(tl, r.start, r.end) for r in window.plan.train),
        tuple(slot_index_of(tl, r.start, r.end) for r in window.plan.eval),
    )


def test_bodmas_weekly_windows_match_the_oracle_built_from_the_cache(built_data):
    src = CachedSource("bodmas", built_data, length="1w", anchor=ANCHOR)
    tl = raw_timeline(built_data, "bodmas", anchor=ANCHOR, width=WEEK)
    windows = list(slice_windows(src, SPEC))
    want = expected_windows(tl, nT=1, nE=1, stride=1, ratio=0.40, min_malware=2)
    assert want, "the fixture must support at least one window or this test proves nothing"
    assert [keys_of(tl, w) for w in windows] == want
    for window in windows:
        assert_window_matches_oracle(window, tl, ratio=0.40)


def test_feature_rows_come_back_aligned_with_the_rows_the_slicer_names(built_data):
    src = CachedSource("bodmas", built_data, length="1w", anchor=ANCHOR)
    window = next(iter(slice_windows(src, SPEC)))
    slot = next(window.eval_slots())
    data = CachedDataset("bodmas", built_data)
    truth = data.load_slot(slot.ref.slot_id, length="1w", anchor=ANCHOR)
    order = {rid: i for i, rid in enumerate(truth.meta["row_id"].to_numpy())}
    rows = [order[r] for r in slot.row_id]
    assert slot.X.shape == (len(slot.row_id), data.n_features)
    assert np.array_equal(slot.X, truth.X[rows])
    assert np.array_equal(slot.y, truth.y[rows])


def test_two_week_slots_missing_a_week_are_partial_and_unusable(built_data):
    src = CachedSource("bodmas", built_data, length="2w", anchor=ANCHOR)
    planned = {p.ref.slot_id: p for p in plan_slots(src, SPEC)}
    partial = [
        s.slot_id for s in CachedDataset("bodmas", built_data).slots("2w", ANCHOR) if s.is_partial
    ]
    assert partial, "the fixture has two-week slots with a missing week"
    for slot_id in partial:
        assert planned[slot_id].structural == "partial"
        assert planned[slot_id].usable is False and planned[slot_id].skip_reason == "partial"


def test_lamda_slots_load_sparse_int8_and_are_never_densified(built_data):
    src = CachedSource("lamda", built_data, length="month")
    assert src.sparse
    loaded = 0
    for row in src.slot_table():
        if row.n_rows == 0:
            continue
        rows = src.load_slot(row.ref.slot_id)
        assert sp.issparse(rows.X) and rows.X.dtype == np.int8
        assert rows.X.shape[0] == row.n_rows == len(rows.y) == len(rows.ts)
        loaded += 1
    assert loaded >= 3


def test_lamda_month_ids_and_bounds_match_the_cache_slots(built_data):
    src = CachedSource("lamda", built_data, length="month")
    theirs = CachedDataset("lamda", built_data).slots("month")
    assert [r.ref.slot_id for r in src.slot_table()] == [s.slot_id for s in theirs]
    first = src.slot_table()[0].ref
    assert first.start == np.datetime64(theirs[0].start.replace(tzinfo=None), "ns")


def test_study_span_removes_slots_and_rows_outside_it(built_data):
    start, end = ANCHOR, datetime(2019, 10, 7, tzinfo=UTC)
    src = CachedSource(
        "bodmas", built_data, length="1w", anchor=ANCHOR, study_start=start, study_end=end
    )
    table = src.slot_table()
    assert table[0].ref.start == np.datetime64("2019-08-26", "ns")
    assert table[-1].ref.end <= np.datetime64("2019-10-07", "ns")
    tl = raw_timeline(built_data, "bodmas", anchor=ANCHOR, width=WEEK)
    inside = (tl.ts >= int(start.timestamp())) & (tl.ts < int(end.timestamp()))
    assert sum(r.n_rows for r in table) == int(inside.sum())


def test_placeholder_rule_looks_at_the_timestamp_pattern_only():
    meta = pd.DataFrame(
        {
            "ts_date_only": [True, True, True, False, True],
            "ts_tie_count": [5877, 1000, 999, 5000, 1],
            "label": [0, 1, 0, 0, 0],  # the class plays no part in the rule
        }
    )
    rule = placeholder_dates(min_ties=1000)
    assert rule(meta).tolist() == [True, True, False, False, False]
    assert "1000" in rule.name


def test_excluded_rows_are_counted_by_class_in_the_provenance(built_data):
    rule = placeholder_dates(min_ties=3)  # the fixture plants a tie of three date-only rows
    plain = CachedSource("bodmas", built_data, length="1w", anchor=ANCHOR)
    filtered = CachedSource("bodmas", built_data, length="1w", anchor=ANCHOR, exclude=rule)
    total = lambda s: sum(r.n_rows for r in s.slot_table())  # noqa: E731
    assert total(plain) - total(filtered) == 3
    excluded = filtered.provenance()["excluded_rows"]
    assert excluded["malware"] + excluded["benign"] == 3
    assert sum(r.n_excluded for r in filtered.slot_table()) == 3
    assert filtered.provenance()["row_filter"] == rule.name


def test_presets_carry_the_accepted_adr_0004_values():
    lamda, bodmas = PRESETS["lamda"], PRESETS["bodmas"]
    assert lamda.length == "month" and lamda.anchor is None and lamda.exclude is None
    assert bodmas.length == "2w"
    assert bodmas.anchor == ANCHOR and bodmas.study_start == ANCHOR
    assert bodmas.study_end == datetime(2020, 10, 5, tzinfo=UTC)  # the slot grid ends 2020-10-04
    assert bodmas.exclude is not None and "1000" in bodmas.exclude.name
