"""The training pool: initial window plus arrived labels, weight 1, never truncated (ADR-0007)."""

from __future__ import annotations

import numpy as np
import pytest
import scipy.sparse as sp
from simstream import N_EVAL, pick, sealed, train_window

from driftwatch.data.constraints import C1Violation
from driftwatch.sim.pool import TrainingPool
from driftwatch.sim.queue import LabelQueue


def released_after(delay: int, queries: dict[int, list[int]]):
    queue = LabelQueue(delay=delay, n_slots=N_EVAL)
    slots = sealed()
    out = []
    for s, slot in enumerate(slots):
        out.append(queue.release(s))
        queue.query(s, slot, pick(slot, queries.get(s, [])))
    return out


def test_the_pool_starts_as_the_initial_window() -> None:
    tw = train_window()
    pool = TrainingPool(tw)
    assert pool.n_initial == len(tw.y) and pool.n_arrived == 0 and pool.n == len(tw.y)
    assert np.array_equal(pool.y, tw.y)
    assert pool.X.shape[0] == pool.n


def test_arrived_labels_are_appended_with_weight_one_and_nothing_is_dropped() -> None:
    pool = TrainingPool(train_window())
    rel = released_after(0, {0: [0, 1, 2], 1: [4], 2: [5, 6]})
    for r in rel:
        pool.add(r)
    assert pool.n_arrived == 6
    assert pool.n == pool.n_initial + 6
    assert pool.y[-6:].tolist() == np.concatenate([r.y for r in rel if len(r)]).tolist()
    assert pool.n_new_since_fit == 6
    pool.mark_fitted()
    assert pool.n_new_since_fit == 0 and pool.n_arrived == 6  # fitted marks, never prunes


def test_pool_matrix_has_the_features_in_the_same_order_as_labels() -> None:
    pool = TrainingPool(train_window())
    rel = released_after(0, {0: [3, 1]})
    for r in rel:
        pool.add(r)
    slot0 = sealed()[0]
    first = rel[1]
    assert np.array_equal(
        np.asarray(pool.X[pool.n_initial :]).reshape(len(first), -1),
        np.asarray(first.X).reshape(len(first), -1),
    )
    assert slot0.n > 0


def test_pool_c1_holds_against_every_later_slot_and_raises_if_violated() -> None:
    pool = TrainingPool(train_window())
    for r in released_after(0, {0: [0, 1], 1: [2]}):
        pool.add(r)
    slots = sealed()
    pool.assert_c1(slots[2])  # slot 2 is later than every pooled row
    with pytest.raises(C1Violation):
        pool.assert_c1(slots[0])  # a label queried in slot 0 is not older than slot 0


def test_sparse_features_stay_sparse() -> None:
    tw = train_window()
    pool = TrainingPool(tw)
    assert sp.issparse(pool.X) == sp.issparse(tw.X)


def test_empty_releases_are_a_no_op() -> None:
    pool = TrainingPool(train_window())
    rel = released_after(1, {})
    for r in rel:
        pool.add(r)
    assert pool.n_arrived == 0 and pool.n_new_since_fit == 0


def test_provenance_lists_where_each_arrived_row_was_queried() -> None:
    pool = TrainingPool(train_window())
    for r in released_after(0, {0: [0], 2: [1, 2]}):
        pool.add(r)
    assert pool.arrived_queried_in.tolist() == [0, 2, 2]
    assert len(pool.arrived_row_id) == 3
