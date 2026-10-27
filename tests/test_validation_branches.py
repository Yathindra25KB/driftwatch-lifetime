"""Input-validation branches of the constraints, the queue and the conformal layer.

C1 to C3 are checks that raise (CLAUDE.md rule 2). The happy paths are covered by the slicer,
simulator and E3 tests; these pin the refusals, so that a malformed input cannot pass
silently: a missing timestamp, labels outside {0, 1}, a kept set that is not a set of valid
row indices, a window with no slot, an empty calibration buffer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from driftwatch.conformal.mondrian import ClassCalibration, credibility
from driftwatch.conformal.recalibrate import CalibrationBuffer, time_ordered_holdout
from driftwatch.data import constraints as C
from driftwatch.sim.queue import LabelQueue

T0, T1 = pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-15")
INSIDE = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"])


def test_c2_refuses_a_missing_timestamp_and_labels_outside_zero_one() -> None:
    with pytest.raises(C.C2Violation, match="timestamp is missing"):
        C.check_c2(pd.to_datetime(["2020-01-02", None]), [0, 1], T0, T1)
    with pytest.raises(C.C2Violation, match="must be 0 .benign. or 1"):
        C.check_c2(INSIDE[:3], [0, 1, 2], T0, T1)
    with pytest.raises(C.C2Violation, match="do not line up"):
        C.check_c2(INSIDE[:3], [0, 1], T0, T1)
    with pytest.raises(C.C2Violation, match="empty window"):
        C.check_c2(INSIDE[:2], [0, 1], T1, T0)


def test_c3_subsampling_refuses_bad_labels_a_negative_seed_and_a_slot_without_benign() -> None:
    with pytest.raises(C.C3Violation, match="1-D array of 0"):
        C.subsample_malware([0, 1, 2], 0.1, 0, "s")
    with pytest.raises(C.C3Violation, match="seed must be non-negative"):
        C.subsample_malware([0, 1], 0.1, -1, "s")
    with pytest.raises(C.C3Violation, match="without benign"):
        C.subsample_malware([1, 1, 1], 0.1, 0, "s")
    with pytest.raises(C.C3Violation, match="without benign"):
        C.check_c3([1, 1, 1], np.arange(3), 0.1)


def test_c3_check_refuses_a_kept_set_that_is_not_a_set_of_row_indices() -> None:
    y = np.array([0] * 9 + [1] * 3)
    with pytest.raises(C.C3Violation, match="kept must be a 1-D array of row indices"):
        C.check_c3(y, np.array([[0, 1]]), 0.1)
    with pytest.raises(C.C3Violation, match="kept must be a 1-D array of row indices"):
        C.check_c3(y, np.array([0.5, 1.5]), 0.1)
    with pytest.raises(C.C3Violation, match="outside the slot"):
        C.check_c3(y, np.array([0, 99]), 0.1)
    with pytest.raises(C.C3Violation, match="more than once"):
        C.check_c3(y, np.array([0, 0, 1]), 0.1)


def test_c3_result_is_a_plain_record_for_the_manifest() -> None:
    y = np.array([0] * 20 + [1] * 5)
    kept = C.subsample_malware(y, 0.1, 0, "s")
    record = C.check_c3(y, kept, 0.1).as_record()
    assert record["status"] in ("at_target", "below_target")
    assert record["n_benign_before"] == 20 and record["target_ratio"] == 0.1


def test_the_queue_refuses_an_empty_window_and_a_release_outside_it() -> None:
    with pytest.raises(ValueError, match="n_slots must be a positive integer"):
        LabelQueue(delay=0, n_slots=0)
    with pytest.raises(ValueError, match="delay must be a non-negative integer"):
        LabelQueue(delay=-1, n_slots=3)
    q = LabelQueue(delay=0, n_slots=1)
    first = q.release(0)
    assert len(first) == 0 and q.n_pending == 0
    with pytest.raises(ValueError, match="releases must be in order"):
        q.release(0)
    with pytest.raises(ValueError, match="outside the window"):
        # in order (the next index is 1) but beyond the one-slot window
        q.release(1)


def test_released_rows_take_a_mask_of_the_right_length_only() -> None:
    first = LabelQueue(delay=0, n_slots=2).release(0)
    assert first.take(np.zeros(0, dtype=bool)) is first  # nothing arrived: the same object
    with pytest.raises(ValueError, match="one entry per released row"):
        first.take(np.ones(3, dtype=bool))


def test_the_hold_out_needs_two_rows_with_distinct_timestamps() -> None:
    with pytest.raises(ValueError, match="at least two rows"):
        time_ordered_holdout(np.array(["2020-01-01"], dtype="datetime64[ns]"), 0.2)
    same = np.array(["2020-01-01"] * 5, dtype="datetime64[ns]")
    with pytest.raises(ValueError, match="share one timestamp"):
        time_ordered_holdout(same, 0.2)


def test_the_calibration_buffer_refuses_misaligned_rows_and_an_empty_read() -> None:
    buf = CalibrationBuffer()
    assert buf.class_counts() == (0, 0) and len(buf) == 0
    with pytest.raises(ValueError, match="buffer is empty"):
        buf.rows()
    buf.add(np.zeros((0, 2)), np.zeros(0, dtype=np.int8), "holdout")  # nothing to add
    assert len(buf) == 0
    with pytest.raises(ValueError, match="must line up"):
        buf.add(np.zeros((3, 2)), np.array([0, 1]), "holdout")


def test_mondrian_calibration_and_credibility_refuse_malformed_arrays() -> None:
    with pytest.raises(ValueError, match="one-dimensional and the same length"):
        ClassCalibration.from_scores(np.array([0.1, 0.2]), np.array([0]))
    with pytest.raises(ValueError, match="must be finite"):
        ClassCalibration.from_scores(np.array([0.1, np.nan]), np.array([0, 1]))
    with pytest.raises(ValueError, match="labels must lie in"):
        ClassCalibration.from_scores(np.array([0.1, 0.2]), np.array([0, 5]))
    with pytest.raises(ValueError, match="p must be .n, classes."):
        credibility(np.array([0.5, 0.5]), np.array([0, 1]))
    with pytest.raises(ValueError, match="outside the p-value columns"):
        credibility(np.full((2, 2), 0.5), np.array([0, 2]))
