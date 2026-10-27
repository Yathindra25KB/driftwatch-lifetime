"""Conformal layer: hand-worked p-values, uniformity, scores, buffer and contamination.

Synthetic arrays only (code-behaviour checks, never evidence).
"""

from __future__ import annotations

import numpy as np
import pytest
import scipy.sparse as sp
from scipy import stats as scipy_stats

from driftwatch.conformal import mondrian
from driftwatch.conformal.mondrian import ClassCalibration, credibility, pvalues
from driftwatch.conformal.nonconformity import (
    CentroidScore,
    ProbabilityScore,
    WindowMismatch,
)
from driftwatch.conformal.recalibrate import (
    CalibrationBuffer,
    CalibrationContamination,
    RecalibrationRule,
    time_ordered_holdout,
)

# --- hand-worked p-values --------------------------------------------------------------------


def hand_calibration() -> ClassCalibration:
    # class 0: own scores 0.2, 0.3          (n_0 = 2)
    # class 1: own scores 0.1, 0.4, 0.4, 0.9 (n_1 = 4)
    s = np.array([0.2, 0.3, 0.1, 0.4, 0.4, 0.9])
    y = np.array([0, 0, 1, 1, 1, 1])
    return ClassCalibration.from_scores(s, y)


def test_p_c_matches_the_formula_by_hand() -> None:
    cal = hand_calibration()
    assert cal.counts() == (2, 4)
    # test sample: s_0 = 0.25, s_1 = 0.4
    p = pvalues(cal, np.array([[0.25, 0.4]]))
    # class 0: calibration scores >= 0.25 are {0.3} -> (1 + 1) / (2 + 1)
    assert p[0, 0] == pytest.approx(2 / 3)
    # class 1: scores >= 0.4 are {0.4, 0.4, 0.9} (ties count) -> (1 + 3) / (4 + 1)
    assert p[0, 1] == pytest.approx(0.8)


@pytest.mark.parametrize(
    ("s1", "expected"),
    [(0.0, 5 / 5), (0.1, 5 / 5), (0.11, 4 / 5), (0.9, 2 / 5), (0.95, 1 / 5)],
)
def test_p_values_step_down_with_the_score(s1: float, expected: float) -> None:
    p = pvalues(hand_calibration(), np.array([[0.0, s1]]))
    assert p[0, 1] == pytest.approx(expected)


def test_the_smallest_possible_p_value_is_one_over_n_plus_one() -> None:
    p = pvalues(hand_calibration(), np.array([[99.0, 99.0]]))
    assert p[0, 0] == pytest.approx(1 / 3) and p[0, 1] == pytest.approx(1 / 5)


def test_a_class_without_calibration_samples_gets_p_one() -> None:
    cal = ClassCalibration.from_scores(np.array([0.1, 0.2]), np.array([1, 1]))
    p = pvalues(cal, np.array([[0.5, 0.15]]))
    assert p[0, 0] == 1.0  # (1 + 0) / (0 + 1)
    assert p[0, 1] == pytest.approx(2 / 3)


def test_classes_are_calibrated_separately() -> None:
    # the same score is rare in one class and common in the other
    s = np.array([0.9, 0.9, 0.9, 0.1, 0.1, 0.1])
    y = np.array([0, 0, 0, 1, 1, 1])
    cal = ClassCalibration.from_scores(s, y)
    p = pvalues(cal, np.array([[0.9, 0.9]]))
    assert p[0, 0] == pytest.approx(1.0)  # 0.9 is typical for class 0
    assert p[0, 1] == pytest.approx(1 / 4)  # and unusual for class 1


def test_credibility_is_the_p_value_of_the_predicted_class() -> None:
    p = np.array([[0.9, 0.1], [0.2, 0.6], [0.4, 0.4]])
    assert credibility(p, np.array([0, 1, 1])).tolist() == [0.9, 0.6, 0.4]


def test_input_checks() -> None:
    with pytest.raises(ValueError, match="shape"):
        pvalues(hand_calibration(), np.zeros((3, 3)))
    with pytest.raises(ValueError, match="finite"):
        pvalues(hand_calibration(), np.array([[np.nan, 0.1]]))
    with pytest.raises(ValueError, match="labels must lie"):
        ClassCalibration.from_scores(np.array([0.1]), np.array([2]))
    with pytest.raises(ValueError, match="outside"):
        credibility(np.zeros((1, 2)), np.array([2]))


