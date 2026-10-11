"""An independent oracle for the slicer: what must be true, derived from raw timestamps only.

It never imports slicer internals. A timeline is integer seconds, a label and an id per
row, and a slot grid given by an anchor and a width in seconds, so slot ``k`` is
``[anchor + k * width, anchor + (k + 1) * width)``. Everything the slicer yields is compared
with what this module recomputes from scratch, using integer arithmetic, so a boundary
off-by-one, a leaked sample or a window over a gap shows up here even when the slicer's own
checks have been broken.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import numpy as np


@dataclass(frozen=True)
class RawTimeline:
    ts: np.ndarray  # int64 seconds
    y: np.ndarray  # int8, 1 = malware
    row_id: np.ndarray  # int64, unique
    anchor: int
    width: int

    def cell_of(self, ts: np.ndarray) -> np.ndarray:
        return (ts - self.anchor) // self.width

    def bounds(self, k: int) -> tuple[int, int]:
        return self.anchor + k * self.width, self.anchor + (k + 1) * self.width


def target_count(n_benign: int, ratio: float) -> int:
    r = Fraction(str(ratio))
    return (n_benign * r.numerator) // (r.denominator - r.numerator)


def cells(tl: RawTimeline) -> dict[int, dict[str, np.ndarray | int]]:
    """slot index -> row positions and class counts, for every populated slot."""
    out: dict[int, dict[str, np.ndarray | int]] = {}
    k = tl.cell_of(tl.ts)
    for key in np.unique(k):
        pos = np.flatnonzero(k == key)
        n_mal = int((tl.y[pos] == 1).sum())
        out[int(key)] = {"pos": pos, "n_mal": n_mal, "n_ben": len(pos) - n_mal}
    return out


def usable_cells(tl: RawTimeline, ratio: float, min_malware: int) -> list[int]:
    ok = []
    for key, c in cells(tl).items():
        kept = min(int(c["n_mal"]), target_count(int(c["n_ben"]), ratio))
        if kept >= min_malware:
            ok.append(key)
    return sorted(ok)


def runs(keys: list[int]) -> list[list[int]]:
    """Maximal runs of consecutive integers."""
    out: list[list[int]] = []
    for key in keys:
        if out and key == out[-1][-1] + 1:
            out[-1].append(key)
        else:
            out.append([key])
    return out


def expected_windows(
    tl: RawTimeline, *, nT: int, nE: int | None, stride: int, ratio: float, min_malware: int
) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """(train slot indices, eval slot indices) for every window the protocol allows."""
    windows = []
    for run in runs(usable_cells(tl, ratio, min_malware)):
        if nE is None:
            if len(run) > nT:
                windows.append((tuple(run[:nT]), tuple(run[nT:])))
            continue
        start = 0
        while start + nT + nE <= len(run):
            block = run[start : start + nT + nE]
            windows.append((tuple(block[:nT]), tuple(block[nT:])))
            start += stride
    return windows


def seconds(value: np.datetime64) -> int:
    return int(np.datetime64(value, "s").astype("int64"))


def seconds_array(values: np.ndarray) -> np.ndarray:
    return np.asarray(values).astype("datetime64[s]").astype("int64")


def positions(tl: RawTimeline, row_ids: np.ndarray) -> np.ndarray:
    """Row positions in the raw timeline for the given ids, in the given order."""
    order = np.argsort(tl.row_id)
    found = np.searchsorted(tl.row_id, row_ids, sorter=order)
    pos = order[np.clip(found, 0, len(order) - 1)]
    assert np.array_equal(tl.row_id[pos], row_ids), "a yielded row id is not in the raw timeline"
    return pos


def slot_index_of(tl: RawTimeline, start: np.datetime64, end: np.datetime64) -> int:
    """The grid index of a slot the slicer names by its bounds; asserts the bounds are exact."""
    s, e = seconds(start), seconds(end)
    assert e - s == tl.width, f"slot [{s}, {e}) is not {tl.width} s wide"
    assert (s - tl.anchor) % tl.width == 0, f"slot start {s} is off the anchored grid"
    return (s - tl.anchor) // tl.width


def assert_window_matches_oracle(window, tl: RawTimeline, *, ratio: float) -> None:
    """Every fact about one yielded window, recomputed from the raw timeline."""
    grid = cells(tl)
    train_keys = [slot_index_of(tl, r.start, r.end) for r in window.plan.train]
    eval_keys = [slot_index_of(tl, r.start, r.end) for r in window.plan.eval]
    keys = train_keys + eval_keys
    assert keys == list(range(keys[0], keys[0] + len(keys))), "a window spans a gap or skips a slot"

    # Training rows: exactly the raw rows of the training slots (no subsampling, no extras).
    want_train = np.sort(np.concatenate([tl.row_id[grid[k]["pos"]] for k in train_keys]))
    got_train = np.sort(window.train.row_id)
    assert np.array_equal(got_train, want_train), "training rows differ from the raw slots"
    newest_train = int(tl.ts[np.isin(tl.row_id, got_train)].max())

    for slot in window.eval_slots():
        k = slot_index_of(tl, slot.ref.start, slot.ref.end)
        assert k in eval_keys
        cell = grid[k]
        lo, hi = tl.bounds(k)
        pos = positions(tl, slot.row_id)
        assert (tl.ts[pos] >= lo).all() and (tl.ts[pos] < hi).all(), "row outside its slot window"
        assert (tl.ts[pos] > newest_train).all(), "evaluation row not newer than training"
        assert np.array_equal(slot.y, tl.y[pos]), "labels do not belong to the yielded rows"
        assert np.array_equal(seconds_array(slot.ts), tl.ts[pos]), "timestamps were altered"
        kept_malware = int((slot.y == 1).sum())
        kept_benign = int((slot.y == 0).sum())
        assert kept_benign == cell["n_ben"], "benign samples were dropped"
        assert kept_malware == min(int(cell["n_mal"]), target_count(int(cell["n_ben"]), ratio))
        assert kept_malware / (kept_malware + kept_benign) <= ratio + 1e-12
        assert len(set(slot.row_id.tolist())) == len(slot.row_id), "a row appears twice"
