"""TESSERACT constraints C1-C3 as checks that raise (Build Guide section 3; PROTOCOL section 4).

- **C1** (temporal training consistency): every training sample is strictly older than every
  evaluation sample.
- **C2** (temporal window consistency): an evaluation slot holds malware *and* benign samples,
  all from that slot's own window ``[start, end)``.
- **C3** (realistic ratio): the evaluation slot is brought to the target malware ratio by
  seeded subsampling of **malware only**. A slot already below the target keeps all its rows
  and is flagged ``below_target`` ("cap and flag", the researcher's decision of 10 Oct 2026;
  ADR-0005 records it). The achieved ratio is therefore never above the target.

Every check raises a :class:`ConstraintViolation`. None of them warns, and none can be
switched off. Never weaken a check to get green: write an ADR and ask the researcher.

The checks take plain arrays. They know nothing about datasets, slots or files, so the
slicer and later phases (the simulator re-checks C1 against the real training pool) share them.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Literal

import numpy as np
import pandas as pd

RATIO_TOLERANCE = 1e-12


class ConstraintViolation(Exception):
    """A TESSERACT constraint does not hold. Never caught and ignored."""


class C1Violation(ConstraintViolation):
    """A training sample is not strictly older than an evaluation sample."""


class C2Violation(ConstraintViolation):
    """An evaluation slot is not made of both classes from its own window."""


class C3Violation(ConstraintViolation):
    """The malware ratio was not reached by malware-only subsampling, or the ratio is invalid."""


# --- C1 -------------------------------------------------------------------------------------


def check_c1(train_ts: Any, eval_ts: Any) -> None:
    """Raise unless the newest training timestamp is strictly older than the earliest test one.

    An empty side cannot be validated and raises too. Missing timestamps raise.
    """
    train, evaluation = np.asarray(train_ts), np.asarray(eval_ts)
    if train.size == 0 or evaluation.size == 0:
        raise C1Violation(
            f"C1 cannot be validated with {train.size} training and {evaluation.size} "
            "evaluation samples"
        )
    if pd.isna(train).any() or pd.isna(evaluation).any():
        raise C1Violation("C1 cannot be validated: a timestamp is missing")
    newest_train, earliest_eval = train.max(), evaluation.min()
    if not newest_train < earliest_eval:
        raise C1Violation(
            f"C1: newest training sample {newest_train} is not strictly older than the "
            f"earliest evaluation sample {earliest_eval}"
        )


# --- C2 -------------------------------------------------------------------------------------


def check_c2(ts: Any, y: Any, start: Any, end: Any) -> None:
    """Raise unless every row lies in ``[start, end)`` and both classes are present."""
    ts, y = np.asarray(ts), np.asarray(y)
    if ts.ndim != 1 or ts.shape != y.shape:
        raise C2Violation(f"C2: timestamps {ts.shape} and labels {y.shape} do not line up")
    if not start < end:
        raise C2Violation(f"C2: empty window [{start}, {end})")
    if ts.size == 0:
        raise C2Violation("C2: the evaluation slot is empty")
    if pd.isna(ts).any():
        raise C2Violation("C2 cannot be validated: a timestamp is missing")
    outside = int(((ts < start) | (ts >= end)).sum())
    if outside:
        raise C2Violation(
            f"C2: {outside} of {ts.size} samples lie outside the slot window [{start}, {end})"
        )
    n_malware, n_benign = int((y == 1).sum()), int((y == 0).sum())
    if n_malware + n_benign != y.size:
        raise C2Violation("C2: labels must be 0 (benign) or 1 (malware)")
    if n_malware == 0 or n_benign == 0:
        raise C2Violation(
            f"C2: the slot needs both classes from its window ({n_malware} malware, "
            f"{n_benign} benign)"
        )


# --- C3 -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class C3Result:
    """Counts before and after subsampling, as logged per slot in the manifest."""

    target_ratio: float
    n_target_malware: int
    n_malware_before: int
    n_benign_before: int
    n_malware_after: int
    n_benign_after: int
    achieved_ratio: float
    share_malware_discarded: float
    status: Literal["at_target", "below_target"]

    def as_record(self) -> dict[str, Any]:
        return asdict(self)


def _exact_ratio(ratio: float) -> Fraction:
    if not 0.0 < float(ratio) < 1.0:
        raise C3Violation(f"C3: the target malware ratio must lie in (0, 1), got {ratio!r}")
    return Fraction(str(float(ratio)))  # str(0.1) == "0.1": exact decimal, no float noise


def target_malware_count(n_benign: int, ratio: float) -> int:
    """Largest malware count whose share of the slot does not exceed ``ratio``.

    ``floor(n_benign * r / (1 - r))``, in exact arithmetic: 900 benign at 10% give 100.
    """
    r = _exact_ratio(ratio)
    return math.floor(Fraction(int(n_benign)) * r / (1 - r))


def _binary_labels(y: Any) -> np.ndarray:
    y = np.asarray(y)
    if y.ndim != 1 or not np.isin(y, (0, 1)).all():
        raise C3Violation("C3: labels must be a 1-D array of 0 (benign) and 1 (malware)")
    return y.astype(np.int8, copy=False)


def subsample_malware(y: Any, ratio: float, seed: int, slot_id: str) -> np.ndarray:
    """Row indices to keep: every benign row plus a seeded draw of malware (sorted).

    The generator depends only on ``(seed, slot_id)``, so a slot's draw is identical across
    windows, runs and grid cells, whatever else was sliced before it. The draw is the head of
    one seeded permutation, so a lower ratio selects a subset of a higher ratio's malware
    (the sensitivity check is nested in the headline ratio). A slot already at or below the
    target keeps every row.
    """
    y = _binary_labels(y)
    if seed < 0:
        raise C3Violation("C3: the seed must be non-negative")
    n_benign = int((y == 0).sum())
    if n_benign == 0:
        raise C3Violation("C3: a slot without benign samples has no malware ratio to reach")
    target = target_malware_count(n_benign, ratio)
    malware = np.flatnonzero(y == 1)
    if malware.size <= target:
        return np.arange(y.size)
    entropy = [int(seed), zlib.crc32(slot_id.encode("utf-8"))]
    order = np.random.default_rng(np.random.SeedSequence(entropy)).permutation(malware.size)
    kept = np.concatenate([np.flatnonzero(y == 0), malware[order[:target]]])
    kept.sort()
    return kept


def check_c3(y: Any, kept: Any, ratio: float) -> C3Result:
    """Raise unless ``kept`` is exactly what malware-only subsampling to ``ratio`` leaves.

    Raises when a benign row was dropped, ``kept`` is not a set of valid distinct indices,
    the ratio ends above target, a reachable slot misses its target count, or malware was
    dropped from a slot that was already below target.
    """
    y = _binary_labels(y)
    kept = np.asarray(kept)
    if kept.ndim != 1 or (kept.size and kept.dtype.kind not in "iu"):
        raise C3Violation("C3: kept must be a 1-D array of row indices")
    if kept.size and (kept.min() < 0 or kept.max() >= y.size):
        raise C3Violation("C3: kept holds an index outside the slot")
    if np.unique(kept).size != kept.size:
        raise C3Violation("C3: kept holds a row more than once")
    n_benign = int((y == 0).sum())
    n_malware = int((y == 1).sum())
    if n_benign == 0:
        raise C3Violation("C3: a slot without benign samples has no malware ratio to reach")
    target = target_malware_count(n_benign, ratio)
    after = y[kept]
    n_malware_after, n_benign_after = int((after == 1).sum()), int((after == 0).sum())
    if n_benign_after != n_benign:
        raise C3Violation(
            f"C3: only malware may be dropped, but {n_benign - n_benign_after} of "
            f"{n_benign} benign samples are gone"
        )
    reachable = n_malware >= target
    expected = target if reachable else n_malware
    if n_malware_after != expected:
        raise C3Violation(
            f"C3: expected {expected} malware samples to remain "
            f"({'target reached' if reachable else 'slot below target, keep all'}), "
            f"found {n_malware_after} of {n_malware}"
        )
    achieved = n_malware_after / (n_malware_after + n_benign_after)
    if achieved > float(ratio) + RATIO_TOLERANCE:
        raise C3Violation(f"C3: achieved ratio {achieved:.6f} exceeds the target {ratio}")
    discarded = 1.0 - n_malware_after / n_malware if n_malware else 0.0
    return C3Result(
        target_ratio=float(ratio),
        n_target_malware=target,
        n_malware_before=n_malware,
        n_benign_before=n_benign,
        n_malware_after=n_malware_after,
        n_benign_after=n_benign_after,
        achieved_ratio=achieved,
        share_malware_discarded=discarded,
        status="at_target" if reachable else "below_target",
    )