# --- uniformity on exchangeable data ----------------------------------------------------------


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_p_values_of_exchangeable_data_are_uniform_and_valid(seed: int) -> None:
    """Over many fresh calibration sets, one exchangeable test sample per set.

    With ``n_cal`` calibration scores of a class the p-value of an exchangeable sample is
    uniform on {1/(n+1), ..., 1}, each value with probability 1/(n+1). For one *fixed*
    calibration set the p-values of many test samples share its sampling noise, so a KS test
    on a single set would be misleading.
    """
    rng = np.random.default_rng(seed)
    n_cal, trials = 9, 6000
    draw = {0: lambda n: rng.beta(2, 5, n), 1: lambda n: rng.beta(5, 2, n)}
    for c in (0, 1):
        ps = np.empty(trials)
        for k in range(trials):
            cal = ClassCalibration.from_scores(draw[c](n_cal), np.full(n_cal, c))
            test = np.zeros((1, 2))
            test[0, c] = draw[c](1)[0]
            ps[k] = pvalues(cal, test)[0, c]
        grid = np.arange(1, n_cal + 2) / (n_cal + 1)
        counts = np.array([np.isclose(ps, g).sum() for g in grid])
        assert counts.sum() == trials  # every p-value lies on the grid
        chi = scipy_stats.chisquare(counts)
        assert chi.pvalue > 0.001, f"class {c}: chi-square p = {chi.pvalue:.5f}"
        for eps in (0.1, 0.3, 0.5):  # validity: P(p <= eps) <= eps, up to noise
            assert (ps <= eps).mean() <= eps + 4 * np.sqrt(eps * (1 - eps) / trials)


def test_p_values_are_inflated_when_calibration_is_a_biased_draw() -> None:
    # the exchangeability trap: calibrate on the hard (high-score) samples a selector would pick
    rng = np.random.default_rng(3)
    pool = rng.beta(2, 5, 4000)
    hard = np.sort(pool)[-400:]  # an uncertainty-style selection of the top tail
    cal = ClassCalibration.from_scores(hard, np.zeros(len(hard), int))
    test = np.column_stack([rng.beta(2, 5, 4000), np.zeros(4000)])
    p = pvalues(cal, test)[:, 0]
    assert scipy_stats.kstest(p, "uniform").pvalue < 1e-6
    # fresh samples all look typical: the p-values sit far above uniform, so a credibility
    # selector or a drift monitor built on them cannot tell the unusual from the usual
    assert p.mean() > 0.8 and (p <= 0.05).mean() < 0.01


# --- scores -----------------------------------------------------------------------------------


def test_probability_score_is_one_minus_the_class_probability() -> None:
    s = ProbabilityScore().scores(None, np.array([0.1, 0.8]))
    assert s.tolist() == [[0.1, 0.9], [0.8, pytest.approx(0.2)]]  # (s_0, s_1)
    with pytest.raises(ValueError):
        ProbabilityScore().scores(None, np.array([1.2]))


def test_centroid_score_by_hand_dense_and_sparse_agree() -> None:
    X = np.array([[0.0, 0.0], [2.0, 0.0], [10.0, 10.0], [10.0, 12.0]])
    y = np.array([0, 0, 1, 1])
    q = np.array([[1.0, 0.0], [10.0, 11.0], [4.0, 3.0]])
    dense = CentroidScore().fit(X, y, "w1").scores(q)
    # centroids (1, 0) and (10, 11); distances of (4, 3): sqrt(9+9), sqrt(36+64)
    assert dense[0].tolist() == pytest.approx([0.0, np.hypot(9, 11)])
    assert dense[1].tolist() == pytest.approx([np.hypot(9, 11), 0.0])
    assert dense[2].tolist() == pytest.approx([np.hypot(3, 3), np.hypot(6, 8)])
    sparse = CentroidScore().fit(sp.csr_matrix(X), y, "w1").scores(sp.csr_matrix(q))
    assert sparse == pytest.approx(dense)


def test_centroid_score_uses_the_transform_and_refuses_another_window() -> None:
    X = np.array([[0.0], [2.0], [10.0], [12.0]])
    y = np.array([0, 0, 1, 1])
    cs = CentroidScore(transform=lambda Z: Z / 2.0).fit(X, y, "w1")
    assert cs.scores(np.array([[1.0]]))[0].tolist() == pytest.approx([0.0, 5.0])
    with pytest.raises(WindowMismatch):
        cs.scores(np.array([[1.0]]), window_id="w2")
    with pytest.raises(RuntimeError):
        CentroidScore().scores(np.array([[1.0]]))
    with pytest.raises(ValueError, match="each class"):
        CentroidScore().fit(X, np.zeros(4, int), "w")


# --- hold-out, buffer, contamination ----------------------------------------------------------


