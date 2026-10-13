"""Selectors: budget arithmetic, random selection, and the plug-in interface for Phase 8."""

from __future__ import annotations

import numpy as np
import pytest
from simstream import sealed

from driftwatch.sim.selectors import (
    RandomSelector,
    Selection,
    budget_count,
    calibration_count,
    make_selector,
    selector_rng,
)


@pytest.mark.parametrize(
    ("n_slot", "pct", "expected"),
    [
        (400, 0.5, 2),
        (400, 1, 4),
        (400, 2, 8),
        (400, 5, 20),
        (30, 0.5, 0),
        (50, 1, 1),
        (250, 0.5, 1),
    ],
)
def test_budget_is_a_percentage_of_the_evaluated_slot_rounded_half_up(n_slot, pct, expected):
    assert budget_count(n_slot, pct) == expected


def test_budget_never_exceeds_the_slot_and_rejects_bad_input() -> None:
    assert budget_count(10, 100) == 10
    for bad in (-1, 101, float("nan")):
        with pytest.raises(ValueError):
            budget_count(10, bad)
    with pytest.raises(ValueError):
        budget_count(-1, 1)


def test_calibration_slice_is_a_share_of_the_budget() -> None:
    assert calibration_count(20, 0.20) == 4
    assert calibration_count(20, 0.0) == 0
    assert calibration_count(0, 0.2) == 0
    assert calibration_count(3, 0.5) == 2  # half up
    with pytest.raises(ValueError):
        calibration_count(10, 1.5)


def test_random_selection_is_distinct_in_range_and_tagged_with_the_slot() -> None:
    pub = sealed()[0].public()
    sel = RandomSelector().select(pub, 12, selector_rng(0, pub.slot_id))
    assert isinstance(sel, Selection) and sel.slot_id == pub.slot_id
    assert len(sel.handles) == 12 and len(set(sel.handles.tolist())) == 12
    assert sel.handles.min() >= 0 and sel.handles.max() < len(pub.handle)


def test_selection_is_deterministic_given_seed_and_slot_and_differs_across_seeds() -> None:
    pub = sealed()[1].public()
    a = RandomSelector().select(pub, 10, selector_rng(5, pub.slot_id)).handles
    b = RandomSelector().select(pub, 10, selector_rng(5, pub.slot_id)).handles
    c = RandomSelector().select(pub, 10, selector_rng(6, pub.slot_id)).handles
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_a_smaller_budget_selects_a_subset_of_a_larger_one() -> None:
    """Paired comparisons across budgets: 0.5% rows are inside the 5% rows."""
    pub = sealed()[2].public()
    small = RandomSelector().select(pub, 2, selector_rng(1, pub.slot_id)).handles
    large = RandomSelector().select(pub, 20, selector_rng(1, pub.slot_id)).handles
    assert set(small.tolist()) <= set(large.tolist())


def test_budget_larger_than_the_slot_is_clipped_not_an_error() -> None:
    pub = sealed()[0].public()
    sel = RandomSelector().select(pub, 10**6, selector_rng(0, pub.slot_id))
    assert len(sel.handles) == len(pub.handle)


def test_zero_budget_selects_nothing() -> None:
    pub = sealed()[0].public()
    assert len(RandomSelector().select(pub, 0, selector_rng(0, pub.slot_id)).handles) == 0


def test_the_interface_accepts_a_score_driven_selector() -> None:
    """Phase 8 plugs in uncertainty and credibility selectors through the same call."""

    class LowestScore:
        name = "lowest-score"

        def select(self, public, n, rng, scores=None):
            order = np.argsort(scores, kind="stable")[:n]
            return Selection(public.slot_id, public.handle[order])

    pub = sealed()[0].public()
    scores = np.linspace(1, 0, len(pub.handle))
    sel = LowestScore().select(pub, 3, np.random.default_rng(0), scores=scores)
    assert sel.handles.tolist() == [len(pub.handle) - 1, len(pub.handle) - 2, len(pub.handle) - 3]


def test_make_selector_knows_random_only_for_now() -> None:
    assert make_selector("random").name == "random"
    with pytest.raises(ValueError, match="uncertainty"):
        make_selector("uncertainty")
