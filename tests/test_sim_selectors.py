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


def test_make_selector_knows_the_three_arms_and_refuses_others() -> None:
    # Phase 8 adds the score-driven selectors behind the same interface
    assert [make_selector(n).name for n in ("random", "uncertainty", "credibility")] == [
        "random",
        "uncertainty",
        "credibility",
    ]
    with pytest.raises(ValueError, match="unknown selector"):
        make_selector("oracle")


# --- Phase 8: score-driven selectors and the reserved random slice ----------------------------


def test_uncertainty_picks_the_probabilities_closest_to_one_half() -> None:
    pub = sealed()[0].public()
    n = len(pub.handle)
    proba = np.linspace(0.0, 1.0, n)  # row i has P = i / (n - 1)
    sel = make_selector("uncertainty").select(pub, 4, np.random.default_rng(0), scores=proba)
    expect = np.argsort(np.abs(proba - 0.5), kind="stable")[:4]
    assert sorted(sel.handles.tolist()) == sorted(expect.tolist())


def test_credibility_picks_the_lowest_p_values_and_ties_follow_the_seed() -> None:
    pub = sealed()[0].public()
    n = len(pub.handle)
    cred = np.full(n, 0.5)
    cred[[3, 7, 11]] = 0.01
    first = make_selector("credibility").select(pub, 5, np.random.default_rng(1), scores=cred)
    assert {3, 7, 11} <= set(first.handles.tolist()) and len(first.handles) == 5
    again = make_selector("credibility").select(pub, 5, np.random.default_rng(1), scores=cred)
    assert first.handles.tolist() == again.handles.tolist()  # same seed, same tie order
    assert set(first.handles.tolist()[:3]) == {3, 7, 11}  # the lowest values come first


def test_score_selectors_need_scores_and_finite_values() -> None:
    pub = sealed()[0].public()
    with pytest.raises(ValueError, match="needs"):
        make_selector("credibility").select(pub, 3, np.random.default_rng(0))
    bad = np.full(len(pub.handle), np.nan)
    with pytest.raises(ValueError, match="finite"):
        make_selector("uncertainty").select(pub, 3, np.random.default_rng(0), scores=bad)


def test_exclusion_is_respected_by_every_selector() -> None:
    from driftwatch.sim.selectors import select_with_reserved_slice  # noqa: F401

    pub = sealed()[0].public()
    n = len(pub.handle)
    exclude = np.zeros(n, dtype=bool)
    exclude[: n // 2] = True
    scores = np.linspace(0, 1, n)
    for name in ("random", "uncertainty", "credibility"):
        sel = make_selector(name).select(
            pub, n, np.random.default_rng(0), scores=scores, exclude=exclude
        )
        assert len(sel.handles) == n - n // 2 and (sel.handles >= n // 2).all()


@pytest.mark.parametrize("name", ["random", "uncertainty", "credibility"])
def test_every_arm_spends_the_same_budget_and_tags_the_reserved_slice(name: str) -> None:
    from driftwatch.sim.selectors import (
        ORIGIN_RANDOM,
        ORIGIN_SELECTED,
        select_with_reserved_slice,
        selector_rng,
    )

    pub = sealed()[0].public()
    n = len(pub.handle)
    scores = np.random.default_rng(5).uniform(size=n)
    sel = select_with_reserved_slice(
        make_selector(name), pub, 20, 4, seed=3, rng=selector_rng(3, pub.slot_id), scores=scores
    )
    assert len(sel.handles) == 20 and len(set(sel.handles.tolist())) == 20  # equal labels spent
    assert (sel.origin == ORIGIN_RANDOM).sum() == 4 and (sel.origin == ORIGIN_SELECTED).sum() == 16
    reserved = sel.handles[sel.origin == ORIGIN_RANDOM]
    # the reserved slice is the same draw whatever the selector or the scores
    other = select_with_reserved_slice(
        make_selector("random"), pub, 20, 4, seed=3, rng=selector_rng(3, pub.slot_id)
    )
    assert reserved.tolist() == other.handles[other.origin == ORIGIN_RANDOM].tolist()


def test_the_reserved_slice_does_not_depend_on_the_scores() -> None:
    from driftwatch.sim.selectors import ORIGIN_RANDOM, select_with_reserved_slice, selector_rng

    pub = sealed()[0].public()
    n = len(pub.handle)
    a = np.random.default_rng(1).uniform(size=n)
    b = 1.0 - a
    kw = dict(seed=0, rng=selector_rng(0, pub.slot_id))
    sa = select_with_reserved_slice(make_selector("credibility"), pub, 12, 3, scores=a, **kw)
    sb = select_with_reserved_slice(make_selector("credibility"), pub, 12, 3, scores=b, **kw)
    assert (
        sa.handles[sa.origin == ORIGIN_RANDOM].tolist()
        == sb.handles[sb.origin == ORIGIN_RANDOM].tolist()
    )
    assert set(sa.handles.tolist()) != set(sb.handles.tolist())  # the selected part follows scores


def test_zero_reserved_share_and_oversized_budget() -> None:
    from driftwatch.sim.selectors import ORIGIN_SELECTED, select_with_reserved_slice, selector_rng

    pub = sealed()[0].public()
    n = len(pub.handle)
    s0 = select_with_reserved_slice(
        make_selector("random"), pub, 9, 0, seed=0, rng=selector_rng(0, pub.slot_id)
    )
    assert (s0.origin == ORIGIN_SELECTED).all() and len(s0.handles) == 9
    big = select_with_reserved_slice(
        make_selector("random"), pub, n + 50, 5, seed=0, rng=selector_rng(0, pub.slot_id)
    )
    assert len(big.handles) == n
