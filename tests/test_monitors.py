"""Drift monitors: change-point detection, false-alarm rate, determinism, no labels.

Synthetic streams only (never evidence). Each monitor is driven the way the runner drives it:
start on the initial window, reference = the window's time-ordered hold-out, calibration rows
= the hold-out (features only), then one ``update`` per slot after the slot is scored.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from driftwatch.data.synthetic import change_point_stream
from driftwatch.monitors import MONITORS, SlotView, make_monitor
from driftwatch.monitors.base import ALPHA, INITIAL_REF, MonitorState, reference_sample
from driftwatch.monitors.domain_clf import DomainClassifier
from driftwatch.monitors.ks import top_features
from driftwatch.monitors.mmd import mmd_permutation
from driftwatch.monitors.p_uniformity import label_free_scores

N_TRAIN_SLOTS = 3


def drive(name: str, stream, *, seed: int = 0, monitor=None):
    """Alarms of one monitor over the evaluation slots of ``stream`` (fixed reference)."""
    mon = monitor or make_monitor(name)
    train = stream[:N_TRAIN_SLOTS]
    X = np.vstack([x for x, _ in train])
    y = np.concatenate([t for _, t in train])
    cut = int(0.8 * len(y))  # time-ordered hold-out: the newest 20% of the window
    proper_X, proper_y, hold_X = X[:cut], y[:cut], X[cut:]
    model = LogisticRegression(max_iter=1000).fit(proper_X, proper_y)
    state = MonitorState(seed=seed, window_key="w0")
    state.reset_reference(reference_sample(hold_X, seed, "w0", INITIAL_REF), INITIAL_REF)
    mon.start(state, proper_X, proper_y, hold_X)
    cal_proba = model.predict_proba(hold_X)[:, 1]
    alarms = []
    for s, (Xs, _ys) in enumerate(stream[N_TRAIN_SLOTS:]):
        view = SlotView(
            slot_index=s,
            slot_id=f"slot{s}",
            X=Xs,
            proba=model.predict_proba(Xs)[:, 1],
            ref_proba=model.predict_proba(state.ref_X)[:, 1],
            cal_X=hold_X,
            cal_proba=cal_proba,
        )
        alarms.append(mon.update(view, state))
    return alarms, state


@pytest.mark.parametrize("name", MONITORS)
def test_each_monitor_detects_a_known_shift_at_the_change_point(name: str) -> None:
    change = 4  # evaluation slot index of the shift
    stream = change_point_stream(n_slots=N_TRAIN_SLOTS + 8, change_at=N_TRAIN_SLOTS + change,
                                 rows_per_slot=700, shift=1.0, seed=11)  # fmt: skip
    alarms, _ = drive(name, stream)
    fired = [a.slot_index for a in alarms if a.fired]
    assert all(a.decided for a in alarms)
    assert fired, f"{name} never alarmed"
    first_after = min(s for s in fired if s >= change) if any(s >= change for s in fired) else None
    assert first_after is not None and first_after - change <= 1, (name, fired)
    # after the change every slot differs from the reference: the monitor keeps alarming
    assert all(a.fired for a in alarms if a.slot_index >= change + 1), (name, fired)


@pytest.mark.parametrize("name", MONITORS)
def test_no_drift_stream_rarely_alarms(name: str) -> None:
    stream = change_point_stream(n_slots=N_TRAIN_SLOTS + 30, change_at=None,
                                 rows_per_slot=700, seed=5)  # fmt: skip
    alarms, _ = drive(name, stream)
    assert sum(a.fired for a in alarms) <= 2, name  # 30 slots at alpha 0.01: 0.3 expected


@pytest.mark.slow
@pytest.mark.parametrize("name", MONITORS)
def test_false_alarm_rate_is_near_nominal_on_a_long_no_drift_stream(name: str) -> None:
    n = 200
    stream = change_point_stream(n_slots=N_TRAIN_SLOTS + n, change_at=None,
                                 rows_per_slot=700, seed=7)  # fmt: skip
    alarms, _ = drive(name, stream)
    k = sum(a.fired for a in alarms)
    # Binomial(200, 0.01): P(K >= 7) is about 5e-4; a conservative test may sit below alpha
    assert k <= 6, (name, k, k / n, ALPHA)


@pytest.mark.parametrize("name", MONITORS)
def test_monitors_are_deterministic_given_seed_and_window(name: str) -> None:
    stream = change_point_stream(n_slots=N_TRAIN_SLOTS + 4, change_at=N_TRAIN_SLOTS + 2,
                                 rows_per_slot=400, seed=2)  # fmt: skip
    a, _ = drive(name, stream, seed=3)
    b, _ = drive(name, stream, seed=3)
    assert [(x.statistic, x.p_value) for x in a] == [(x.statistic, x.p_value) for x in b]


def test_cached_feature_statistics_are_reused_not_recomputed() -> None:
    stream = change_point_stream(n_slots=N_TRAIN_SLOTS + 3, change_at=None, rows_per_slot=400)
    _, state = drive("ks", stream)
    assert len([k for k in state.cache if k.startswith("ks|")]) == 3
    mon = make_monitor("ks")
    view = SlotView(slot_index=0, slot_id="slot0", X=np.zeros((5, 24)))  # wrong data, cached
    again = mon.update(view, state)
    assert again.p_value == state.cache[next(k for k in state.cache if "slot0" in k)][1]


def test_slot_view_has_no_label_field() -> None:
    names = {f.name for f in dataclasses.fields(SlotView)}
    assert not names & {"y", "y_true", "label", "labels", "cal_y"}
    assert names == {"slot_index", "slot_id", "X", "proba", "ref_proba", "cal_X", "cal_proba"}


def test_undecided_when_calibration_is_too_small() -> None:
    stream = change_point_stream(n_slots=N_TRAIN_SLOTS + 1, change_at=None, rows_per_slot=300)
    mon = make_monitor("p_uniformity")
    state = MonitorState(seed=0, window_key="w")
    view = SlotView(0, "s0", stream[-1][0], proba=np.full(300, 0.9),
                    cal_X=stream[0][0][:5], cal_proba=np.full(5, 0.9))  # fmt: skip
    alarm = mon.update(view, state)
    assert not alarm.decided and not alarm.fired and state.n_undecided == 1


def test_top_features_pick_the_discriminative_block() -> None:
    X, y = change_point_stream(n_slots=1, change_at=None, rows_per_slot=2000, seed=1)[0]
    assert set(top_features(X, y, 5)) <= set(range(12))


def test_mmd_permutation_p_value_is_large_for_one_distribution_and_small_for_two() -> None:
    rng = np.random.default_rng(0)
    a, b = rng.normal(size=(100, 3)), rng.normal(size=(100, 3))
    _, p_same = mmd_permutation(a, b, 199, np.random.default_rng(1))
    _, p_diff = mmd_permutation(a, b + 1.0, 199, np.random.default_rng(1))
    assert p_same > 0.05 and p_diff == pytest.approx(1 / 200)


def test_label_free_scores_need_no_label() -> None:
    s, pred = label_free_scores(np.array([0.9, 0.1, 0.5, 0.6]))
    assert np.allclose(s, [0.1, 0.1, 0.5, 0.4]) and pred.tolist() == [1, 0, 0, 1]


def test_domain_classifier_null_is_shared_across_seeds_and_cached() -> None:
    hold = np.random.default_rng(0).normal(size=(400, 6))
    dc = DomainClassifier(n_null=5)
    s0, s1 = MonitorState(seed=0, window_key="w"), MonitorState(seed=1, window_key="w")
    dc.start(s0, hold, np.r_[np.zeros(200), np.ones(200)], hold)
    dc.start(s1, hold, np.r_[np.zeros(200), np.ones(200)], hold)
    assert np.array_equal(s0.fitted["null"], s1.fitted["null"])
    assert dc.null_key(s0) in s0.cache


def test_unknown_monitor_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown monitor"):
        make_monitor("adwin")
