"""Regression tests for the Phase 3 leakage review (docs/reviews/slicer-review.md).

Each test is named for its finding. They were written before the fixes and failed on the
code as reviewed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from timelines import DAY, build_timeline, to_table

from driftwatch.data import constraints
from driftwatch.data.constraints import C2Violation, C3Violation
from driftwatch.data.loaders import CachedDataset
from driftwatch.data.presets import CachedSource, placeholder_dates
from driftwatch.data.slicer import (
    RowFilter,
    SliceLog,
    SlotInfo,
    SlotRows,
    WindowSpec,
    plan_slots,
    slice_windows,
)
from driftwatch.data.tables import FixedWidthScheme, TableSource

STANDARD = (40, 180)
ANCHOR = datetime(2019, 8, 26, tzinfo=UTC)


def spec(**kw) -> WindowSpec:
    base = {"nT": 3, "nE": 2, "stride": 1, "target_ratio": 0.10, "min_malware": 2, "seed": 0}
    return WindowSpec(**{**base, **kw})


def scheme_for(tl) -> FixedWidthScheme:
    return FixedWidthScheme(
        np.datetime64(tl.anchor, "s").astype("datetime64[ns]"), np.timedelta64(tl.width, "s")
    )


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Correlation of a position/handle sequence with a 0/1 label (point-biserial).

    Rank correlation would be wrong here: tied labels get ranks by position.
    """
    return float(np.corrcoef(np.asarray(a, float), np.asarray(b, float))[0, 1])


