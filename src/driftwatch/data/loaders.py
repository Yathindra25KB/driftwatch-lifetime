"""One loader interface for every dataset: (dataset, slot) -> features, labels, metadata.

Slots are read from the per-unit caches that ``driftwatch data build`` writes. Only the
requested slot is ever held in memory. :func:`iter_slots` streams a whole scheme one slot
at a time. Row order is deterministic: units are taken in time order, and rows inside a unit
are sorted by (timestamp, sha256).

Labels are returned because later phases need them for queue release and scoring. Policies,
selectors and monitors must never read them directly (CLAUDE.md hard rule 4).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import scipy.sparse as sp

from driftwatch.data.cache import Layout, load_manifest
from driftwatch.data.slots import Slot, build_slots, slot_by_id, unit_start

X_FILES = {"csr-npz": "X.npz", "dense-npy": "X.npy"}


@dataclass(frozen=True)
class SlotData:
    dataset: str
    slot: Slot
    X: sp.csr_matrix | np.ndarray
    y: np.ndarray
    meta: pd.DataFrame

    def __len__(self) -> int:
        return int(self.y.shape[0])


class CachedDataset:
    """Read access to one dataset's caches, driven by data/manifest.json."""

    def __init__(self, dataset: str, root: Path | str = "data") -> None:
        self.dataset = dataset
        self.layout = Layout(Path(root))
        manifest = load_manifest(self.layout.manifest)
        try:
            self._cache: dict[str, Any] = manifest["datasets"][dataset]["cache"]
        except KeyError as exc:
            raise FileNotFoundError(
                f"{dataset} is not in {self.layout.manifest}; run `driftwatch data build`"
            ) from exc
        self.x_format: str = self._cache["x_format"]
        self.n_features: int = int(self._cache["n_features"])

    @property
    def units(self) -> list[str]:
        return sorted(self._cache["units"], key=unit_start)

    def slots(self, length: str) -> list[Slot]:
        return build_slots(self.dataset, length, self.units)

    def _unit_x(self, unit: str, mmap: bool) -> sp.csr_matrix | np.ndarray:
        path = self.layout.unit_dir(self.dataset, unit) / X_FILES[self.x_format]
        if self.x_format == "csr-npz":
            return sp.load_npz(path).tocsr()
        return np.load(path, mmap_mode="r" if mmap else None, allow_pickle=False)

    def _unit_meta(self, unit: str) -> pd.DataFrame:
        return pq.read_table(self.layout.unit_dir(self.dataset, unit) / "meta.parquet").to_pandas()

    def load_unit(self, unit: str, mmap: bool = False) -> tuple[Any, pd.DataFrame]:
        x, meta = self._unit_x(unit, mmap), self._unit_meta(unit)
        if x.shape[0] != len(meta):
            raise ValueError(f"{self.dataset} {unit}: X has {x.shape[0]} rows, meta {len(meta)}")
        return x, meta

    def load_slot(self, slot: Slot | str, length: str | None = None) -> SlotData:
        if isinstance(slot, str):
            if length is None:
                length = slot.split(":", 1)[0]
            slot = slot_by_id(self.dataset, length, self.units, slot)
        parts = [self.load_unit(u) for u in slot.units]
        if parts:
            xs, metas = zip(*parts, strict=True)
            if self.x_format == "csr-npz":
                X: Any = sp.vstack(xs, format="csr")
            else:
                X = np.concatenate(xs, axis=0)
            meta = pd.concat(metas, ignore_index=True)
        else:
            X = self._empty_x()
            meta = self._unit_meta_empty()
        y = meta["label"].to_numpy(dtype=np.int8)
        return SlotData(self.dataset, slot, X, y, meta)

    def _empty_x(self) -> sp.csr_matrix | np.ndarray:
        if self.x_format == "csr-npz":
            return sp.csr_matrix((0, self.n_features), dtype=np.int8)
        return np.zeros((0, self.n_features), dtype=np.float32)

    def _unit_meta_empty(self) -> pd.DataFrame:
        first = self.units[0]
        return self._unit_meta(first).iloc[0:0].reset_index(drop=True)

    def iter_slots(self, length: str, include_gaps: bool = False) -> Iterator[SlotData]:
        for slot in self.slots(length):
            if slot.is_gap and not include_gaps:
                continue
            yield self.load_slot(slot)


def load_slot(dataset: str, slot_id: str, root: Path | str = "data") -> SlotData:
    """Load one slot, e.g. ``load_slot("lamda", "quarter:2013Q1")``."""
    return CachedDataset(dataset, root).load_slot(slot_id)


def iter_slots(
    dataset: str, length: str, root: Path | str = "data", include_gaps: bool = False
) -> Iterator[SlotData]:
    """Stream every slot of a scheme in time order, one slot in memory at a time."""
    yield from CachedDataset(dataset, root).iter_slots(length, include_gaps=include_gaps)
