"""Slot schemes and an in-memory table source: the slicer on any time-indexed table.

A table needs a timestamp, a 0/1 label and a unique row id per row. Optional: a feature
matrix aligned to the rows, a feature-vector hash column and a row filter. Rows are ordered
by ``(timestamp, row id)``, so the input row order never changes the output.
"""

from __future__ import annotations

from typing import Any, Protocol

import numpy as np
import pandas as pd
import scipy.sparse as sp

from driftwatch.data.slicer import SlicerError, SlotInfo, SlotRef, SlotRows

NS = "datetime64[ns]"


class SlotScheme(Protocol):
    def edges(self, lo: np.datetime64, hi: np.datetime64) -> np.ndarray:
        """Strictly increasing slot edges (ns) with ``edges[0] <= lo`` and ``edges[-1] > hi``."""
        ...

    def slot_id(self, start: np.datetime64) -> str: ...

    def describe(self) -> dict[str, Any]: ...


class FixedWidthScheme:
    """Slots ``[anchor + k*width, anchor + (k+1)*width)`` for integer k."""

    def __init__(self, anchor: np.datetime64, width: np.timedelta64, prefix: str = "w") -> None:
        self.anchor = np.datetime64(anchor, "ns")
        self.width = np.timedelta64(width, "ns")
        if self.width <= np.timedelta64(0, "ns"):
            raise ValueError("slot width must be positive")
        self.prefix = prefix

    def edges(self, lo: np.datetime64, hi: np.datetime64) -> np.ndarray:
        width = self.width.astype("int64")
        anchor = self.anchor.astype("int64")
        first = anchor + (int(lo.astype("int64")) - anchor) // width * width
        n_slots = (int(hi.astype("int64")) - first) // width + 1
        return (first + np.arange(n_slots + 1, dtype=np.int64) * width).astype(NS)

    def slot_id(self, start: np.datetime64) -> str:
        return f"{self.prefix}:{np.datetime64(start, 's')}"

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "fixed-width",
            "anchor": str(self.anchor),
            "width_s": int(self.width.astype("timedelta64[s]").astype("int64")),
        }


class CalendarMonthScheme:
    """Calendar months in UTC, ids ``month:YYYY-MM`` (the LAMDA slot ids)."""

    def edges(self, lo: np.datetime64, hi: np.datetime64) -> np.ndarray:
        first = np.datetime64(lo, "M")
        last = np.datetime64(hi, "M") + np.timedelta64(1, "M")
        return np.arange(first, last + np.timedelta64(1, "M"), dtype="datetime64[M]").astype(NS)

    def slot_id(self, start: np.datetime64) -> str:
        return f"month:{np.datetime64(start, 'M')}"

    def describe(self) -> dict[str, Any]:
        return {"kind": "calendar-month"}


class TableSource:
    """A :class:`~driftwatch.data.slicer.SlotSource` over a pandas table held in memory."""

    def __init__(
        self,
        table: pd.DataFrame,
        scheme: SlotScheme,
        *,
        ts_col: str = "ts",
        label_col: str = "label",
        id_col: str = "row_id",
        x: Any = None,
        fv_col: str | None = None,
        exclude: Any = None,
        name: str = "table",
    ) -> None:
        self.name = name
        self.scheme = scheme
        self.sparse = bool(sp.issparse(x)) if x is not None else False
        n = len(table)
        ts = pd.to_datetime(table[ts_col], utc=True).dt.tz_localize(None)
        ts = ts.to_numpy(dtype=NS)
        y = table[label_col].to_numpy()
        ids = table[id_col].to_numpy(dtype=np.int64)
        if n == 0:
            raise SlicerError("the table is empty")
        if np.isnat(ts).any():
            raise SlicerError("the table has missing timestamps")
        if not np.isin(y, (0, 1)).all():
            raise SlicerError("labels must be 0 (benign) or 1 (malware)")
        if np.unique(ids).size != n:
            raise SlicerError(f"{id_col} must be unique: row order would not be deterministic")
        if x is not None and x.shape[0] != n:
            raise SlicerError("the feature matrix has a different number of rows than the table")
        drop = np.zeros(n, dtype=bool) if exclude is None else np.asarray(exclude(table), bool)
        self._row_filter = getattr(exclude, "name", None) if exclude is not None else None

        order = np.lexsort((ids, ts.astype("int64")))
        self._order = order
        self._ts = ts[order]
        self._y = y[order].astype(np.int8)
        self._id = ids[order]
        self._drop = drop[order]
        self._x = x
        self._fv = table[fv_col].to_numpy(dtype=str)[order] if fv_col is not None else None

        edges = scheme.edges(self._ts[0], self._ts[-1])
        self._edges = edges
        bounds = np.searchsorted(self._ts, edges, side="left")
        self._slots: list[tuple[SlotRef, int, int]] = []
        for k in range(len(edges) - 1):
            ref = SlotRef(scheme.slot_id(edges[k]), edges[k], edges[k + 1], k)
            self._slots.append((ref, int(bounds[k]), int(bounds[k + 1])))
        if bounds[-1] != n:
            raise SlicerError("slot edges do not cover every row")
        self._by_id = {ref.slot_id: (ref, lo, hi) for ref, lo, hi in self._slots}
        if len(self._by_id) != len(self._slots):
            raise SlicerError("the scheme produced duplicate slot ids")
        self.excluded_rows = {
            "malware": int((self._drop & (self._y == 1)).sum()),
            "benign": int((self._drop & (self._y == 0)).sum()),
        }

    def slot_table(self) -> list[SlotInfo]:
        out = []
        for ref, lo, hi in self._slots:
            keep = ~self._drop[lo:hi]
            y = self._y[lo:hi][keep]
            n_mal = int((y == 1).sum())
            out.append(
                SlotInfo(
                    ref=ref,
                    n_rows=int(keep.sum()),
                    n_malware=n_mal,
                    n_benign=int(y.size) - n_mal,
                    n_excluded=int((~keep).sum()),
                )
            )
        return out

    def load_slot(self, slot_id: str) -> SlotRows:
        if slot_id not in self._by_id:
            raise KeyError(slot_id)
        ref, lo, hi = self._by_id[slot_id]
        keep = ~self._drop[lo:hi]
        positions = np.arange(lo, hi)[keep]
        source_rows = self._order[positions]
        return SlotRows(
            ref=ref,
            y=self._y[positions],
            ts=self._ts[positions],
            row_id=self._id[positions],
            X=None if self._x is None else self._x[source_rows],
            fv_hash=None if self._fv is None else self._fv[positions],
        )

    def provenance(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": "table",
            "n_rows": int(self._y.size),
            "scheme": self.scheme.describe(),
            "row_filter": self._row_filter,
            "excluded_rows": self.excluded_rows,
        }