def test_time_ordered_holdout_is_newest_and_strictly_after_training() -> None:
    ts = np.array(np.arange(10), dtype="datetime64[D]")[np.random.default_rng(0).permutation(10)]
    train, hold = time_ordered_holdout(ts, 0.2)
    assert len(hold) == 2 and len(train) == 8
    assert ts[train].max() < ts[hold].min()


def test_time_ordered_holdout_never_splits_a_timestamp() -> None:
    ts = np.array(
        ["2020-01-01"] * 5 + ["2020-01-02"] * 3 + ["2020-01-03"] * 2, dtype="datetime64[D]"
    )
    train, hold = time_ordered_holdout(ts, 0.35)
    assert ts[train].max() < ts[hold].min()
    assert set(np.unique(ts[hold])) == {np.datetime64("2020-01-03")} or ts[
        hold
    ].min() == np.datetime64("2020-01-02")


def test_time_ordered_holdout_refuses_one_timestamp() -> None:
    with pytest.raises(ValueError, match="one timestamp"):
        time_ordered_holdout(np.array(["2020-01-01"] * 6, dtype="datetime64[D]"), 0.2)


def rows(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return rng.normal(size=(n, 3)), (np.arange(n) % 2).astype(int)


def test_a_selected_sample_in_the_calibration_buffer_fails() -> None:
    buf = CalibrationBuffer()
    X, y = rows(10)
    buf.add(X, y, "random_slice")  # fine
    buf.add(X, y, "holdout")  # fine
    origins = ["random_slice"] * 9 + ["selected"]
    with pytest.raises(CalibrationContamination):
        buf.add(X, y, origins)
    assert len(buf) == 20  # nothing from the failed call was kept


def test_the_trap_arm_must_say_so_and_unknown_origins_are_refused() -> None:
    X, y = rows(6)
    CalibrationBuffer(allow_selected=True).add(X, y, "selected")  # the named, logged trap
    with pytest.raises(ValueError, match="origin"):
        CalibrationBuffer().add(X, y, "somewhere")


def test_buffer_evicts_the_oldest_rows_first() -> None:
    rule = RecalibrationRule(min_per_class=2, buffer_size=10)
    buf = CalibrationBuffer(rule)
    for k in range(4):
        X = np.full((4, 1), float(k))
        buf.add(X, np.array([0, 1, 0, 1]), "random_slice")
    X, y = buf.rows()
    assert len(buf) == 10 and X[:, 0].tolist() == [1.0] * 2 + [2.0] * 4 + [3.0] * 4


def test_recalibration_skips_below_the_minimum_and_keeps_the_previous_calibration() -> None:
    rule = RecalibrationRule(min_per_class=3, buffer_size=100)
    buf = CalibrationBuffer(rule)
    score = lambda X, y: X[:, 0]  # noqa: E731 - own score is the first feature
    X = np.array([[0.1], [0.2], [0.3], [0.4], [0.5], [0.6]])
    buf.add(X[:2], np.array([0, 1]), "holdout")
    assert buf.recalibrate(score, slot_index=-1) is None and buf.n_skipped == 1
    buf.add(X[2:], np.array([0, 1, 0, 1]), "random_slice")
    first = buf.recalibrate(score, slot_index=0)
    assert first is not None and first.n_rows == 6 and buf.n_skipped == 1
    assert first.classes.counts() == (3, 3)
    # a smaller buffer cannot happen without eviction, so force a skip with a stricter rule
    buf.rule = RecalibrationRule(min_per_class=4, buffer_size=100)
    kept = buf.recalibrate(score, slot_index=1)
    assert kept is first and buf.n_skipped == 2 and buf.n_recalibrations == 1


def test_recalibration_recomputes_scores_under_the_current_model() -> None:
    buf = CalibrationBuffer(RecalibrationRule(min_per_class=2, buffer_size=50))
    X = np.array([[1.0], [2.0], [3.0], [4.0]])
    buf.add(X, np.array([0, 0, 1, 1]), "holdout")
    a = buf.recalibrate(lambda X, y: X[:, 0], 0)
    b = buf.recalibrate(lambda X, y: -X[:, 0], 1)
    assert a is not None and b is not None and a.classes.scores[0].tolist() == [1.0, 2.0]
    assert b.classes.scores[0].tolist() == [-2.0, -1.0] and b.built_at == 1


def test_rule_validation() -> None:
    with pytest.raises(ValueError):
        RecalibrationRule(holdout_fraction=0.0)
    with pytest.raises(ValueError):
        RecalibrationRule(min_per_class=20, buffer_size=30)


def test_module_exports() -> None:
    assert hasattr(mondrian, "pvalues") and hasattr(mondrian, "credibility")
