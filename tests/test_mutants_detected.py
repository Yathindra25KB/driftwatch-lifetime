"""Every deliberate breakage must make at least one declared detector fail.

If a mutant here ever survives, some leakage rule has no test that would notice it being
broken: add a test, never remove the mutant.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest
import test_constraints as tc
from slicer_mutants import MUTANTS
from slicer_oracle import assert_window_matches_oracle, expected_windows, slot_index_of
from timelines import build_timeline, to_table

from driftwatch.data import constraints
from driftwatch.data.slicer import WindowSpec, slice_windows
from driftwatch.data.tables import FixedWidthScheme, TableSource

STANDARD = (40, 180)


def _source(tl) -> TableSource:
    scheme = FixedWidthScheme(
        np.datetime64(tl.anchor, "s").astype("datetime64[ns]"), np.timedelta64(tl.width, "s")
    )
    return TableSource(to_table(tl), scheme, name="probe")


def _timelines():
    plain = {k: STANDARD for k in range(10)}
    with_gap = {k: STANDARD for k in range(12) if k != 5}
    gated = {**{k: STANDARD for k in range(10)}, 4: (1, 180)}
    below = {**{k: STANDARD for k in range(8)}, 3: (12, 180), 5: (9, 120)}
    return [
        build_timeline(plain, seed=1),
        build_timeline(with_gap, seed=2, anchor=3 * 3600),
        build_timeline(gated, seed=3),
        build_timeline(below, seed=4, width=7 * 86400),
    ]


SPECS = [
    WindowSpec(nT=3, nE=2, stride=1, target_ratio=0.10, min_malware=2, seed=0),
    WindowSpec(nT=2, nE=3, stride=2, target_ratio=0.10, min_malware=2, seed=5),
    WindowSpec(nT=3, nE=None, stride=1, target_ratio=0.20, min_malware=2, seed=1),
]


def probe_windows_against_oracle() -> None:
    """Deterministic scenarios (gaps, a failing slot, a below-target slot, boundary rows)."""
    for tl in _timelines():
        for spec in SPECS:
            windows = list(slice_windows(_source(tl), spec))
            keys = [
                (
                    tuple(slot_index_of(tl, r.start, r.end) for r in w.plan.train),
                    tuple(slot_index_of(tl, r.start, r.end) for r in w.plan.eval),
                )
                for w in windows
            ]
            want = expected_windows(
                tl,
                nT=spec.nT,
                nE=spec.nE,
                stride=spec.stride,
                ratio=spec.target_ratio,
                min_malware=spec.min_malware,
            )
            assert keys == want, "windows differ from the oracle"
            for w in windows:
                assert_window_matches_oracle(w, tl, ratio=spec.target_ratio)


def probe_same_seed_same_rows() -> None:
    tl = build_timeline({k: STANDARD for k in range(8)}, seed=9)
    spec = WindowSpec(nT=3, nE=3, stride=1, target_ratio=0.10, min_malware=2, seed=3)

    def run() -> list[bytes]:
        return [
            s.row_id.tobytes() for w in slice_windows(_source(tl), spec) for s in w.eval_slots()
        ]

    assert run() == run(), "the same seed gave different evaluation rows"


def probe_public_view_is_opaque() -> None:
    import test_slicer_review_fixes as rf

    rf.test_f1_public_row_order_and_handles_carry_no_class_signal()
    rf.test_f1_public_features_follow_their_handles_and_resolve_to_true_rows()


DETECTORS: dict[str, tuple[Callable[[], None], ...]] = {
    "oldest_malware": (
        lambda: tc.test_the_malware_draw_is_not_biased_toward_early_or_late_rows(0),
    ),
    "public_ids_are_row_ids": (probe_public_view_is_opaque,),
    "shift_boundary": (probe_windows_against_oracle,),
    "shuffle_timestamps": (probe_windows_against_oracle,),
    "leak_one_sample": (probe_windows_against_oracle,),
    "span_gap": (probe_windows_against_oracle,),
    "gate_off": (probe_windows_against_oracle,),
    "stride_ignored": (probe_windows_against_oracle,),
    "eval_overlaps_train": (probe_windows_against_oracle,),
    "c1_non_strict": (tc.test_c1_is_strict_equal_timestamps_violate,),
    "c2_inclusive_end": (tc.test_c2_rejects_a_sample_exactly_at_the_window_end,),
    "c3_drop_benign": (probe_windows_against_oracle,),
    "c3_unseeded": (probe_same_seed_same_rows,),
    "no_subsampling": (probe_windows_against_oracle,),
}


def test_every_mutant_has_a_declared_detector():
    assert set(DETECTORS) == set(MUTANTS)


def test_the_probes_pass_on_the_unmutated_slicer():
    probe_windows_against_oracle()
    probe_same_seed_same_rows()
    tc.test_c1_is_strict_equal_timestamps_violate()
    tc.test_c2_rejects_a_sample_exactly_at_the_window_end()


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_mutant_is_caught(name, monkeypatch):
    MUTANTS[name].apply(monkeypatch)
    # test_constraints imported the checks by name; point it at the mutated ones, as the
    # subprocess plugin does by patching before that import.
    for attr in ("check_c1", "check_c2", "check_c3", "subsample_malware", "target_malware_count"):
        monkeypatch.setattr(tc, attr, getattr(constraints, attr))
    caught = []
    for detector in DETECTORS[name]:
        try:
            detector()
        except (Exception, pytest.fail.Exception) as exc:  # "DID NOT RAISE" is a Failed outcome
            caught.append(f"{detector.__name__}: {type(exc).__name__}")
    assert caught, f"mutant {name!r} ({MUTANTS[name].breaks}) survived every detector"
