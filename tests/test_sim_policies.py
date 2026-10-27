"""Retraining policies: never, periodic every 3 slots, monitor-triggered and matched-count."""

from __future__ import annotations

import pytest

from driftwatch.sim.policies import (
    MonitorTriggered,
    Never,
    Periodic,
    Scheduled,
    even_schedule,
    make_policy,
)


def fires(policy, n_slots: int) -> list[int]:
    return [s for s in range(n_slots) if policy.should_retrain(s)]


def test_never_never_retrains() -> None:
    assert fires(Never(), 12) == []


def test_periodic_retrains_before_slots_3_6_9_counted_from_the_first_evaluation_slot() -> None:
    assert fires(Periodic(period=3), 12) == [3, 6, 9]
    assert fires(Periodic(period=3), 6) == [3]  # BODMAS nE = 6: one event
    assert fires(Periodic(period=2), 7) == [2, 4, 6]


def test_slot_zero_is_never_a_retrain_slot() -> None:
    assert not Periodic(period=1).should_retrain(0)


def test_period_must_be_a_positive_integer() -> None:
    for bad in (0, -3, 1.5, True):
        with pytest.raises(ValueError):
            Periodic(period=bad)  # type: ignore[arg-type]


def drive_monitor(policy: MonitorTriggered, alarms: list[bool], refit_ok: list[bool]) -> list:
    """Runner order per slot: event check, record (refit or no-op), then the slot's alarm."""
    events = []
    for s, alarm in enumerate(alarms):
        event = policy.should_retrain(s)
        refit = event and refit_ok[s]
        if event:
            events.append((s, "refit" if refit else "noop"))
        policy.record(s, refit)
        policy.notify(alarm)
    return events


def test_monitor_alarm_triggers_a_retrain_before_the_next_slot() -> None:
    alarms = [False, False, True, False, False, False]
    assert drive_monitor(MonitorTriggered("ks", 2), alarms, [True] * 6) == [(3, "refit")]


def test_monitor_respects_the_minimum_gap_from_the_last_refit() -> None:
    # alarms every slot; gap 2 from the initial fit at 0: refits at 2, 4, 6
    events = drive_monitor(MonitorTriggered("ks", 2), [True] * 8, [True] * 8)
    assert events == [(2, "refit"), (4, "refit"), (6, "refit")]
    events = drive_monitor(MonitorTriggered("ks", 1), [True] * 4, [True] * 4)
    assert events == [(1, "refit"), (2, "refit"), (3, "refit")]


def test_an_alarm_without_new_labels_is_a_logged_noop_and_is_not_carried() -> None:
    alarms = [False, True, False, False, False]
    labels = [False, False, False, True, True]  # nothing has arrived before slot 3
    assert drive_monitor(MonitorTriggered("ks", 1), alarms, labels) == [(2, "noop")]


def test_a_noop_does_not_restart_the_gap() -> None:
    alarms = [False, True, True, False]
    labels = [False, False, False, True]
    assert drive_monitor(MonitorTriggered("ks", 2), alarms, labels) == [
        (2, "noop"),
        (3, "refit"),
    ]


def test_min_gap_must_be_a_positive_integer() -> None:
    for bad in (0, -1, 1.5, True):
        with pytest.raises(ValueError):
            MonitorTriggered("ks", bad)  # type: ignore[arg-type]


def test_scheduled_fires_on_its_slots_only() -> None:
    assert fires(Scheduled([2, 5]), 8) == [2, 5]


def test_even_schedule_spreads_k_events_and_caps_at_the_available_slots() -> None:
    assert even_schedule(0, 1, 11) == ()
    assert even_schedule(1, 1, 11) == (6,)
    assert even_schedule(3, 1, 11) == (3, 6, 9)
    assert even_schedule(3, 4, 11) == (6, 8, 10)
    assert even_schedule(20, 4, 5) == (4, 5)
    assert even_schedule(2, 6, 5) == ()
    for k in range(12):
        s = even_schedule(k, 1, 11)
        assert len(s) == min(k, 11) and len(set(s)) == len(s) and s == tuple(sorted(s))


def test_make_policy() -> None:
    assert make_policy("never").name == "never"
    p = make_policy("periodic", period=3)
    assert isinstance(p, Periodic) and p.period == 3
    m = make_policy("monitor", trigger="mmd", min_gap=2)
    assert isinstance(m, MonitorTriggered) and m.trigger == "mmd" and m.min_gap == 2
    with pytest.raises(ValueError, match="trigger"):
        make_policy("monitor")
    with pytest.raises(ValueError):
        make_policy("sometimes")


def test_policies_take_a_slot_index_and_nothing_label_shaped() -> None:
    import inspect

    assert list(inspect.signature(MonitorTriggered.notify).parameters) == ["self", "alarm"]
    for cls in (Never, Periodic, MonitorTriggered, Scheduled):
        params = list(inspect.signature(cls.should_retrain).parameters)
        assert params == ["self", "slot_index"]
