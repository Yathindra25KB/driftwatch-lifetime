"""Window options are derived from slot counts only: no features, no labels beyond counts."""

from __future__ import annotations

import numpy as np
from slicer_oracle import expected_windows
from timelines import build_timeline, to_table

from driftwatch.data.slicer import SlotSource
from driftwatch.data.tables import FixedWidthScheme, TableSource
from driftwatch.data.window_options import candidate_windows, run_lengths, segment_table


def source(per_slot, **kw) -> tuple[SlotSource, object]:
    tl = build_timeline(per_slot, **kw)
    scheme = FixedWidthScheme(
        np.datetime64(tl.anchor, "s").astype("datetime64[ns]"), np.timedelta64(tl.width, "s")
    )
    return TableSource(to_table(tl), scheme, name="t"), tl


def test_segments_report_length_and_below_target_slots():
    per_slot = {k: (40, 180) for k in range(8) if k != 3}
    per_slot[5] = (12, 180)  # below target at 10%
    src, _ = source(per_slot)
    segs = segment_table(src, ratio=0.10, min_malware=2)
    assert [s["n_slots"] for s in segs] == [3, 4]
    assert [s["n_below_target"] for s in segs] == [0, 1]
    assert segs[0]["first"] < segs[0]["last"] < segs[1]["first"]


def test_run_lengths_matches_the_segments():
    src, _ = source({k: (40, 180) for k in range(6)})
    assert run_lengths(src, ratio=0.10, min_malware=2) == [6]


def test_candidate_window_counts_match_the_independent_oracle():
    per_slot = {k: (40, 180) for k in range(14) if k != 6}
    src, tl = source(per_slot)
    for nT, nE, stride in [(3, 4, 1), (3, 4, 2), (2, 5, 3), (4, 12, 1)]:
        got = candidate_windows(src, nT=nT, nE=nE, stride=stride, ratio=0.10, min_malware=2)
        want = expected_windows(tl, nT=nT, nE=nE, stride=stride, ratio=0.10, min_malware=2)
        assert got["n_windows"] == len(want), (nT, nE, stride)
        assert got["n_eval_slots_distinct"] == len({e for _, ev in want for e in ev})


def test_overlap_is_the_share_of_evaluation_slots_reused_across_windows():
    src, _ = source({k: (40, 180) for k in range(10)})
    disjoint = candidate_windows(src, nT=2, nE=4, stride=4, ratio=0.10, min_malware=2)
    shifted = candidate_windows(src, nT=2, nE=4, stride=1, ratio=0.10, min_malware=2)
    assert disjoint["eval_reuse"] == 1.0  # every evaluation slot appears in exactly one window
    assert shifted["eval_reuse"] > 1.0
