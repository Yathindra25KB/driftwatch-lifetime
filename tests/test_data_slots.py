"""Slot schemes and the loader: no row in two slots, monotone time, determinism."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from driftwatch.data.loaders import CachedDataset, iter_slots, load_slot
from driftwatch.data.slots import SLOT_LENGTHS, build_slots, unit_end, unit_start

SCHEMES = [(ds, length) for ds, lengths in SLOT_LENGTHS.items() for length in lengths]


def _dense(x):
    return x.toarray() if sp.issparse(x) else np.asarray(x)


@pytest.mark.parametrize(("dataset", "length"), SCHEMES)
def test_no_row_in_two_slots(built_data, dataset, length):
    data = CachedDataset(dataset, built_data)
    ids = [s.meta["row_id"].to_numpy() for s in data.iter_slots(length)]
    flat = np.concatenate(ids)
    assert flat.size == np.unique(flat).size
    all_ids = np.concatenate([data.load_unit(u)[1]["row_id"].to_numpy() for u in data.units])
    assert set(flat) == set(all_ids)


@pytest.mark.parametrize(("dataset", "length"), SCHEMES)
def test_slot_timestamps_monotone_and_inside_window(built_data, dataset, length):
    previous_max = None
    for s in iter_slots(dataset, length, built_data):
        ts = pd.to_datetime(s.meta["ts"], utc=True)
        assert ts.is_monotonic_increasing
        assert ts.min() >= pd.Timestamp(s.slot.start) and ts.max() < pd.Timestamp(s.slot.end)
        if previous_max is not None:
            assert ts.min() > previous_max
        previous_max = ts.max()


@pytest.mark.parametrize(("dataset", "length"), SCHEMES)
def test_loader_is_deterministic(built_data, dataset, length):
    a = list(iter_slots(dataset, length, built_data))
    b = list(iter_slots(dataset, length, built_data))
    assert [s.slot for s in a] == [s.slot for s in b]
    for x, y in zip(a, b, strict=True):
        np.testing.assert_array_equal(_dense(x.X), _dense(y.X))
        np.testing.assert_array_equal(x.y, y.y)
        pd.testing.assert_frame_equal(x.meta, y.meta)


@pytest.mark.parametrize(
    ("dataset", "coarse"), [("lamda", "quarter"), ("bodmas", "2w"), ("bodmas", "4w")]
)
def test_coarse_slots_are_unions_of_base_units(built_data, dataset, coarse):
    data = CachedDataset(dataset, built_data)
    for s in data.slots(coarse):
        got = data.load_slot(s)
        parts = [data.load_unit(u)[1] for u in s.units]
        expected = pd.concat(parts, ignore_index=True)["row_id"] if parts else pd.Series([])
        assert got.meta["row_id"].tolist() == expected.tolist()
        assert all(s.start <= unit_start(u) and unit_end(u) <= s.end for u in s.units)


def test_lamda_2015_is_a_gap(built_data):
    data = CachedDataset("lamda", built_data)
    by_id = {s.slot_id: s for s in data.slots("quarter")}
    assert all(by_id[f"quarter:2015Q{q}"].is_gap for q in range(1, 5))
    months = {s.slot_id: s for s in data.slots("month")}
    assert all(months[f"month:2015-{m:02d}"].is_gap for m in range(1, 13))


def test_iter_slots_skips_gaps_unless_asked(built_data):
    with_gaps = list(iter_slots("bodmas", "1w", built_data, include_gaps=True))
    without = list(iter_slots("bodmas", "1w", built_data))
    assert len(with_gaps) > len(without) and all(len(s) for s in without)
    gap = next(s for s in with_gaps if s.slot.is_gap)
    assert len(gap) == 0 and gap.X.shape == (0, 2381)


def test_load_slot_by_id(built_data):
    s = load_slot("lamda", "month:2013-02", built_data)
    assert len(s) == 3 and sp.issparse(s.X) and s.X.dtype == np.int8  # planted small month


def test_unknown_slot_length_is_rejected():
    with pytest.raises(ValueError):
        build_slots("lamda", "1w", ["2013-01"])
    with pytest.raises(ValueError):
        build_slots("bodmas", "month", ["2019-W35"])


def test_week_slots_anchor_at_first_week():
    slots = build_slots("bodmas", "2w", ["2019-W35", "2019-W38"])
    assert [s.slot_id for s in slots] == ["2w:2019-08-26", "2w:2019-09-09"]
    assert slots[0].units == ("2019-W35",) and slots[1].units == ("2019-W38",)
