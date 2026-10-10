"""The dataset caches as slicer sources, and the ADR-0004 presets.

:class:`CachedSource` plans from ``meta.parquet`` files only (class counts, partial slots,
exclusions) and loads features for one slot at a time. Everything dataset-specific the
accepted ADR-0004 fixed lives in :data:`PRESETS`, not in the slicer:

- LAMDA: calendar-month slots over the whole span; gaps (2013-07/08, 2014-09 to 2016-01, ...)
  are grid slots with no rows.
- BODMAS: 2-week slots anchored at 2019-08-26 (Monday of ISO week 2019-W35), study window
  ending 2020-10-04. Benign rows with a date-only timestamp shared by at least 1,000 rows
  (batch placeholders such as 2020-01-01) are excluded by timestamp pattern, not by label.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from driftwatch.data.cache import load_manifest
from driftwatch.data.loaders import CachedDataset
from driftwatch.data.slicer import RowFilter, SlicerError, SlotInfo, SlotRef, SlotRows
from driftwatch.data.sources import CACHE_VERSION

PLACEHOLDER_MIN_TIES = 1000  # ADR-0004 item 5: above every regular batch day (max 599)
NS = "datetime64[ns]"


def placeholder_dates(min_ties: int = PLACEHOLDER_MIN_TIES) -> RowFilter:
    """Rows whose timestamp is a date shared by at least ``min_ties`` rows."""

    def rule(meta: pd.DataFrame) -> np.ndarray:
        date_only = meta["ts_date_only"].to_numpy(dtype=bool)
        return date_only & (meta["ts_tie_count"].to_numpy() >= min_ties)

    return RowFilter(
        name=f"placeholder-dates(date-only timestamp shared by >= {min_ties} rows)",
        fn=rule,
        columns=("ts_date_only", "ts_tie_count"),
    )


def _naive_ns(moment: datetime) -> np.datetime64:
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC).replace(tzinfo=None)
    return np.datetime64(moment, "ns")


class CachedSource:
    """A :class:`~driftwatch.data.slicer.SlotSource` over one dataset's per-unit caches."""

    def __init__(
        self,
        dataset: str,
        root: Any = "data",
        *,
        length: str,
        anchor: datetime | None = None,
        study_start: datetime | None = None,
        study_end: datetime | None = None,
        exclude: RowFilter | None = None,
    ) -> None:
        self.name = dataset
        self.data = CachedDataset(dataset, root)
        self.sparse = self.data.x_format == "csr-npz"
        self.length, self.anchor = length, anchor
        self.study_start, self.study_end = study_start, study_end
        self.exclude = exclude
        slots = self.data.slots(length, anchor)
        if study_start is not None:
            slots = [s for s in slots if s.start >= study_start]
        if study_end is not None:
            slots = [s for s in slots if s.end <= study_end]
        if not slots:
            raise SlicerError(f"{dataset} {length}: no slot lies inside the study span")
        self._slots = {s.slot_id: s for s in slots}
        self._refs = {
            s.slot_id: SlotRef(s.slot_id, _naive_ns(s.start), _naive_ns(s.end), i)
            for i, s in enumerate(slots)
        }
        self._table: list[SlotInfo] | None = None
        self._excluded = {"malware": 0, "benign": 0}
        self._manifest_hash = load_manifest(self.data.layout.manifest).get("content_hash")

    # -- planning --------------------------------------------------------------------------

    def slot_table(self) -> list[SlotInfo]:
        if self._table is None:
            self._table = [self._count(slot) for slot in self._slots.values()]
        return self._table

    def _count(self, slot: Any) -> SlotInfo:
        columns = ["label", *(self.exclude.columns if self.exclude is not None else ())]
        n_rows = n_mal = 0
        n_excluded = 0
        for unit in slot.units:
            meta = self.data.unit_meta(unit, columns)
            label = meta["label"].to_numpy()
            drop = (
                self.exclude(meta) if self.exclude is not None else np.zeros(len(meta), dtype=bool)
            )
            self._excluded["malware"] += int((drop & (label == 1)).sum())
            self._excluded["benign"] += int((drop & (label == 0)).sum())
            n_excluded += int(drop.sum())
            kept = label[~drop]
            n_rows += int(kept.size)
            n_mal += int((kept == 1).sum())
        return SlotInfo(
            ref=self._refs[slot.slot_id],
            n_rows=n_rows,
            n_malware=n_mal,
            n_benign=n_rows - n_mal,
            n_excluded=n_excluded,
            structural="partial" if slot.is_partial else "",
        )

    # -- loading ---------------------------------------------------------------------------

    def load_slot(self, slot_id: str) -> SlotRows:
        slot = self._slots[slot_id]
        data = self.data.load_slot(slot)
        meta = data.meta
        X = data.X
        if self.exclude is not None and len(meta):
            drop = self.exclude(meta)
            if drop.any():
                keep = np.flatnonzero(~drop)
                X, meta = X[keep], meta.iloc[keep].reset_index(drop=True)
        ts = pd.to_datetime(meta["ts"], utc=True).dt.tz_localize(None).to_numpy(dtype=NS)
        fv = meta["fv_hash"].to_numpy(dtype=str) if "fv_hash" in meta.columns else None
        return SlotRows(
            ref=self._refs[slot_id],
            y=meta["label"].to_numpy(dtype=np.int8),
            ts=ts,
            row_id=meta["row_id"].to_numpy(dtype=np.int64),
            X=X,
            fv_hash=fv,
        )

    def provenance(self) -> dict[str, Any]:
        self.slot_table()  # fills the exclusion counts
        return {
            "name": self.name,
            "kind": "cache",
            "length": self.length,
            "anchor": None if self.anchor is None else self.anchor.isoformat(),
            "study_start": None if self.study_start is None else self.study_start.isoformat(),
            "study_end": None if self.study_end is None else self.study_end.isoformat(),
            "row_filter": None if self.exclude is None else self.exclude.name,
            "excluded_rows": dict(self._excluded),
            "cache_version": CACHE_VERSION,
            "data_manifest_hash": self._manifest_hash,
            "x_format": self.data.x_format,
            "n_features": self.data.n_features,
        }


# --- ADR-0004 presets -----------------------------------------------------------------------


@dataclass(frozen=True)
class Preset:
    dataset: str
    length: str
    anchor: datetime | None
    study_start: datetime | None
    study_end: datetime | None
    exclude: RowFilter | None


BODMAS_ANCHOR = datetime(2019, 8, 26, tzinfo=UTC)

PRESETS: dict[str, Preset] = {
    "lamda": Preset("lamda", "month", None, None, None, None),
    "bodmas": Preset(
        "bodmas",
        "2w",
        anchor=BODMAS_ANCHOR,
        study_start=BODMAS_ANCHOR,
        study_end=datetime(2020, 10, 5, tzinfo=UTC),  # the last slot is 2020-09-21..2020-10-04
        exclude=placeholder_dates(),
    ),
}


def cached_source(dataset: str, root: Any = "data", **overrides: Any) -> CachedSource:
    """A source for ``dataset`` with the accepted preset, optionally overridden."""
    preset = dataclasses.replace(PRESETS[dataset], **overrides)
    return CachedSource(
        dataset,
        root,
        length=preset.length,
        anchor=preset.anchor,
        study_start=preset.study_start,
        study_end=preset.study_end,
        exclude=preset.exclude,
    )
