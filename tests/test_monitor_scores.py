"""Monitor scoring against drop events: hand-computed cases."""

from __future__ import annotations

import math

import pytest

from driftwatch.metrics.monitor_scores import AlarmCounts, score_alarms

# trailing mean of slots 0-2 is 0.8; slot 3 at 0.7 is a drop (0.10 below), recovered at slot 4
F1 = [0.8, 0.8, 0.8, 0.7, 0.8, 0.8, 0.8, 0.8]


def alarms_at(*slots: int, n: int = len(F1)) -> list[bool]:
    return [s in slots for s in range(n)]


def test_an_alarm_on_the_drop_slot_is_a_true_alarm_with_delay_zero() -> None:
    c = score_alarms(F1, alarms_at(3))
    assert (c.n_drops, c.n_alarms, c.n_true_alarms, c.n_detected, c.delay_sum) == (1, 1, 1, 1, 0)
    assert c.precision == 1.0 and c.recall == 1.0 and c.mean_delay == 0.0


def test_an_alarm_within_the_horizon_detects_late_and_one_beyond_it_is_false() -> None:
    c = score_alarms(F1, alarms_at(5))
    assert c.n_detected == 1 and c.mean_delay == 2.0
    c = score_alarms(F1, alarms_at(6))
    assert c.n_detected == 0 and c.n_true_alarms == 0 and c.precision == 0.0 and c.recall == 0.0


def test_alarms_before_the_drop_or_before_slot_three_do_not_count_as_detection() -> None:
    c = score_alarms(F1, alarms_at(1, 2))
    assert c.n_alarms == 0 and c.n_detected == 0 and math.isnan(c.precision)
    assert c.n_slots == len(F1) - 3


def test_several_alarms_on_one_drop_are_all_true_and_detect_it_once() -> None:
    c = score_alarms(F1, alarms_at(3, 4, 5))
    assert c.n_true_alarms == 3 and c.n_detected == 1 and c.delay_sum == 0
    assert c.alarm_rate == pytest.approx(3 / 5)


def test_no_drop_gives_undefined_recall_and_every_alarm_false() -> None:
    flat = [0.8] * 8
    c = score_alarms(flat, alarms_at(4, 6))
    assert c.n_drops == 0 and math.isnan(c.recall) and c.precision == 0.0


def test_counts_add_up_across_series() -> None:
    a = score_alarms(F1, alarms_at(3))
    b = score_alarms(F1, alarms_at(6))
    s = a + b
    assert isinstance(s, AlarmCounts) and s.n_drops == 2 and s.n_alarms == 2
    assert s.precision == 0.5 and s.recall == 0.5


def test_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError, match="one alarm decision per slot"):
        score_alarms(F1, [True])
