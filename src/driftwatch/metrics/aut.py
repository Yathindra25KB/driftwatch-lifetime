"""AUT, A-AUT and the rolling-window geometry of Chow et al. (arXiv 2506.23814v2).

AUT is the guide's ``AUT(f, N) = 1/(N-1) * sum_{k=1..N-1} (f_k + f_{k+1}) / 2``: numpy's
trapezoid over per-slot F1 with time rescaled to [0, 1], so 1.0 means no decay. TESSERACT
arXiv v4 says its published Eq. (4) carried an extra 1/N factor (a typo); this is the form
the results rely on (ADR-0006).

A-AUT is ``(mean, std)`` of AUT over rolling train/test windows (Eq. 1). The window geometry
of the paper, for ``n`` slots:

- ``nE >= nT`` (Eq. 2-4): training windows start every ``nT`` slots, ``k = floor((n-nE)/nT)``.
- ``nE < nT`` (appendix A-E, Eq. 6-8): they advance by ``nE``, ``k = floor((n-nT)/nE)``.

Both are ``stride = min(nT, nE)`` and ``k = floor((n-nT-nE)/stride) + 1``. The slicer takes
the stride as a parameter: ADR-0005 keeps its own strides (LAMDA 3, BODMAS 2) as the
headline, and ``chow_stride`` gives the paper's value for the secondary check.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import NamedTuple

import numpy as np


class AAut(NamedTuple):
    mean: float
    std: float  # NaN for a single window
    n_windows: int


def aut(f1_per_slot: Sequence[float]) -> float:
    """Normalised trapezoid area under per-slot F1 (needs at least two slots)."""
    f = np.asarray(f1_per_slot, dtype=np.float64)
    if f.ndim != 1 or f.size < 2:
        raise ValueError("AUT needs at least two evaluation slots")
    if not np.isfinite(f).all() or f.min() < 0.0 or f.max() > 1.0:
        raise ValueError("AUT is defined on F1 values in [0, 1]")
    return float(np.mean((f[:-1] + f[1:]) / 2.0))


def a_aut(aut_per_window: Sequence[float], ddof: int = 1) -> AAut:
    """Mean and standard deviation of AUT over windows (sample std by default)."""
    values = np.asarray(aut_per_window, dtype=np.float64)
    if values.ndim != 1 or values.size < 1:
        raise ValueError("A-AUT needs at least one window")
    if not np.isfinite(values).all():
        raise ValueError("A-AUT is defined on finite AUT values")
    std = math.nan if values.size - ddof < 1 else float(values.std(ddof=ddof))
    return AAut(float(values.mean()), std, int(values.size))


# --- window geometry --------------------------------------------------------------------------


def _check_sizes(nT: int, nE: int) -> None:
    if nT < 1 or nE < 1:
        raise ValueError("nT and nE must be at least 1")


def chow_stride(nT: int, nE: int) -> int:
    """How far the paper advances a window: ``min(nT, nE)``."""
    _check_sizes(nT, nE)
    return min(nT, nE)


def chow_window_count(n_slots: int, nT: int, nE: int) -> int:
    """Eq. (4) for ``nE >= nT`` and Eq. (8) for ``nE < nT`` (0 when no window fits)."""
    _check_sizes(nT, nE)
    if n_slots < nT + nE:
        return 0
    return (n_slots - nT - nE) // min(nT, nE) + 1


def chow_windows(n_slots: int, nT: int, nE: int) -> list[tuple[range, range]]:
    """(training slots, evaluation slots) of every window, written out as in the paper."""
    k = chow_window_count(n_slots, nT, nE)
    if nE >= nT:  # Eq. (2), (3)
        return [
            (
                range(i * nT, i * nT + nT),
                range((i + 1) * nT, (i + 1) * nT + nE),
            )
            for i in range(k)
        ]
    return [  # Eq. (6), (7)
        (
            range(i * nE, i * nE + nT),
            range(nT + i * nE, nT + (i + 1) * nE),
        )
        for i in range(k)
    ]
