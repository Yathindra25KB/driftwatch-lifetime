"""Small synthetic timelines for slicer tests (integer-second timestamps, seeded)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.sparse as sp
from slicer_oracle import RawTimeline

DAY = 86400


def build_timeline(
    per_slot: dict[int, tuple[int, int]],
    *,
    width: int = DAY,
    anchor: int = 0,
    seed: int = 0,
    pin_boundaries: bool = True,
) -> RawTimeline:
    """Rows for slot ``k`` -> (n_malware, n_benign), spread uniformly inside the slot.

    With ``pin_boundaries`` the first row of every populated slot sits exactly on the slot's
    start second, so a boundary off-by-one cannot hide.
    """
    rng = np.random.default_rng(seed)
    ts: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    for k in sorted(per_slot):
        n_mal, n_ben = per_slot[k]
        n = n_mal + n_ben
        if n == 0:
            continue
        lo = anchor + k * width
        stamps = rng.integers(lo, lo + width, size=n)
        if pin_boundaries:
            stamps[0] = lo
            if n > 1:
                stamps[-1] = lo + width - 1  # the last second still belongs to the slot
        y = np.array([1] * n_mal + [0] * n_ben, dtype=np.int8)
        rng.shuffle(y)
        ts.append(stamps)
        labels.append(y)
    all_ts = np.concatenate(ts).astype(np.int64)
    all_y = np.concatenate(labels)
    order = rng.permutation(len(all_ts))  # the table is not handed over in time order
    return RawTimeline(
        ts=all_ts[order],
        y=all_y[order],
        row_id=np.arange(len(all_ts), dtype=np.int64),
        anchor=anchor,
        width=width,
    )


def to_table(tl: RawTimeline) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.to_datetime(tl.ts, unit="s").astype("datetime64[ns]"),
            "label": tl.y,
            "row_id": tl.row_id,
        }
    )


def feature_matrix(tl: RawTimeline, n_features: int = 5, sparse: bool = False):
    """Features that carry the row id, so tests can check X follows the rows they claim."""
    x = np.zeros((len(tl.row_id), n_features), dtype=np.float32)
    x[:, 0] = tl.row_id + 1
    x[:, 1] = tl.y
    return sp.csr_matrix(x) if sparse else x
