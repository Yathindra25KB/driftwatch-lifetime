"""AUT and A-AUT: the guide's unit tests, the Chow et al. window formula, slicer agreement.

Guide section 6 / PROTOCOL section 3: constant F1 gives that constant; a known two-point
example matches the hand-computed trapezoid. Chow et al. (arXiv 2506.23814v2) Eq. (2)-(4)
for nE >= nT and appendix A-E Eq. (6)-(8) for nE < nT, with the paper's worked examples
Eq. (9) and (10).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from driftwatch.data.canary import aut as canary_aut
from driftwatch.data.slicer import PlannedSlot, SlotRef, WindowSpec, plan_windows
from driftwatch.metrics.aut import (
    a_aut,
    aut,
    chow_stride,
    chow_window_count,
    chow_windows,
)

unit_f1 = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


# --- AUT -------------------------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3, 7, 40])
@pytest.mark.parametrize("c", [0.0, 0.25, 0.8, 1.0])
def test_constant_f1_gives_that_constant(n: int, c: float) -> None:
    assert aut([c] * n) == pytest.approx(c, abs=1e-12)


def test_two_point_example_matches_hand_computed_trapezoid() -> None:
    # N = 2: one trapezoid between (f1, f2): (0.8 + 0.6) / 2 = 0.7
    assert aut([0.8, 0.6]) == pytest.approx(0.7, abs=1e-12)


def test_three_point_example_matches_hand_computed_trapezoid() -> None:
    # 1/(3-1) * ((1.0+0.5)/2 + (0.5+0.0)/2) = 0.5 * (0.75 + 0.25)
    assert aut([1.0, 0.5, 0.0]) == pytest.approx(0.5, abs=1e-12)


def test_four_point_example_matches_hand_computed_trapezoid() -> None:
    # (0.9+0.7)/2 = 0.8, (0.7+0.8)/2 = 0.75, (0.8+0.4)/2 = 0.6; mean of three = 2.15 / 3
    assert aut([0.9, 0.7, 0.8, 0.4]) == pytest.approx(2.15 / 3, abs=1e-12)


def test_no_decay_scores_one_and_total_collapse_scores_zero() -> None:
    assert aut([1.0] * 5) == 1.0
    assert aut([0.0] * 5) == 0.0


@pytest.mark.parametrize("bad", [[], [0.5]])
def test_aut_needs_at_least_two_slots(bad: list[float]) -> None:
    with pytest.raises(ValueError, match="at least two"):
        aut(bad)


@pytest.mark.parametrize("bad", [[0.5, float("nan")], [0.5, 1.2], [-0.1, 0.5]])
def test_aut_rejects_values_that_are_not_f1(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        aut(bad)


@given(st.lists(unit_f1, min_size=2, max_size=60))
def test_aut_equals_numpy_trapezoid_over_unit_time_axis(f: list[float]) -> None:
    """The guide's formula is numpy's area under the curve on time rescaled to [0, 1].

    TESSERACT arXiv v4 says its published Eq. (4) carried an extra 1/N factor (a typo) and that
    the results rely on numpy's area-under-curve: this is the form the guide writes.
    """
    n = len(f)
    expected = float(np.trapezoid(np.asarray(f), dx=1.0 / (n - 1)))
    assert aut(f) == pytest.approx(expected, abs=1e-12)


@given(st.lists(unit_f1, min_size=2, max_size=60))
def test_aut_lies_between_min_and_max_and_matches_the_canary_implementation(
    f: list[float],
) -> None:
    value = aut(f)
    assert min(f) - 1e-12 <= value <= max(f) + 1e-12
    assert value == pytest.approx(canary_aut(f), abs=1e-12)


@given(st.lists(unit_f1, min_size=2, max_size=30))
def test_aut_is_unchanged_by_time_reversal(f: list[float]) -> None:
    assert aut(f) == pytest.approx(aut(f[::-1]), abs=1e-12)


# --- A-AUT -----------------------------------------------------------------------------------


def test_a_aut_is_mean_and_sample_std_of_window_auts() -> None:
    result = a_aut([0.6, 0.8])
    assert result.mean == pytest.approx(0.7)
    assert result.std == pytest.approx(math.sqrt(0.02))  # ddof = 1: sqrt(((0.1)^2 * 2) / 1)
    assert result.n_windows == 2


def test_a_aut_population_std_is_available_and_named() -> None:
    assert a_aut([0.6, 0.8], ddof=0).std == pytest.approx(0.1)


def test_a_aut_of_one_window_has_mean_and_no_std() -> None:
    result = a_aut([0.55])
    assert result.mean == pytest.approx(0.55)
    assert math.isnan(result.std)
    assert result.n_windows == 1


def test_a_aut_of_nothing_raises() -> None:
    with pytest.raises(ValueError, match="at least one window"):
        a_aut([])


def test_a_aut_of_identical_windows_has_zero_spread() -> None:
    result = a_aut([0.7] * 5)
    assert result.mean == pytest.approx(0.7)
    assert result.std == pytest.approx(0.0, abs=1e-12)


# --- window formula (Chow et al.) --------------------------------------------------------------


def test_chow_stride_is_the_smaller_window() -> None:
    assert chow_stride(4, 12) == 4  # nE >= nT: windows advance by nT (Eq. 2-3)
    assert chow_stride(12, 4) == 4  # nE < nT: windows advance by nE (Eq. 6-7)
    assert chow_stride(5, 5) == 5


def test_paper_example_eq9_equal_windows() -> None:
    """nT = nE = 12 months over 2014-2019: T = D2014..D2018, E = D2015..D2019 (Eq. 9)."""
    windows = chow_windows(n_slots=72, nT=12, nE=12)
    assert len(windows) == 5
    assert [(t.start // 12, e.start // 12) for t, e in windows] == [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
    ]
    assert all(len(t) == 12 and len(e) == 12 for t, e in windows)


def test_paper_example_eq10_longer_evaluation_window() -> None:
    """nT = 12, nE = 24 months over 2014-2019: T = D2014..D2017, E = D2015:2016..D2018:2019."""
    windows = chow_windows(n_slots=72, nT=12, nE=24)
    assert len(windows) == 4
    assert [t.start // 12 for t, _ in windows] == [0, 1, 2, 3]
    assert windows[0][1] == range(12, 36)  # 2015:2016
    assert windows[-1][1] == range(48, 72)  # 2018:2019
    assert chow_window_count(72, 12, 24) == 4  # Eq. (4): floor((72 - 24) / 12)


def test_appendix_case_nT_larger_than_nE() -> None:
    """Eq. (6)-(8): training windows overlap, evaluation windows are contiguous."""
    windows = chow_windows(n_slots=20, nT=6, nE=2)
    assert len(windows) == (20 - 6) // 2 == 7  # Eq. (8): floor((|D| - nT) / nE)
    for i, (train, evaluation) in enumerate(windows):
        assert train == range(2 * i, 2 * i + 6)  # Eq. (6)
        assert evaluation == range(6 + 2 * i, 6 + 2 * i + 2)  # Eq. (7)
    evals = [e for _, e in windows]
    assert all(a.stop == b.start for a, b in zip(evals, evals[1:], strict=False))  # contiguous
    assert windows[0][0].start == 0 and windows[1][0].start == 2  # training windows overlap


def test_nE_at_least_nT_gives_disjoint_training_windows() -> None:
    windows = chow_windows(n_slots=30, nT=4, nE=8)
    trains = [t for t, _ in windows]
    assert len(windows) == (30 - 8) // 4 == 5  # Eq. (4)
    assert all(a.stop == b.start for a, b in zip(trains, trains[1:], strict=False))


@given(st.integers(1, 12), st.integers(1, 12), st.integers(0, 90))
def test_count_matches_the_literal_equations_and_the_unified_form(nT: int, nE: int, n: int) -> None:
    literal = (n - nE) // nT if nE >= nT else (n - nT) // nE  # Eq. (4) and Eq. (8)
    literal = max(literal, 0)
    assert chow_window_count(n, nT, nE) == literal
    assert len(chow_windows(n, nT, nE)) == literal
    if n >= nT + nE:  # unified: stride min(nT, nE), floor((n - nT - nE) / stride) + 1
        assert literal == (n - nT - nE) // chow_stride(nT, nE) + 1
    else:
        assert literal == 0


@given(st.integers(1, 10), st.integers(1, 10), st.integers(0, 70))
def test_every_window_is_contiguous_inside_the_data_and_evaluation_follows_training(
    nT: int, nE: int, n: int
) -> None:
    for train, evaluation in chow_windows(n, nT, nE):
        assert len(train) == nT and len(evaluation) == nE
        assert train.stop == evaluation.start  # evaluation begins right after training (C1)
        assert train.start >= 0 and evaluation.stop <= n


@pytest.mark.parametrize("bad", [(0, 3), (3, 0), (-1, 2)])
def test_window_sizes_must_be_positive(bad: tuple[int, int]) -> None:
    with pytest.raises(ValueError):
        chow_stride(*bad)


# --- agreement with the slicer ----------------------------------------------------------------


def _run_of(n: int) -> list[PlannedSlot]:
    day = np.timedelta64(1, "D")
    t0 = np.datetime64("2020-01-01", "ns")
    slots = []
    for i in range(n):
        ref = SlotRef(f"s{i:03d}", t0 + i * day, t0 + (i + 1) * day, i)
        slots.append(PlannedSlot(ref, 100, 40, 60, 0, 40, "", True, ""))
    return slots


@pytest.mark.parametrize(("nT", "nE"), [(4, 12), (3, 6), (6, 2), (5, 5), (1, 3), (7, 1)])
@pytest.mark.parametrize("n", [0, 5, 16, 33, 62])
def test_slicer_windows_equal_the_formula_at_the_chow_stride(nT: int, nE: int, n: int) -> None:
    """The slicer is the same window generator as Chow et al. once stride = min(nT, nE)."""
    spec = WindowSpec(nT=nT, nE=nE, stride=chow_stride(nT, nE))
    schedule = plan_windows(_run_of(n), spec)
    got = [
        (
            range(w.train[0].index, w.train[-1].index + 1),
            range(w.eval[0].index, w.eval[-1].index + 1),
        )
        for w in schedule.windows
    ]
    assert got == chow_windows(n, nT, nE)


def test_adr_0005_strides_differ_from_the_chow_stride_on_both_datasets() -> None:
    """ADR-0005 keeps stride 3 (LAMDA) and 2 (BODMAS); Chow's formula gives 4 and 3."""
    assert chow_stride(4, 12) == 4 != 3
    assert chow_stride(3, 6) == 3 != 2
    assert chow_window_count(62, 4, 12) == 12  # the 62-month LAMDA run at Chow's stride
    assert len(plan_windows(_run_of(62), WindowSpec(4, 12, 3)).windows) == 16  # ADR-0005
