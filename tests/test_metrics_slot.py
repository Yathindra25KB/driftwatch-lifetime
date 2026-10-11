"""Per-slot F1, FPR, FNR, labels spent, drop events and recovery time (ADR-0006, PROTOCOL D6)."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from driftwatch.data.canary import f1_malware
from driftwatch.metrics.slot import (
    DropEvent,
    drop_events,
    labels_spent,
    recovery_time,
    score_slot,
)

# --- score_slot ------------------------------------------------------------------------------


def test_hand_computed_confusion_matrix() -> None:
    y = [1, 1, 1, 0, 0, 0, 0, 0]
    p = [1, 1, 0, 1, 0, 0, 0, 0]  # tp 2, fn 1, fp 1, tn 4
    s = score_slot(y, p)
    assert (s.tp, s.fn, s.fp, s.tn) == (2, 1, 1, 4)
    assert s.f1 == pytest.approx(4 / 6)  # 2*2 / (2*2 + 1 + 1)
    assert s.fpr == pytest.approx(1 / 5)
    assert s.fnr == pytest.approx(1 / 3)
    assert (s.n, s.n_malware, s.n_benign) == (8, 3, 5)


def test_perfect_all_benign_and_all_malware_predictions() -> None:
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    perfect = score_slot(y, y)
    assert (perfect.f1, perfect.fpr, perfect.fnr) == (1.0, 0.0, 0.0)
    quiet = score_slot(y, np.zeros_like(y))  # a detector that never alarms
    assert (quiet.f1, quiet.fpr, quiet.fnr) == (0.0, 0.0, 1.0)
    loud = score_slot(y, np.ones_like(y))  # alarms on everything
    assert loud.fpr == 1.0 and loud.fnr == 0.0
    assert loud.f1 == pytest.approx(2 * 2 / (2 * 2 + 8))  # F1 collapses at 20% prevalence


@given(
    st.lists(st.tuples(st.integers(0, 1), st.integers(0, 1)), min_size=2, max_size=200).filter(
        lambda rows: {r[0] for r in rows} == {0, 1}
    )
)
def test_f1_agrees_with_the_canary_implementation(rows: list[tuple[int, int]]) -> None:
    y, p = zip(*rows, strict=True)
    s = score_slot(y, p)
    assert s.f1 == pytest.approx(f1_malware(y, p))
    assert 0.0 <= s.fpr <= 1.0 and 0.0 <= s.fnr <= 1.0
    assert s.tp + s.fn == s.n_malware and s.fp + s.tn == s.n_benign


@pytest.mark.parametrize(
    ("y", "p", "message"),
    [
        ([1, 0], [1], "line up"),
        ([1, 2], [1, 0], "0 or 1"),
        ([1, 0], [1, 3], "0 or 1"),
        ([1, 1, 1], [1, 0, 1], "both classes"),
        ([0, 0, 0], [0, 0, 1], "both classes"),
    ],
)
def test_score_slot_rejects_what_it_cannot_score(y: list[int], p: list[int], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        score_slot(y, p)


# --- labels spent ----------------------------------------------------------------------------


def test_labels_spent_sums_queries() -> None:
    assert labels_spent([0, 0, 0]) == 0  # E0 never queries
    assert labels_spent([5, 5, 10]) == 20


@pytest.mark.parametrize("bad", [[-1, 2], [1.5, 2]])
def test_labels_spent_rejects_negative_and_fractional_counts(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        labels_spent(bad)


# --- drop events and recovery ----------------------------------------------------------------


def test_drop_with_recovery() -> None:
    f1 = [0.8, 0.8, 0.8, 0.7, 0.78, 0.8, 0.8]
    events = drop_events(f1)
    assert events == [DropEvent(index=3, level=pytest.approx(0.8), f1=0.7, recovery_slots=1)]


def test_drop_of_exactly_five_points_counts() -> None:
    assert len(drop_events([0.8, 0.8, 0.8, 0.75])) == 1
    assert drop_events([0.8, 0.8, 0.8, 0.76]) == []  # four points is not a drop


def test_no_recovery_is_censored_and_stops_the_scan() -> None:
    events = drop_events([0.8, 0.8, 0.8, 0.5, 0.5, 0.5, 0.3, 0.3])
    assert len(events) == 1
    assert events[0].index == 3 and events[0].recovery_slots is None


def test_events_do_not_overlap_and_are_found_after_recovery() -> None:
    f1 = [0.8, 0.8, 0.8, 0.6, 0.8, 0.8, 0.8, 0.8, 0.5, 0.5, 0.8]
    events = drop_events(f1)
    assert [e.index for e in events] == [3, 8]
    assert [e.recovery_slots for e in events] == [1, 2]


def test_a_flat_series_and_a_short_series_have_no_events() -> None:
    assert drop_events([0.6] * 10) == []
    assert drop_events([0.9, 0.1, 0.1]) == []  # fewer than 3 trailing slots before slot 2


def test_recovery_time_is_measured_in_slots_from_the_drop() -> None:
    f1 = [0.8, 0.8, 0.8, 0.5, 0.6, 0.7, 0.75, 0.8]
    # level 0.8, recovered once F1 >= 0.72: slot 6 (0.75), three slots after the drop at 3
    assert recovery_time(f1, index=3, level=0.8) == 3
    assert recovery_time(f1, index=3, level=0.8, fraction=1.0) == 4
    assert recovery_time(f1[:6], index=3, level=0.8) is None


@given(st.lists(st.floats(0.0, 1.0, allow_nan=False), min_size=4, max_size=40))
def test_every_event_is_a_real_drop_and_its_recovery_is_real(f1: list[float]) -> None:
    for e in drop_events(f1):
        assert e.level - f1[e.index] >= 0.05 - 1e-9
        if e.recovery_slots is not None:
            assert f1[e.index + e.recovery_slots] >= 0.9 * e.level - 1e-12
            assert all(v < 0.9 * e.level for v in f1[e.index + 1 : e.index + e.recovery_slots])
