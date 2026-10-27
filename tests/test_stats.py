"""Two-stage bootstrap, contrasts, effect-size units and the supporting Wilcoxon check.

Hand-computed arrays only (no model, no data): the units and signs of every contrast are
pinned here before any grid result exists.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftwatch.metrics import stats

FAST = {"n_boot": 2000, "seed": 7}


def _mat(rows: list[list[float]]) -> np.ndarray:
    return np.asarray(rows, dtype=np.float64)


# --- block length -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n_eval", "stride", "expected"), [(12, 3, 4), (6, 2, 3), (12, 4, 3), (6, 3, 2), (5, 5, 1)]
)
def test_block_length_is_windows_sharing_a_slot(n_eval: int, stride: int, expected: int) -> None:
    assert stats.block_length(n_eval, stride) == expected


# --- paired point estimates -------------------------------------------------------------------


def test_difference_point_is_mean_over_windows_of_seed_means() -> None:
    a = _mat([[0.9, 0.7], [0.8, 0.8], [0.6, 0.6]])  # seed means 0.8, 0.8, 0.6 -> 0.7333
    b = _mat([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]])
    est = stats.difference({"a": a, "b": b}, "a", "b", block_len=1, **FAST)
    assert est.point == pytest.approx((0.8 + 0.8 + 0.6) / 3 - 0.5)


def test_constant_difference_has_a_degenerate_interval() -> None:
    base = np.random.default_rng(0).uniform(0.4, 0.9, size=(8, 4))
    est = stats.difference({"a": base + 0.05, "b": base}, "a", "b", block_len=3, **FAST)
    assert est.point == pytest.approx(0.05)
    assert est.low == pytest.approx(0.05) and est.high == pytest.approx(0.05)


def test_pairing_removes_the_shared_window_effect() -> None:
    rng = np.random.default_rng(1)
    shared = rng.normal(0.7, 0.15, size=(12, 5))  # large shared window/seed variation
    a, b = shared + 0.02, shared
    paired = stats.difference({"a": a, "b": b}, "a", "b", block_len=2, **FAST)
    unpaired = stats.estimate(
        a.mean() - b.mean(),
        stats.resample_means({"a": a}, 2, **FAST)["a"]
        - stats.resample_means({"b": b}, 2, n_boot=2000, seed=8)["b"],
    )
    assert paired.half_width < unpaired.half_width / 5


def test_interval_is_not_overconfident_and_at_most_moderately_conservative() -> None:
    # Resampling windows and then seeds inside them counts the within-window variance twice,
    # so for iid cells the interval is conservative (about sqrt(2) wide when seed noise
    # dominates). It must never be narrower than the plain standard error of the grand mean.
    rng = np.random.default_rng(2)
    hits, trials, ratios = 0, 120, []
    for t in range(trials):
        m = rng.normal(0.1, 0.05, size=(30, 4))
        z = np.zeros_like(m)
        est = stats.difference({"a": m, "z": z}, "a", "z", block_len=1, n_boot=400, seed=t)
        hits += est.low <= 0.1 <= est.high
        se = m.std(ddof=1) / np.sqrt(m.size)
        ratios.append(est.half_width / (1.96 * se))
    assert hits / trials >= 0.90
    assert 1.0 <= float(np.mean(ratios)) <= 1.6


def test_block_resampling_widens_the_interval_for_autocorrelated_windows() -> None:
    rng = np.random.default_rng(3)
    walk = np.cumsum(rng.normal(0, 0.05, size=60))  # strongly autocorrelated window series
    a = np.repeat(walk[:, None], 3, axis=1)
    z = np.zeros_like(a)
    iid = stats.difference({"a": a, "z": z}, "a", "z", block_len=1, **FAST)
    blocked = stats.difference({"a": a, "z": z}, "a", "z", block_len=8, **FAST)
    assert blocked.half_width > 1.5 * iid.half_width


def test_seed_stage_contributes_spread_when_windows_are_identical() -> None:
    # every window has the same per-seed values, so only the seed stage can move the mean
    row = [0.2, 0.4, 0.6, 0.8]
    a = _mat([row] * 6)
    z = np.zeros_like(a)
    est = stats.difference({"a": a, "z": z}, "a", "z", block_len=2, **FAST)
    assert est.point == pytest.approx(0.5)
    assert est.low < 0.5 < est.high


def test_resampling_is_deterministic_and_seeded() -> None:
    m = np.random.default_rng(4).uniform(size=(9, 3))
    one = stats.resample_means({"m": m}, 3, n_boot=50, seed=11)["m"]
    two = stats.resample_means({"m": m}, 3, n_boot=50, seed=11)["m"]
    other = stats.resample_means({"m": m}, 3, n_boot=50, seed=12)["m"]
    assert np.array_equal(one, two) and not np.array_equal(one, other)


def test_arms_use_the_same_indices() -> None:
    m = np.random.default_rng(5).uniform(size=(7, 3))
    rs = stats.resample_means({"x": m, "y": m + 1.0}, 2, n_boot=100, seed=3)
    assert np.allclose(rs["y"] - rs["x"], 1.0)


def test_resample_rejects_mismatched_shapes() -> None:
    with pytest.raises(ValueError, match="shape"):
        stats.resample_means({"a": np.zeros((4, 2)), "b": np.zeros((4, 3))}, 1, **FAST)


# --- effect sizes in plain units --------------------------------------------------------------


def test_delay_slope_is_aut_lost_per_slot_with_the_right_sign() -> None:
    # AUT falls by exactly 0.03 per slot of delay: slope -0.03, so "lost per slot" is +0.03
    base = np.random.default_rng(6).uniform(0.5, 0.7, size=(8, 3))
    arms = {f"d{d}": base - 0.03 * d for d in range(4)}
    sl = stats.slope(arms, {f"d{d}": float(d) for d in range(4)}, block_len=2, **FAST)
    assert sl.point == pytest.approx(-0.03)
    lost = stats.scale(sl, -1.0)
    assert lost.point == pytest.approx(0.03) and lost.low <= lost.point <= lost.high


def test_contrast_scaled_to_per_slot_of_delay() -> None:
    base = np.full((5, 2), 0.6)
    est = stats.difference({"d0": base + 0.09, "d3": base}, "d0", "d3", block_len=1, **FAST)
    per_slot = stats.scale(est, 1 / 3)
    assert per_slot.point == pytest.approx(0.03)


def test_scale_with_negative_factor_swaps_the_ends() -> None:
    est = stats.Estimate(0.1, 0.05, 0.2)
    flipped = stats.scale(est, -2.0)
    assert (flipped.point, flipped.low, flipped.high) == pytest.approx((-0.2, -0.4, -0.1))


def test_slope_needs_two_distinct_x() -> None:
    arms = {"a": np.zeros((3, 2)), "b": np.ones((3, 2))}
    with pytest.raises(ValueError, match="distinct"):
        stats.slope(arms, {"a": 1.0, "b": 1.0}, block_len=1, **FAST)


def test_per_100_labels_units() -> None:
    gain = stats.Estimate(0.02, 0.01, 0.03)  # AUT gained going from 20 to 120 labels per slot
    per_100 = stats.scale(gain, 100.0 / (120.0 - 20.0))
    assert per_100.point == pytest.approx(0.02)
    per_label = stats.scale(gain, 1.0 / (120.0 - 20.0))
    assert per_label.point == pytest.approx(0.0002)


# --- supporting checks ------------------------------------------------------------------------


def test_wilcoxon_floor_for_ten_pairs_and_five_pairs() -> None:
    assert stats.wilcoxon_p(np.arange(1.0, 11.0)) == pytest.approx(2 / 2**10)
    assert stats.wilcoxon_p(np.arange(1.0, 6.0)) == pytest.approx(0.0625)  # guide section 10
    assert stats.min_wilcoxon_p(10) == pytest.approx(2 / 1024)
    assert stats.min_wilcoxon_p(5) == pytest.approx(0.0625)


def test_wilcoxon_all_zero_is_one_not_an_error() -> None:
    assert stats.wilcoxon_p(np.zeros(10)) == 1.0


def test_seed_paired_means_average_windows() -> None:
    a = _mat([[1.0, 2.0], [3.0, 4.0]])
    b = _mat([[0.0, 0.0], [1.0, 2.0]])
    assert stats.seed_paired_means({"a": a, "b": b}, "a", "b").tolist() == [1.5, 2.0]


def test_holm_matches_the_textbook_example() -> None:
    adj = stats.holm([0.01, 0.04, 0.03, 0.005])
    assert adj == pytest.approx([0.03, 0.06, 0.06, 0.02])


# --- tables from stored predictions -----------------------------------------------------------


def _preds(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["model", "seed", "window_id", "slot_id", "y_true", "pred"]
    ).astype({"seed": "int64", "y_true": "int8", "pred": "int8"})


def test_f1_per_slot_and_aut_matrix_by_hand() -> None:
    w1, w2 = "h1|month:2019-01|T2|E3", "h1|month:2019-02|T2|E3"
    rows = []
    # window 1, seed 0: slot a: tp=1 fp=0 fn=1 -> F1 2/3; slot b: tp=2 fp=0 fn=0 -> 1.0
    rows += [("lr", 0, w1, "a", 1, 1), ("lr", 0, w1, "a", 1, 0), ("lr", 0, w1, "a", 0, 0)]
    rows += [("lr", 0, w1, "b", 1, 1), ("lr", 0, w1, "b", 1, 1), ("lr", 0, w1, "b", 0, 0)]
    # window 2 has a single slot: AUT undefined, counted and excluded
    rows += [("lr", 0, w2, "c", 1, 1), ("lr", 0, w2, "c", 0, 0)]
    order = pd.DataFrame(
        {
            "window_id": [w1, w1, w2],
            "slot_id": ["a", "b", "c"],
            "slot_index": [10, 11, 12],
        }
    )
    cells = stats.f1_per_slot(_preds(rows), order)
    f1 = cells.set_index("slot_id")["f1"]
    assert f1["a"] == pytest.approx(2 / 3) and f1["b"] == pytest.approx(1.0)
    m = stats.aut_matrix(cells, "lr")
    assert m.n_windows_undefined == 1
    assert list(m.values.index) == ["month:2019-01|T2|E3"]
    assert m.values.loc["month:2019-01|T2|E3", 0] == pytest.approx((2 / 3 + 1.0) / 2)


def test_f1_per_slot_rejects_unlisted_slots() -> None:
    rows = [("lr", 0, "h|w", "zzz", 1, 1)]
    order = pd.DataFrame({"window_id": ["h|w"], "slot_id": ["a"], "slot_index": [0]})
    with pytest.raises(ValueError, match="slot table"):
        stats.f1_per_slot(_preds(rows), order)


def test_align_arms_requires_the_same_windows() -> None:
    idx1, idx2 = ["w1", "w2"], ["w1", "w3"]
    a = pd.DataFrame(np.ones((2, 2)), index=idx1, columns=[0, 1])
    b = pd.DataFrame(np.ones((2, 2)), index=idx2, columns=[0, 1])
    with pytest.raises(ValueError, match="other windows"):
        stats.align_arms({"a": a, "b": b})


def test_align_arms_cuts_to_the_requested_seeds_and_keeps_window_order() -> None:
    a = pd.DataFrame(
        np.arange(6.0).reshape(2, 3), index=["w2", "w1"], columns=[0, 1, 2]
    )  # window order is time order, not alphabetical
    b = a.copy() + 1
    arrays, windows, seeds = stats.align_arms({"a": a, "b": b}, seeds=[0, 2])
    assert windows == ["w2", "w1"] and seeds == [0, 2]
    assert arrays["a"].tolist() == [[0.0, 2.0], [3.0, 5.0]]
    with pytest.raises(ValueError, match="no seed"):
        stats.align_arms({"a": a}, seeds=[0, 9])


def test_align_arms_rejects_missing_cells() -> None:
    a = pd.DataFrame([[0.5, np.nan]], index=["w1"], columns=[0, 1])
    with pytest.raises(ValueError, match="missing AUT"):
        stats.align_arms({"a": a})


def test_reading_predictions_in_batches_gives_the_same_f1(tmp_path) -> None:
    rng = np.random.default_rng(0)
    n = 200
    df = pd.DataFrame(
        {
            "series": "time_aware",
            "variant": "rolling",
            "model": rng.choice(["lr", "lgbm"], n),
            "seed": rng.integers(0, 3, n),
            "window_id": rng.choice(["h|month:2019-01|T2|E3", "h|month:2019-02|T2|E3"], n),
            "slot_id": rng.choice(["a", "b", "c"], n),
            "y_true": rng.integers(0, 2, n).astype("int8"),
            "pred": rng.integers(0, 2, n).astype("int8"),
        }
    )
    order = pd.DataFrame(
        [
            (w, s, i)
            for i, (w, s) in enumerate(
                (w, s) for w in ["h|month:2019-01|T2|E3", "h|month:2019-02|T2|E3"] for s in "abc"
            )
        ],
        columns=["window_id", "slot_id", "slot_index"],
    )
    path = tmp_path / "p.parquet"
    df.to_parquet(path, index=False)
    whole = stats.f1_per_slot(df, order)
    batched = stats.f1_per_slot_from_file(path, order, list(df.columns), batch_rows=7)
    keys = ["model", "seed", "window_id", "slot_id", "series", "variant"]
    a = whole.sort_values(keys).reset_index(drop=True)
    b = batched.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(
        a[keys + ["tp", "fp", "fn", "f1"]], b[keys + ["tp", "fp", "fn", "f1"]]
    )
    only = stats.f1_per_slot_from_file(path, order, list(df.columns), series="time_aware")
    assert len(only) == len(whole)
    with pytest.raises(ValueError, match="no predictions"):
        stats.f1_per_slot_from_file(path, order, list(df.columns), series="random_split")
