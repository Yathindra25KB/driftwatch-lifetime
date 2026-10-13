"""Retraining policies: never, periodic every 3 slots, and the Phase 9 monitor stub."""

from __future__ import annotations

import pytest

from driftwatch.sim.policies import MonitorTriggered, Never, Periodic, make_policy


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


def test_monitor_triggered_is_an_interface_that_raises_until_phase_9() -> None:
    with pytest.raises(NotImplementedError, match="Phase 9"):
        MonitorTriggered().should_retrain(3)


def test_make_policy() -> None:
    assert make_policy("never").name == "never"
    p = make_policy("periodic", period=3)
    assert isinstance(p, Periodic) and p.period == 3
    assert make_policy("monitor").name == "monitor"
    with pytest.raises(ValueError):
        make_policy("sometimes")


def test_policies_take_a_slot_index_and_nothing_label_shaped() -> None:
    import inspect

    for cls in (Never, Periodic, MonitorTriggered):
        params = list(inspect.signature(cls.should_retrain).parameters)
        assert params == ["self", "slot_index"]
