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
    origin: np.ndarray | None = None  # per handle: ORIGIN_RANDOM or ORIGIN_SELECTED (E3)


ORIGIN_RANDOM = "random_slice"  # the reserved random slice: the only calibration data
ORIGIN_SELECTED = "selected"  # chosen by the selector: never calibration data
_RESERVE_TAG = 0x52455356  # separates the reserved-slice draw from the selector's draw


class Selector(Protocol):
    name: str

    def select(
        self,
        public: OpaqueSlot,
        n: int,
        rng: np.random.Generator,
        scores: np.ndarray | None = None,
        exclude: np.ndarray | None = None,
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


def reserved_rng(seed: int, slot_id: str) -> np.random.Generator:
    """The reserved-slice draw depends on ``(seed, slot id)`` only, never on scores."""
    entropy = [seed, zlib.crc32(slot_id.encode("utf-8")), _RESERVE_TAG]
    return np.random.default_rng(np.random.SeedSequence(entropy))


def _eligible(n_rows: int, exclude: np.ndarray | None) -> np.ndarray:
    if exclude is None:
        return np.ones(n_rows, dtype=bool)
    e = np.asarray(exclude, dtype=bool)
    if e.shape != (n_rows,):
        raise ValueError("exclude must have one entry per public row")
    return ~e


class RandomSelector:
    """Uniform selection without replacement."""

    name = "random"

    def select(
        self,
        public: OpaqueSlot,
        n: int,
        rng: np.random.Generator,
        scores: np.ndarray | None = None,
        exclude: np.ndarray | None = None,
    ) -> Selection:
        del scores  # random selection is score-blind
        if n < 0:
            raise ValueError(f"n must be non-negative, got {n}")
        order = rng.permutation(len(public.handle))
        ok = _eligible(len(public.handle), exclude)
        order = order[ok[order]]
        return Selection(public.slot_id, public.handle[order[: min(n, len(order))]])


class _ScoreSelector:
    """Take the ``n`` eligible rows with the lowest priority value; ties by a seeded shuffle."""

    name = "score"
    needs = "scores"

    def _priority(self, scores: np.ndarray) -> np.ndarray:  # lower = chosen first
        raise NotImplementedError

    def select(
        self,
        public: OpaqueSlot,
        n: int,
        rng: np.random.Generator,
        scores: np.ndarray | None = None,
        exclude: np.ndarray | None = None,
    ) -> Selection:
        if n < 0:
            raise ValueError(f"n must be non-negative, got {n}")
        if scores is None:
            raise ValueError(f"selector {self.name!r} needs {self.needs}")
        s = np.asarray(scores, dtype=np.float64)
        if s.shape != (len(public.handle),) or not np.isfinite(s).all():
            raise ValueError("scores must be finite and have one entry per public row")
        prio = self._priority(s)
        ok = _eligible(len(public.handle), exclude)
        shuffle = rng.permutation(len(public.handle))  # tie-break: seeded, label-free
        cand = shuffle[ok[shuffle]]
        order = cand[np.argsort(prio[cand], kind="stable")]
        return Selection(public.slot_id, public.handle[order[: min(n, len(order))]])


class UncertaintySelector(_ScoreSelector):
    """The rows whose P(malware) is closest to 0.5."""

    name = "uncertainty"
    needs = "the model's P(malware) per row"

    def _priority(self, scores: np.ndarray) -> np.ndarray:
        return np.abs(scores - 0.5)


class CredibilitySelector(_ScoreSelector):
    """The rows with the lowest conformal p-value of their predicted class."""

    name = "credibility"
    needs = "the credibility per row"

    def _priority(self, scores: np.ndarray) -> np.ndarray:
        return scores


def select_with_reserved_slice(
    selector: Selector,
    public: OpaqueSlot,
    n_budget: int,
    n_calibration: int,
    seed: int,
    rng: np.random.Generator,
    scores: np.ndarray | None = None,
) -> Selection:
    """Spend ``n_budget`` labels: a random reserved slice first, the selector gets the rest.

    The reserved rows are a uniform draw that depends on ``(seed, slot id)`` only, so they are
    the same for every selector and every score; they are the only rows tagged as calibration
    data. The rest is chosen by ``selector`` from the other rows. The total is exactly
    ``min(n_budget, rows)``, so every arm spends the same number of labels.
    """
    n_rows = len(public.handle)
    n_budget = min(int(n_budget), n_rows)
    n_cal = min(max(int(n_calibration), 0), n_budget)
    order = reserved_rng(seed, public.slot_id).permutation(n_rows)
    reserved = order[:n_cal]
    exclude = np.zeros(n_rows, dtype=bool)
    exclude[reserved] = True
    chosen = selector.select(public, n_budget - n_cal, rng, scores, exclude)
    handles = np.concatenate([public.handle[reserved], chosen.handles])
    origin = np.array(
        [ORIGIN_RANDOM] * n_cal + [ORIGIN_SELECTED] * len(chosen.handles), dtype=object
    )
    if len(handles) != n_budget or len(np.unique(handles)) != len(handles):
        raise ValueError(
            "the reserved slice and the selection must be disjoint and fill the budget"
        )
    return Selection(public.slot_id, handles, origin)


def make_selector(name: str) -> Selector:
    if name == "random":
        return RandomSelector()
    if name == "uncertainty":
        return UncertaintySelector()
    if name == "credibility":
        return CredibilitySelector()
    raise ValueError(f"unknown selector {name!r}")
