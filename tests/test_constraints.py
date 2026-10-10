"""C1-C3 exactly as the Build Guide defines them (docs/PROTOCOL.md section 4).

- C1: "Every training sample is older than every test sample. Split by first-seen date,
  never randomly."
- C2: "In each test slot, malware and goodware come from the same time window. Evaluate slot
  by slot with both classes from that slot."
- C3: "The test set reflects the in-the-wild malware share ... Subsample malware to a stated
  ratio; report a sensitivity check."

Every check raises an exception. None of them warns. A test here is never weakened to get
green: if one looks wrong, write an ADR and ask the researcher.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from driftwatch.data.constraints import (
    C1Violation,
    C2Violation,
    C3Violation,
    ConstraintViolation,
    check_c1,
    check_c2,
    check_c3,
    subsample_malware,
    target_malware_count,
)

START = np.datetime64("2020-03-01T00:00:00")
END = np.datetime64("2020-03-15T00:00:00")


def at(seconds: int) -> np.datetime64:
    return START + np.timedelta64(seconds, "s")


def stamps(*seconds: int) -> np.ndarray:
    return np.array([at(s) for s in seconds], dtype="datetime64[s]")


def labels(n_malware: int, n_benign: int) -> np.ndarray:
    return np.array([1] * n_malware + [0] * n_benign, dtype=np.int8)


# --- the exception contract -----------------------------------------------------------------


def test_violations_are_exceptions_not_warnings():
    for cls in (C1Violation, C2Violation, C3Violation):
        assert issubclass(cls, ConstraintViolation)
        assert issubclass(ConstraintViolation, Exception)
        assert not issubclass(ConstraintViolation, Warning)


def test_checks_never_warn_they_raise():
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any warning would become an exception here
        with pytest.raises(C1Violation):
            check_c1(stamps(10), stamps(5))


# --- C1: every training sample is older than every evaluation sample ------------------------


def test_c1_passes_when_all_training_is_older():
    check_c1(stamps(0, 5, 9), stamps(10, 11, 99))


def test_c1_raises_when_one_training_sample_is_newer_than_the_earliest_test_sample():
    with pytest.raises(C1Violation):
        check_c1(stamps(0, 5, 11), stamps(10, 12))  # one leaked training sample at 11


def test_c1_is_strict_equal_timestamps_violate():
    with pytest.raises(C1Violation):
        check_c1(stamps(0, 10), stamps(10, 20))


def test_c1_is_independent_of_row_order():
    train, evaluation = stamps(9, 0, 5), stamps(99, 10, 11)
    check_c1(train, evaluation)
    check_c1(train[::-1], evaluation[::-1])


@pytest.mark.parametrize("empty", ["train", "eval"])
def test_c1_cannot_be_validated_on_an_empty_side(empty):
    train = stamps() if empty == "train" else stamps(0)
    evaluation = stamps() if empty == "eval" else stamps(10)
    with pytest.raises(C1Violation):
        check_c1(train, evaluation)


def test_c1_rejects_missing_timestamps():
    nat = np.array(["NaT"], dtype="datetime64[s]")
    with pytest.raises(C1Violation):
        check_c1(nat, stamps(10))
    with pytest.raises(C1Violation):
        check_c1(stamps(0), nat)


@given(
    train=st.lists(st.integers(0, 50), min_size=1, max_size=8),
    evaluation=st.lists(st.integers(0, 50), min_size=1, max_size=8),
)
def test_c1_raises_exactly_when_the_newest_training_sample_is_not_older(train, evaluation):
    violates = max(train) >= min(evaluation)
    if violates:
        with pytest.raises(C1Violation):
            check_c1(np.array(train), np.array(evaluation))
    else:
        check_c1(np.array(train), np.array(evaluation))


# --- C2: the evaluation slot holds both classes from its own window -------------------------


def test_c2_passes_for_both_classes_inside_the_half_open_window():
    ts = stamps(0, 3600, 86400)
    check_c2(ts, np.array([1, 0, 1], dtype=np.int8), START, END)


def test_c2_accepts_a_sample_exactly_at_the_window_start():
    check_c2(stamps(0, 1), np.array([1, 0], dtype=np.int8), START, END)


def test_c2_rejects_a_sample_exactly_at_the_window_end():
    ts = np.array([at(5), END], dtype="datetime64[s]")  # the window is [start, end)
    with pytest.raises(C2Violation):
        check_c2(ts, np.array([1, 0], dtype=np.int8), START, END)


def test_c2_rejects_a_sample_from_an_earlier_window():
    ts = np.array([START - np.timedelta64(1, "s"), at(5)], dtype="datetime64[s]")
    with pytest.raises(C2Violation):
        check_c2(ts, np.array([1, 0], dtype=np.int8), START, END)


def test_c2_rejects_malware_from_another_window_even_if_benign_is_inside():
    ts = np.array([at(5), at(6), END + np.timedelta64(60, "s")], dtype="datetime64[s]")
    with pytest.raises(C2Violation):
        check_c2(ts, np.array([0, 0, 1], dtype=np.int8), START, END)


@pytest.mark.parametrize(("n_malware", "n_benign"), [(0, 4), (4, 0), (0, 0)])
def test_c2_needs_both_classes(n_malware, n_benign):
    y = labels(n_malware, n_benign)
    ts = stamps(*range(len(y)))
    with pytest.raises(C2Violation):
        check_c2(ts, y, START, END)


def test_c2_rejects_length_mismatch_and_an_empty_window():
    with pytest.raises(C2Violation):
        check_c2(stamps(0, 1), labels(1, 2), START, END)
    with pytest.raises(C2Violation):
        check_c2(stamps(0, 1), labels(1, 1), END, START)


@given(
    offsets=st.lists(st.integers(-5, 20), min_size=2, max_size=10),
    flags=st.lists(st.booleans(), min_size=2, max_size=10),
)
def test_c2_raises_exactly_when_a_row_is_outside_or_a_class_is_missing(offsets, flags):
    n = min(len(offsets), len(flags))
    offsets, flags = offsets[:n], flags[:n]
    width = 10
    ts = np.array([np.datetime64(0, "s") + np.timedelta64(o, "s") for o in offsets])
    y = np.array(flags, dtype=np.int8)
    start, end = np.datetime64(0, "s"), np.datetime64(width, "s")
    inside = all(0 <= o < width for o in offsets)
    both = bool(y.sum()) and bool((1 - y).sum())
    if inside and both:
        check_c2(ts, y, start, end)
    else:
        with pytest.raises(C2Violation):
            check_c2(ts, y, start, end)


# --- C3: malware-only seeded subsampling to the target ratio --------------------------------


@pytest.mark.parametrize(
    ("n_benign", "ratio", "expected"),
    [
        (900, 0.10, 100),
        (899, 0.10, 99),
        (9, 0.10, 1),
        (8, 0.10, 0),
        (1900, 0.05, 100),
        (60, 0.25, 20),
    ],
)
def test_target_malware_count_never_exceeds_the_ratio(n_benign, ratio, expected):
    assert target_malware_count(n_benign, ratio) == expected


def test_subsample_reaches_the_target_ratio_by_dropping_malware_only():
    y = labels(n_malware=300, n_benign=900)
    kept = subsample_malware(y, ratio=0.10, seed=7, slot_id="month:2020-03")
    after = y[kept]
    assert int((after == 0).sum()) == 900  # every benign sample survives
    assert int((after == 1).sum()) == 100  # 900 benign -> 100 malware = 10% of 1,000
    assert (after == 1).sum() / len(after) == pytest.approx(0.10)
    assert np.array_equal(kept, np.sort(kept)) and len(set(kept.tolist())) == len(kept)
    result = check_c3(y, kept, ratio=0.10)
    assert result.status == "at_target"
    assert result.n_malware_before == 300 and result.n_malware_after == 100
    assert result.share_malware_discarded == pytest.approx(200 / 300)


def test_subsample_keeps_everything_when_the_slot_is_already_below_target():
    y = labels(n_malware=50, n_benign=900)  # 5.3% malware: 10% cannot be reached
    kept = subsample_malware(y, ratio=0.10, seed=7, slot_id="month:2020-04")
    assert len(kept) == len(y)
    result = check_c3(y, kept, ratio=0.10)
    assert result.status == "below_target"
    assert result.share_malware_discarded == 0.0
    assert result.achieved_ratio == pytest.approx(50 / 950)
    assert result.achieved_ratio < 0.10


def test_subsample_is_deterministic_and_slot_scoped():
    y = labels(300, 900)
    a = subsample_malware(y, 0.10, seed=1, slot_id="2w:2019-09-09")
    b = subsample_malware(y, 0.10, seed=1, slot_id="2w:2019-09-09")
    assert np.array_equal(a, b)
    # Another slot's call in between does not change this slot's selection.
    subsample_malware(y, 0.10, seed=1, slot_id="2w:2019-09-23")
    assert np.array_equal(a, subsample_malware(y, 0.10, seed=1, slot_id="2w:2019-09-09"))
    assert not np.array_equal(a, subsample_malware(y, 0.10, seed=2, slot_id="2w:2019-09-09"))
    assert not np.array_equal(a, subsample_malware(y, 0.10, seed=1, slot_id="2w:2019-09-23"))


def test_lower_ratio_selection_is_nested_in_the_higher_ratio_selection():
    y = labels(600, 1800)
    ten = subsample_malware(y, 0.10, seed=3, slot_id="month:2021-06")
    five = subsample_malware(y, 0.05, seed=3, slot_id="month:2021-06")
    assert set(five.tolist()) <= set(ten.tolist())
    assert len(five) < len(ten)


def test_subsample_uses_labels_only_positions_of_malware_decide_the_draw():
    y = labels(300, 900)
    shuffled = np.random.default_rng(0).permutation(y)
    kept = subsample_malware(shuffled, 0.10, seed=5, slot_id="month:2020-03")
    assert (shuffled[kept] == 1).sum() == 100 and (shuffled[kept] == 0).sum() == 900
    assert set(np.flatnonzero(shuffled == 0).tolist()) <= set(kept.tolist())


def test_check_c3_raises_when_a_benign_sample_was_dropped():
    y = labels(300, 900)
    kept = subsample_malware(y, 0.10, seed=7, slot_id="s")
    benign = int(np.flatnonzero(y == 0)[0])
    with pytest.raises(C3Violation):
        check_c3(y, kept[kept != benign], ratio=0.10)


def test_check_c3_raises_when_the_ratio_ends_above_target():
    y = labels(300, 900)
    with pytest.raises(C3Violation):
        check_c3(y, np.arange(len(y)), ratio=0.10)  # nothing was subsampled: 25% malware


def test_check_c3_raises_when_a_reachable_slot_misses_the_target():
    y = labels(300, 900)
    kept = subsample_malware(y, 0.10, seed=7, slot_id="s")
    selected_malware = kept[y[kept] == 1]
    one_malware_short = kept[kept != selected_malware[0]]
    assert len(one_malware_short) == len(kept) - 1
    with pytest.raises(C3Violation):
        check_c3(y, one_malware_short, ratio=0.10)


def test_check_c3_raises_when_malware_is_dropped_from_a_slot_below_target():
    y = labels(50, 900)
    kept = np.arange(len(y))
    kept = kept[kept != 0]  # drops one malware although the slot is already below target
    with pytest.raises(C3Violation):
        check_c3(y, kept, ratio=0.10)


@pytest.mark.parametrize("bad", ["duplicate", "out_of_range", "negative"])
def test_check_c3_rejects_kept_indices_that_are_not_a_subset(bad):
    y = labels(300, 900)
    kept = subsample_malware(y, 0.10, seed=7, slot_id="s")
    broken = {
        "duplicate": np.append(kept, kept[0]),
        "out_of_range": np.append(kept[:-1], len(y) + 5),
        "negative": np.append(kept[:-1], -1),
    }[bad]
    with pytest.raises(C3Violation):
        check_c3(y, broken, ratio=0.10)


@pytest.mark.parametrize("ratio", [0.0, 1.0, -0.1, 1.5])
def test_ratio_must_lie_strictly_between_zero_and_one(ratio):
    y = labels(10, 90)
    with pytest.raises(C3Violation):
        subsample_malware(y, ratio, seed=1, slot_id="s")
    with pytest.raises(C3Violation):
        check_c3(y, np.arange(len(y)), ratio)


def test_a_slot_without_benign_samples_cannot_be_subsampled():
    with pytest.raises(C3Violation):
        subsample_malware(labels(10, 0), 0.10, seed=1, slot_id="s")


@given(
    n_malware=st.integers(0, 400),
    n_benign=st.integers(1, 400),
    ratio=st.sampled_from([0.05, 0.10, 0.20]),
    seed=st.integers(0, 10),
)
def test_subsample_always_satisfies_check_c3(n_malware, n_benign, ratio, seed):
    y = labels(n_malware, n_benign)
    kept = subsample_malware(y, ratio, seed=seed, slot_id="month:2018-11")
    result = check_c3(y, kept, ratio)
    assert result.n_benign_after == n_benign
    assert result.achieved_ratio <= ratio + 1e-12
    assert result.n_malware_after == min(n_malware, target_malware_count(n_benign, ratio))
