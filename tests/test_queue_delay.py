"""The label queue is the only place a delay exists (hard rule 3, .claude/rules/sim.md).

A label queried in evaluation slot t is usable from slot t + 1 + d (d = 0 means the next slot).
A label whose release slot falls at or after the window's last slot has no slot left to be used
in, so it is ignored and counted. Nothing is lost or duplicated in between.

These are code-behaviour checks on a seeded synthetic stream; none of it is evidence.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from simstream import N_EVAL, eval_slots, pick, sealed

from driftwatch.data.slicer import SlicerError
from driftwatch.sim.queue import LabelQueue


def run_stream(delay: int, schedule: list[list[int]]):
    """Drive the queue the way the runner does: release(s), then query(s). Returns releases."""
    slots = sealed()
    queue = LabelQueue(delay=delay, n_slots=N_EVAL)
    released = []
    for s, slot in enumerate(slots):
        released.append(queue.release(s))
        queue.query(s, slot, pick(slot, schedule[s]))
    return queue, released


# --- the delay rule -------------------------------------------------------------------------


@pytest.mark.parametrize("delay", [0, 1, 2, 3])
def test_a_label_is_usable_from_slot_t_plus_1_plus_d(delay: int) -> None:
    schedule = [[0, 1, 2, 3, 4]] + [[] for _ in range(N_EVAL - 1)]
    queue, released = run_stream(delay, schedule)
    arrival = [s for s, r in enumerate(released) if len(r.y) > 0]
    assert arrival == [1 + delay]
    assert queue.n_queued == 5 and queue.n_released == 5 and queue.n_ignored == 0


def test_d_zero_means_the_next_slot() -> None:
    schedule = [[0, 1], [2], [], [], [], []]
    _, released = run_stream(0, schedule)
    assert [len(r.y) for r in released] == [0, 2, 1, 0, 0, 0]


@pytest.mark.parametrize("delay", [0, 1, 2, 3])
def test_released_rows_are_the_queried_rows_with_their_true_labels(delay: int) -> None:
    slots = eval_slots()
    handles = [3, 0, 7]
    schedule = [handles] + [[] for _ in range(N_EVAL - 1)]
    _, released = run_stream(delay, schedule)
    got = released[1 + delay]
    pos = slots[0].resolve(slots[0].ref.slot_id, handles)
    assert np.array_equal(got.row_id, slots[0].row_id[pos])
    assert np.array_equal(got.y, slots[0].y[pos])
    assert np.array_equal(got.ts, slots[0].ts[pos])
    assert np.array_equal(got.queried_in, np.zeros(3, dtype=np.int64))
    assert got.X.shape[0] == 3


def test_labels_that_would_arrive_after_the_window_ends_are_ignored_and_counted() -> None:
    delay = 2
    # the last slot to arrive in is N_EVAL - 1 = 5, so slots 3, 4 and 5 queue into the void
    schedule = [[0], [0], [0], [0, 1], [0, 1, 2], [0, 1, 2, 3]]
    queue, released = run_stream(delay, schedule)
    assert queue.n_queued == 1 + 1 + 1 + 2 + 3 + 4
    assert queue.n_released == 3
    assert queue.n_ignored == 2 + 3 + 4
    assert sum(len(r.y) for r in released) == 3


def test_a_query_in_the_last_slot_is_always_ignored() -> None:
    for delay in (0, 1, 2, 3):
        schedule = [[] for _ in range(N_EVAL - 1)] + [[0, 1, 2]]
        queue, released = run_stream(delay, schedule)
        assert queue.n_ignored == 3 and queue.n_released == 0
        assert all(len(r.y) == 0 for r in released)


# --- nothing lost, nothing duplicated (property based) -------------------------------------------


@settings(max_examples=150, deadline=None)
@given(
    delay=st.integers(0, 3),
    data=st.data(),
)
def test_conservation_and_exact_release_slot(delay: int, data) -> None:
    slots = eval_slots()
    schedule = []
    for slot in slots:
        n = len(slot.perm)
        picks = data.draw(st.lists(st.integers(0, n - 1), unique=True, max_size=12))
        schedule.append(picks)
    queue, released = run_stream(delay, schedule)

    queued = sum(len(p) for p in schedule)
    assert queue.n_queued == queued
    assert queue.n_released + queue.n_ignored == queued  # nothing lost

    seen: set[int] = set()
    for s, rel in enumerate(released):
        for rid, t in zip(rel.row_id.tolist(), rel.queried_in.tolist(), strict=True):
            assert t + 1 + delay == s  # never earlier, never later
            assert rid not in seen  # never twice
            seen.add(rid)
    expected = {
        int(slots[t].row_id[slots[t].resolve(slots[t].ref.slot_id, schedule[t])][i])
        for t in range(N_EVAL)
        if t + 1 + delay < N_EVAL
        for i in range(len(schedule[t]))
    }
    assert seen == expected  # nothing duplicated or invented


# --- contract errors -------------------------------------------------------------------------


def test_negative_or_non_integer_delay_is_rejected() -> None:
    for bad in (-1, 1.5, "2", None):
        with pytest.raises(ValueError):
            LabelQueue(delay=bad, n_slots=N_EVAL)  # type: ignore[arg-type]


def test_duplicate_handles_in_one_query_are_rejected() -> None:
    slot = sealed()[0]
    queue = LabelQueue(delay=0, n_slots=N_EVAL)
    queue.release(0)
    with pytest.raises(ValueError, match="duplicate"):
        queue.query(0, slot, pick(slot, [1, 1]))


def test_a_slot_can_be_queried_only_once() -> None:
    slot = sealed()[0]
    queue = LabelQueue(delay=0, n_slots=N_EVAL)
    queue.release(0)
    queue.query(0, slot, pick(slot, [1]))
    with pytest.raises(ValueError, match="already"):
        queue.query(0, slot, pick(slot, [2]))


def test_releases_must_be_consecutive_from_slot_zero() -> None:
    queue = LabelQueue(delay=0, n_slots=N_EVAL)
    with pytest.raises(ValueError, match="order"):
        queue.release(1)
    queue.release(0)
    with pytest.raises(ValueError, match="order"):
        queue.release(0)


def test_handles_from_another_slot_are_refused() -> None:
    slots = sealed()
    queue = LabelQueue(delay=0, n_slots=N_EVAL)
    queue.release(0)
    foreign = pick(slots[1], [0])  # selection made against slot 1's public view
    with pytest.raises(SlicerError):
        queue.query(0, slots[0], foreign)


def test_out_of_range_handles_are_refused() -> None:
    slot = sealed()[0]
    queue = LabelQueue(delay=0, n_slots=N_EVAL)
    queue.release(0)
    with pytest.raises(SlicerError):
        queue.query(0, slot, pick(slot, [len(slot.public().handle)]))


def test_a_query_after_the_window_is_refused() -> None:
    slot = sealed()[0]
    queue = LabelQueue(delay=0, n_slots=N_EVAL)
    queue.release(0)
    with pytest.raises(ValueError, match="slot index"):
        queue.query(N_EVAL, slot, pick(slot, [0]))


def test_pool_timestamps_are_checked_against_the_slot_scored() -> None:
    """C1 stays an assertion: a pool row at or after the slot's first timestamp raises."""
    from driftwatch.data.constraints import C1Violation

    slot = sealed()[2]
    first = eval_slots()[2].ts.min()
    slot.assert_c1(np.array([first - np.timedelta64(1, "ns")], dtype="datetime64[ns]"))
    with pytest.raises(C1Violation):
        slot.assert_c1(np.array([first], dtype="datetime64[ns]"))


def test_the_public_view_is_the_slicers_opaque_slot() -> None:
    from driftwatch.data.slicer import OpaqueSlot

    slot = sealed()[0]
    pub = slot.public()
    assert isinstance(pub, OpaqueSlot)
    assert not hasattr(pub, "y") and not hasattr(pub, "row_id")
