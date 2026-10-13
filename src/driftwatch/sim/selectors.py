"""Label selectors: which rows of an evaluated slot the analyst budget is spent on.

A selector sees an :class:`~driftwatch.data.slicer.OpaqueSlot` (features and slot-local
handles) and nothing else. It never sees a label, a timestamp or a row id (hard rule 4), and
it cannot reach the queue. It returns a :class:`Selection`; the queue resolves the handles
and releases the true labels after the delay.

Phase 8 plugs uncertainty and credibility selectors into the same ``select`` call through the
optional ``scores`` argument (one value per row, in the public handle order). Random
selection ignores it.

Budget (ADR-0007, decision D3): a percentage of the evaluated slot **after C3
subsampling**, because that is the slot the selector sees. The absolute count is what the
runner logs next to the percentage.
"""

from __future__ import annotations

import math
import zlib
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from driftwatch.data.slicer import OpaqueSlot

_SELECT_TAG = 0x53454C54  # separates selector draws from every other seeded draw


@dataclass(frozen=True, eq=False)
class Selection:
    """Handles chosen from one slot's public view, tagged with that slot's id.

    The id lets the queue refuse handles that were made against another slot.
    """

    slot_id: str
    handles: np.ndarray


class Selector(Protocol):
    name: str

    def select(
        self,
        public: OpaqueSlot,
        n: int,
        rng: np.random.Generator,
        scores: np.ndarray | None = None,
    ) -> Selection: ...


def _half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def budget_count(n_slot: int, pct: float) -> int:
    """Rows to query: ``pct`` percent of the evaluated slot, rounded half up, at most the slot."""
    if n_slot < 0:
        raise ValueError(f"slot size must be non-negative, got {n_slot}")
    if not (isinstance(pct, int | float) and 0 <= pct <= 100) or math.isnan(pct):
        raise ValueError(f"budget must be a percentage in [0, 100], got {pct!r}")
    return min(n_slot, _half_up(pct / 100.0 * n_slot))


def calibration_count(n_budget: int, fraction: float) -> int:
    """The share of one slot's budget reserved as a random calibration slice (default 0.20)."""
    if n_budget < 0:
        raise ValueError(f"budget must be non-negative, got {n_budget}")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError(f"calibration fraction must be in [0, 1], got {fraction!r}")
    return min(n_budget, _half_up(fraction * n_budget))


def selector_rng(seed: int, slot_id: str) -> np.random.Generator:
    """The draw depends on ``(seed, slot id)`` only, so a smaller budget is a prefix of a larger."""
    entropy = [seed, zlib.crc32(slot_id.encode("utf-8")), _SELECT_TAG]
    return np.random.default_rng(np.random.SeedSequence(entropy))


class RandomSelector:
    """Uniform selection without replacement."""

    name = "random"

    def select(
        self,
        public: OpaqueSlot,
        n: int,
        rng: np.random.Generator,
        scores: np.ndarray | None = None,
    ) -> Selection:
        del scores  # random selection is score-blind
        if n < 0:
            raise ValueError(f"n must be non-negative, got {n}")
        order = rng.permutation(len(public.handle))
        return Selection(public.slot_id, public.handle[order[: min(n, len(order))]])


def make_selector(name: str) -> Selector:
    if name == "random":
        return RandomSelector()
    if name in {"uncertainty", "credibility"}:
        raise ValueError(f"selector {name!r} needs the conformal layer (Phase 8)")
    raise ValueError(f"unknown selector {name!r}")
