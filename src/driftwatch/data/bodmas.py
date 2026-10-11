"""BODMAS: stream the 134,435 x 2,381 float32 matrix into one dense cache per ISO week.

``bodmas.npz`` stores ``X.npy`` deflate-compressed inside a zip. Rows are read straight
from the decompressing stream ``batch_size`` at a time, so the 1.28 GB matrix is never in
memory at once. ``bodmas_metadata.csv`` is aligned row for row with X and sorted by
timestamp, so each ISO week is a contiguous run of rows. Values are stored as published
(float32, unnormalised): scaling is a training-window concern for later phases.
"""

from __future__ import annotations

import logging
import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa

from driftwatch.data.cache import (
    Layout,
    dense_row_hashes,
    file_record,
    save_dense,
    save_table,
    unit_files_match,
)
from driftwatch.data.slots import unit_end, unit_start
from driftwatch.data.sources import BODMAS

log = logging.getLogger(__name__)

SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAVE_EVERY_WEEKS = 8

META_SCHEMA = pa.schema(
    [
        ("row_id", pa.int64()),
        ("sha256", pa.string()),
        ("ts", pa.timestamp("s", tz="UTC")),
        ("label", pa.int8()),
        ("family", pa.string()),
        ("category", pa.string()),
        ("ts_naive", pa.bool_()),  # published without a UTC offset; read as UTC
        ("ts_date_only", pa.bool_()),  # exactly 00:00:00: a date, not a time
        ("ts_tie_count", pa.int32()),  # rows in the whole file sharing this exact ts
        ("fv_hash", pa.string()),
    ]
)


@dataclass
class BodmasStats:
    rows: int = 0
    nan: int = 0
    inf: int = 0
    nonzero: int = 0
    label_family_conflicts: int = 0  # y == 1 without family, or y == 0 with one
    malware_without_category: int = 0
    bad_sha256: int = 0
    ts_unsorted: int = 0
    ts_with_time_of_day: int = 0
    ts_without_offset: int = 0
    ts_without_offset_malware_family: int = 0
    weeks_skipped: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _npy_stream(path: Path, member: str):
    zf = zipfile.ZipFile(path)
    fh = zf.open(member)
    version = np.lib.format.read_magic(fh)
    reader = (
        np.lib.format.read_array_header_1_0
        if version == (1, 0)
        else np.lib.format.read_array_header_2_0
    )
    shape, fortran, dtype = reader(fh)
    if fortran:
        raise ValueError(f"{member} is Fortran-ordered; rows cannot be streamed")
    return zf, fh, shape, np.dtype(dtype)


def read_metadata(raw_dir: Path, stats: BodmasStats) -> pd.DataFrame:
    meta = pd.read_csv(raw_dir / BODMAS.metadata_file, dtype={"sha": str, "family": str})
    if list(meta.columns) != ["sha", "timestamp", "family"]:
        raise ValueError(f"unexpected metadata columns {list(meta.columns)}")
    meta["sha256"] = meta.pop("sha").str.strip().str.lower()
    stats.bad_sha256 = int((~meta["sha256"].str.match(SHA256.pattern)).sum())
    raw_ts = meta.pop("timestamp").astype(str)
    # Most rows end in "+00:00"; a minority carry no offset. Those are read as UTC (an
    # assumption, counted here and listed as an open question in the inventory notes).
    naive = ~raw_ts.str.contains(r"(?:[+-]\d{2}:\d{2}|Z)$", regex=True)
    stats.ts_without_offset = int(naive.sum())
    stats.ts_without_offset_malware_family = int((naive & meta["family"].notna()).sum())
    meta["ts"] = pd.to_datetime(raw_ts, format="ISO8601", utc=True)
    meta["ts_naive"] = naive.to_numpy()
    meta["ts_date_only"] = (meta["ts"] == meta["ts"].dt.normalize()).to_numpy()
    meta["ts_tie_count"] = meta.groupby("ts")["ts"].transform("size").astype("int32")
    if meta["ts"].isna().any():
        raise ValueError("unparseable BODMAS timestamps")
    stats.ts_unsorted = int((meta["ts"].diff().dt.total_seconds() < 0).sum())
    stats.ts_with_time_of_day = int((meta["ts"] != meta["ts"].dt.normalize()).sum())
    meta["family"] = meta["family"].where(meta["family"].notna() & (meta["family"] != ""))
    category_path = raw_dir / "bodmas_malware_category.csv"
    if category_path.exists():
        cats = pd.read_csv(category_path, dtype=str)
        cats["sha256"] = cats["sha256"].str.strip().str.lower()
        meta = meta.merge(cats.drop_duplicates("sha256"), on="sha256", how="left")
    else:
        meta["category"] = None
    meta["row_id"] = np.arange(len(meta), dtype=np.int64)
    iso = meta["ts"].dt.isocalendar()
    meta["unit"] = [f"{y:04d}-W{w:02d}" for y, w in zip(iso["year"], iso["week"], strict=True)]
    return meta