def class_linked_table(n_slots: int = 6) -> tuple[pd.DataFrame, np.ndarray]:
    """Benign rows early in each slot, malware late: row order is class-linked, as in BODMAS."""
    rng = np.random.default_rng(5)
    rows = []
    for k in range(n_slots):
        lo = k * DAY
        for _ in range(180):  # benign: first quarter of the slot (a "midnight" batch)
            rows.append((lo + int(rng.integers(0, DAY // 4)), 0))
        for _ in range(40):  # malware: second half
            rows.append((lo + int(rng.integers(DAY // 2, DAY)), 1))
    ts = np.array([r[0] for r in rows], dtype=np.int64)
    y = np.array([r[1] for r in rows], dtype=np.int8)
    table = pd.DataFrame(
        {
            "ts": pd.to_datetime(ts, unit="s").astype("datetime64[ns]"),
            "label": y,
            "row_id": np.arange(len(rows), dtype=np.int64),
        }
    )
    X = np.zeros((len(rows), 4), dtype=np.float32)
    X[:, 0] = table["row_id"] + 1
    return table, X


# --- finding 1: the public view is opaque ---------------------------------------------------


def test_f1_public_row_order_and_handles_carry_no_class_signal():
    table, X = class_linked_table()
    src = TableSource(
        table,
        FixedWidthScheme(np.datetime64(0, "s").astype("datetime64[ns]"), np.timedelta64(DAY, "s")),
        x=X,
        name="linked",
    )
    window = next(iter(slice_windows(src, spec(nT=2, nE=3))))
    for slot in window.eval_slots():
        n = len(slot.y)
        assert abs(spearman(np.arange(n), slot.y)) > 0.5, "the test has no power: order not linked"
        public = slot.public()
        assert np.array_equal(np.sort(public.row_id), np.arange(n)), "handles must be 0..n-1"
        position = np.arange(n)
        # Resolve what a selector would query back to labels, as the queue does.
        y_in_public_order = slot.y[slot.resolve(public.row_id)]
        assert abs(spearman(position, y_in_public_order)) < 0.25
        assert abs(spearman(public.row_id, y_in_public_order)) < 0.25


def test_f1_public_features_follow_their_handles_and_resolve_to_true_rows():
    table, X = class_linked_table()
    src = TableSource(
        table,
        FixedWidthScheme(np.datetime64(0, "s").astype("datetime64[ns]"), np.timedelta64(DAY, "s")),
        x=X,
        name="linked",
    )
    slot = next(next(iter(slice_windows(src, spec(nT=2, nE=2)))).eval_slots())
    public = slot.public()
    true_ids = slot.row_id[slot.resolve(public.row_id)]
    assert np.array_equal(public.X[:, 0].astype(np.int64) - 1, true_ids)
    assert not np.shares_memory(public.X, slot.X), "the public view must be an isolated copy"
    public.X[:] = -1.0  # a consumer standardising in place must not touch the scoring features
    assert (slot.X[:, 0] > 0).all()


def test_f1_public_order_is_seeded_and_is_not_time_order():
    table, X = class_linked_table()
    scheme = FixedWidthScheme(
        np.datetime64(0, "s").astype("datetime64[ns]"), np.timedelta64(DAY, "s")
    )

    def public_ids(seed: int) -> np.ndarray:
        src = TableSource(table, scheme, x=X, name="l")
        w = next(iter(slice_windows(src, spec(seed=seed, target_ratio=0.5))))
        return next(w.eval_slots()).public().X[:, 0]  # X column 0 holds row_id + 1

    a = public_ids(0)
    assert np.array_equal(a, public_ids(0))
    assert not np.all(np.diff(a) > 0), "the public order is still time order"


# --- finding 2: NO_GAP is inconclusive, not a pass ------------------------------------------


def test_f2_canary_script_exits_nonzero_for_no_gap(tmp_path):
    import json
    import subprocess

    from test_leakage_canary import ROOT, _canary_cmd, _write_drifting_bodmas_raw

    from driftwatch.data.build import build_dataset
    from driftwatch.data.cache import Layout

    _write_drifting_bodmas_raw(tmp_path, drift=0.0)
    build_dataset("bodmas", Layout(tmp_path), raw_layout=Layout(tmp_path), batch_size=256)
    out = tmp_path / "canary.json"
    proc = subprocess.run(
        _canary_cmd(tmp_path, out, nT=2, nE=6, min_malware=5),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == "NO_GAP"
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "INCONCLUSIVE" in proc.stdout


# --- finding 4: C2 on the raw slot and on training slots ------------------------------------


class Hostile:
    """A source that smuggles a row from outside a slot's window into that slot."""

    def __init__(self, inner: TableSource, slot_id: str, *, label: int, shift: np.timedelta64):
        self.inner, self.slot_id, self.label, self.shift = inner, slot_id, label, shift
        self.name, self.sparse = inner.name, inner.sparse

    def slot_table(self):
        out = []
        for info in self.inner.slot_table():
            if info.ref.slot_id == self.slot_id:
                mal = info.n_malware + (self.label == 1)
                ben = info.n_benign + (self.label == 0)
                info = SlotInfo(info.ref, info.n_rows + 1, mal, ben)
            out.append(info)
        return out

    def load_slot(self, slot_id):
        rows = self.inner.load_slot(slot_id)
        if slot_id != self.slot_id:
            return rows
        later = self.shift > np.timedelta64(0, "s")
        stray_ts = rows.ref.end + self.shift if later else rows.ref.start + self.shift
        return SlotRows(
            ref=rows.ref,
            y=np.append(rows.y, np.int8(self.label)),
            ts=np.append(rows.ts, stray_ts),
            row_id=np.append(rows.row_id, np.int64(10_000_000)),
            X=None,
            fv_hash=None,
        )

    def provenance(self):
        return self.inner.provenance()


def test_f4_c2_is_checked_on_the_raw_slot_even_if_the_stray_row_would_be_subsampled_away():
    # 500 malware, 20 benign: C3 keeps 2 malware, so the stray malware row is almost surely
    # dropped before a post-subsampling check could see it.
    tl = build_timeline({k: (500, 20) for k in range(5)}, seed=2)
    src = Hostile(
        TableSource(to_table(tl), scheme_for(tl), name="h"),
        "w:" + str(np.datetime64(tl.anchor + 3 * DAY, "s")),
        label=1,
        shift=np.timedelta64(3600, "s"),
    )
    window = next(iter(slice_windows(src, spec(nT=3, nE=2, min_malware=2))))
    with pytest.raises(C2Violation):
        list(window.eval_slots())


def test_f4_training_slots_are_window_checked_too():
    tl = build_timeline({k: STANDARD for k in range(5)}, seed=2)
    stray_in = "w:" + str(np.datetime64(tl.anchor + 1 * DAY, "s"))
    src = Hostile(
        TableSource(to_table(tl), scheme_for(tl), name="h"),
        stray_in,
        label=0,
        shift=np.timedelta64(-3600, "s"),  # an hour before the slot: older, so C1 is unaffected
    )
    with pytest.raises(C2Violation):
        next(iter(slice_windows(src, spec(nT=3, nE=2))))


# --- finding 5: seen-before accounting is past-only against the initial window --------------


def test_f5_a_vector_that_only_appears_in_a_later_slot_counts_zero():
    tl = build_timeline({k: STANDARD for k in range(8)}, seed=4)
    table = to_table(tl)
    hashes = np.array([f"v{i}" for i in tl.row_id])
    first_eval = np.flatnonzero((tl.ts >= 3 * DAY) & (tl.ts < 4 * DAY) & (tl.y == 0))[:2]
    second_eval = np.flatnonzero((tl.ts >= 4 * DAY) & (tl.ts < 5 * DAY) & (tl.y == 0))[:2]
    hashes[first_eval] = hashes[second_eval]  # shared only between two evaluation slots
    table["fv"] = hashes
    src = TableSource(table, scheme_for(tl), fv_col="fv", name="s")
    log = SliceLog()
    window = next(iter(slice_windows(src, spec(nT=3, nE=2), log)))
    slots = list(window.eval_slots())
    assert [s.n_seen_in_initial_train for s in slots] == [0, 0]
    rows = [r for r in log.window_rows if r["role"] == "eval"]
    assert [r["n_seen_in_initial_train"] for r in rows] == [0, 0]


# --- finding 7: the call sites raise the specific violation ---------------------------------


def test_f7_a_subsampler_that_drops_a_benign_row_raises_c3_from_the_slicer(monkeypatch):
    original = constraints.subsample_malware

    def drop_one_benign(y, ratio, seed, slot_id):
        kept = original(y, ratio, seed, slot_id)
        benign = kept[np.asarray(y)[kept] == 0]
        return kept[kept != benign[0]]

    monkeypatch.setattr(constraints, "subsample_malware", drop_one_benign)
    tl = build_timeline({k: STANDARD for k in range(6)})
    src = TableSource(to_table(tl), scheme_for(tl), name="s")
    window = next(iter(slice_windows(src, spec())))
    with pytest.raises(C3Violation):
        list(window.eval_slots())


# --- finding 8: production-like configuration on the fixture caches -------------------------


def test_f8_rows_features_and_labels_stay_aligned_after_exclusion(built_data):
    rule = placeholder_dates(min_ties=3)
    src = CachedSource("bodmas", built_data, length="1w", anchor=ANCHOR, exclude=rule)
    truth_data = CachedDataset("bodmas", built_data)
    checked = 0
    for info in src.slot_table():
        if info.n_rows == 0:
            continue
        got = src.load_slot(info.ref.slot_id)
        truth = truth_data.load_slot(info.ref.slot_id, length="1w", anchor=ANCHOR)
        drop = (truth.meta["ts_date_only"] & (truth.meta["ts_tie_count"] >= 3)).to_numpy()
        keep = np.flatnonzero(~drop)
        assert np.array_equal(got.row_id, truth.meta["row_id"].to_numpy()[keep])
        assert np.array_equal(got.y, truth.y[keep])
        assert np.array_equal(got.X, truth.X[keep])
        assert len(got) == info.n_rows
        checked += 1
    assert checked >= 3


# --- finding 9: window ids carry the configuration; counts are logged without a manifest ----


def test_f9_window_id_changes_with_ratio_and_seed():
    tl = build_timeline({k: STANDARD for k in range(8)})
    src = TableSource(to_table(tl), scheme_for(tl), name="s")
    ids = {
        (r, s): next(iter(slice_windows(src, spec(target_ratio=r, seed=s)))).plan.window_id
        for r in (0.10, 0.05)
        for s in (0, 1)
    }
    assert len(set(ids.values())) == 4


def test_f9_c3_counts_are_logged_even_without_a_manifest(caplog):
    tl = build_timeline({k: STANDARD for k in range(6)})
    src = TableSource(to_table(tl), scheme_for(tl), name="s")
    window = next(iter(slice_windows(src, spec())))
    with caplog.at_level(logging.INFO, logger="driftwatch.data.slicer"):
        list(window.eval_slots())
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "C3" in text and "malware 40 -> 20" in text and "discarded" in text


# --- finding 10: row filters never see labels -----------------------------------------------


def test_f10_a_row_filter_cannot_read_columns_it_did_not_declare():
    tl = build_timeline({k: STANDARD for k in range(4)})
    peeking = RowFilter("peeks at labels", lambda m: m["label"] == 1, columns=("ts",))
    with pytest.raises(KeyError):
        peeking(to_table(tl))
    honest = RowFilter(
        "early rows", lambda m: m["ts"] < pd.Timestamp("1970-01-02"), columns=("ts",)
    )
    assert honest(to_table(tl)).dtype == bool


def test_f10_the_cache_planner_does_not_hand_labels_to_the_filter(built_data):
    seen_columns: list[list[str]] = []

    def spy(meta: pd.DataFrame):
        seen_columns.append(list(meta.columns))
        return np.zeros(len(meta), dtype=bool)

    rule = RowFilter("spy", spy, columns=("ts_date_only",))
    src = CachedSource("bodmas", built_data, length="1w", anchor=ANCHOR, exclude=rule)
    src.slot_table()
    src.load_slot(next(i.ref.slot_id for i in src.slot_table() if i.n_rows))
    assert seen_columns and all(cols == ["ts_date_only"] for cols in seen_columns)


# --- finding 12: rows read as UTC although published without an offset ----------------------


def test_f12_naive_timestamp_rows_are_counted_per_slot(built_data):
    src = CachedSource("bodmas", built_data, length="1w", anchor=ANCHOR)
    by_id = {p.ref.slot_id: p for p in plan_slots(src, spec(target_ratio=0.4, min_malware=1))}
    total = sum(p.n_naive_ts for p in by_id.values())
    assert total == 1  # the fixture plants exactly one timestamp without a UTC offset
    log = SliceLog()
    log.record_plan(list(by_id.values()), None)  # type: ignore[arg-type]
    assert sum(r["n_naive_ts"] for r in log.slot_rows) == 1


# --- finding 13: a slot whose base unit is emptied by the filter is partial -----------------


def test_f13_a_unit_emptied_by_exclusion_makes_the_slot_partial(built_data):
    first_week = RowFilter(
        "drop week 2019-W35",
        lambda m: m["ts"] < pd.Timestamp("2019-09-02", tz="UTC"),
        columns=("ts",),
    )
    src = CachedSource("bodmas", built_data, length="2w", anchor=ANCHOR, exclude=first_week)
    planned = {p.ref.slot_id: p for p in plan_slots(src, spec(target_ratio=0.4, min_malware=1))}
    slot = planned["2w:2019-08-26"]
    assert slot.n_rows > 0 and slot.structural == "partial"
    assert slot.usable is False and slot.skip_reason == "partial"