def _write_week(
    layout: Layout, week: str, X: np.ndarray, meta: pd.DataFrame, fingerprint: str
) -> dict[str, Any]:
    order = meta.sort_values(["ts", "sha256", "row_id"], kind="stable").index.to_numpy()
    meta = meta.iloc[order].reset_index(drop=True)
    X = X[order]
    table = pa.Table.from_pandas(meta[META_SCHEMA.names], schema=META_SCHEMA, preserve_index=False)
    unit_dir = layout.unit_dir("bodmas", week)
    save_dense(unit_dir / "X.npy", X)
    save_table(unit_dir / "meta.parquet", table)
    files = {layout.rel(unit_dir / n): file_record(unit_dir / n) for n in ("X.npy", "meta.parquet")}
    return {
        "n_rows": int(X.shape[0]),
        "n_malware": int((meta["label"] == 1).sum()),
        "nonzero": int(np.count_nonzero(X)),
        "start": unit_start(week).isoformat(),
        "end": unit_end(week).isoformat(),
        "builder": fingerprint,
        "files": files,
    }


def build(
    layout: Layout, raw_dir: Path, cache: dict[str, Any], batch_size: int, fingerprint: str
) -> Iterator[dict[str, Any]]:
    """Build (or resume) the weekly caches, updating ``cache`` in place."""
    stats = BodmasStats()
    meta = read_metadata(raw_dir, stats)
    if stats.ts_unsorted:
        raise ValueError(f"metadata not sorted by time ({stats.ts_unsorted} inversions)")
    with zipfile.ZipFile(raw_dir / BODMAS.features_file) as zf:
        y = np.load(zf.open("y.npy"), allow_pickle=False)
    zf, fh, shape, dtype = _npy_stream(raw_dir / BODMAS.features_file, "X.npy")
    if shape[0] != len(meta) or shape[0] != len(y):
        raise ValueError(f"X {shape}, y {y.shape}, metadata {len(meta)} rows do not align")
    if dtype != np.float32:
        raise ValueError(f"expected float32 features, found {dtype}")
    meta["label"] = y.astype(np.int8)
    has_family = meta["family"].notna()
    stats.label_family_conflicts = int(((meta["label"] == 1) != has_family).sum())
    stats.malware_without_category = int(((meta["label"] == 1) & meta["category"].isna()).sum())
    cache.setdefault("units", {})
    cache.update(
        {
            "base_unit": "week",
            "n_features": int(shape[1]),
            "feature_dtype": "float32",
            "x_format": "dense-npy",
            "timestamp": "metadata `timestamp` (first appearance, per the BODMAS page), UTC",
        }
    )
    bounds = np.flatnonzero(meta["unit"].to_numpy()[1:] != meta["unit"].to_numpy()[:-1]) + 1
    starts = np.concatenate([[0], bounds])
    ends = np.concatenate([bounds, [len(meta)]])
    row_bytes = shape[1] * dtype.itemsize
    buf = np.empty((0, shape[1]), dtype=dtype)  # rows [buf_start, buf_start + len(buf))
    buf_start = 0
    written = 0
    try:
        for lo, hi in zip(starts, ends, strict=True):
            week = meta["unit"].iat[lo]
            assert lo == buf_start, "weeks are contiguous and processed in order"
            while buf_start + buf.shape[0] < hi:  # read just enough rows for this week
                want = min(batch_size, shape[0] - buf_start - buf.shape[0])
                raw = fh.read(want * row_bytes)
                if len(raw) != want * row_bytes:
                    raise ValueError("X.npy ended early")
                chunk = np.frombuffer(raw, dtype=dtype).reshape(want, shape[1])
                buf = np.concatenate([buf, chunk])
            X = buf[: hi - lo].copy()
            buf = buf[hi - lo :]
            buf_start = hi
            stats.rows += X.shape[0]
            stats.nan += int(np.isnan(X).sum())
            stats.inf += int(np.isinf(X).sum())
            stats.nonzero += int(np.count_nonzero(X))
            existing = cache["units"].get(week)
            if (
                existing
                and existing.get("builder") == fingerprint
                and existing["n_rows"] == X.shape[0]
                and unit_files_match(layout, existing)
            ):
                stats.weeks_skipped += 1
                continue
            wmeta = meta.iloc[lo:hi].reset_index(drop=True)
            wmeta["fv_hash"] = dense_row_hashes(X)
            cache["units"][week] = _write_week(layout, week, X, wmeta, fingerprint)
            written += 1
            if written % SAVE_EVERY_WEEKS == 0:
                cache["stats"] = stats.as_dict()
                yield cache
    finally:
        fh.close()
        zf.close()
    if stats.rows != shape[0]:
        raise AssertionError(f"streamed {stats.rows} of {shape[0]} rows")
    stats.extra["n_weeks"] = len(starts)
    cache["expected_units"] = sorted(set(meta["unit"]))
    cache["stats"] = stats.as_dict()
    yield cache
