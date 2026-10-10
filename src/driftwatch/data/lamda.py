"""LAMDA: stream the per-year parquet files into one sparse cache per month.

The full matrix is never materialised densely. Each parquet batch (``batch_size`` rows,
4,561 int8 columns) becomes a small dense block, then CSR. Rows are routed to their month
by ``year_month``. The provided 80/20 split is ignored: train and test rows of a year are
pooled, and ``src_split`` records the origin for traceability only.

Work is grouped into *chunks*: sets of source files that share a month (normally one
year's train and test file). A chunk's months are written together, so a month never
receives rows from two chunks. A chunk is also the unit of resume.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import scipy.sparse as sp

from driftwatch.data.cache import Layout, file_record, save_csr, save_table, unit_files_match
from driftwatch.data.slots import month_key, unit_end, unit_start
from driftwatch.data.sources import LAMDA

log = logging.getLogger(__name__)

YEAR_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
ROW_ID_STRIDE = 10_000_000  # row_id = file_index * stride + row offset in that file

META_SCHEMA = pa.schema(
    [
        ("row_id", pa.int64()),
        ("sha256", pa.string()),
        ("ts", pa.timestamp("s", tz="UTC")),
        ("added", pa.timestamp("s", tz="UTC")),
        ("year_month", pa.string()),
        ("label", pa.int8()),
        ("family", pa.string()),
        ("vt_count", pa.int16()),
        ("src_file", pa.string()),
        ("src_split", pa.string()),
        ("fv_hash", pa.string()),
    ]
)


@dataclass(frozen=True)
class SourceFile:
    index: int
    year: int
    split: str
    path: Path
    rel: str  # path relative to the snapshot root


def source_files(snapshot: Path) -> list[SourceFile]:
    files = []
    for year_dir in sorted((snapshot / LAMDA.subset).glob("[0-9][0-9][0-9][0-9]")):
        for split in LAMDA.splits:
            path = year_dir / f"{year_dir.name}_{split}.parquet"
            if path.exists():
                rel = path.relative_to(snapshot).as_posix()
                files.append(SourceFile(len(files), int(year_dir.name), split, path, rel))
    if not files:
        raise FileNotFoundError(f"no {LAMDA.subset}/<year>/*.parquet under {snapshot}")
    return files


def parse_month(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    m = YEAR_MONTH.match(value.strip())
    if not m or not 1 <= int(m.group(2)) <= 12:
        return None
    return month_key(int(m.group(1)), int(m.group(2)))


def feature_names(schema: pa.Schema) -> list[str]:
    names = [n for n in schema.names if n.startswith(LAMDA.feature_prefix)]
    expected = [f"{LAMDA.feature_prefix}{i}" for i in range(len(names))]
    if names != expected:
        raise ValueError("feature columns are not feat_0..feat_N-1 in order")
    for col in LAMDA.meta_columns:
        if col not in schema.names:
            raise ValueError(f"missing metadata column {col!r}")
    return names


# --- pre-scan: months per file, chunks ------------------------------------------------------


def prescan(files: list[SourceFile]) -> dict[int, Counter[str | None]]:
    """Months present in each file (reads only the year_month column)."""
    months: dict[int, Counter[str | None]] = {}
    for f in files:
        col = pq.read_table(f.path, columns=["year_month"]).column(0).to_pylist()
        months[f.index] = Counter(parse_month(v) for v in col)
    return months


def chunks(files: list[SourceFile], months: dict[int, Counter]) -> list[list[SourceFile]]:
    """Group files that share any month (union-find), ordered by their earliest month."""
    parent = {f.index: f.index for f in files}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[str, int] = {}
    for f in files:
        for m in months[f.index]:
            if m is None:
                continue
            if m in owner:
                parent[find(f.index)] = find(owner[m])
            else:
                owner[m] = f.index
    groups: dict[int, list[SourceFile]] = defaultdict(list)
    for f in files:
        groups[find(f.index)].append(f)

    def first_month(group: list[SourceFile]) -> str:
        ms = [m for f in group for m in months[f.index] if m is not None]
        return min(ms) if ms else f"{group[0].year:04d}-99"

    return sorted(groups.values(), key=first_month)


def chunk_id(group: list[SourceFile]) -> str:
    return "+".join(sorted({str(f.year) for f in group}))


# --- streaming --------------------------------------------------------------------------------


@dataclass
class ChunkStats:
    rows_read: int = 0
    excluded: Counter[str] = field(default_factory=Counter)
    nnz: int = 0
    max_value: int = 0
    feature_nulls: int = 0
    family_null_malware: int = 0
    family_null_benign: int = 0
    vt_null: int = 0
    vt_non_integral: int = 0
    vt_label_conflicts: int = 0  # benign with vt > 0 or malware with vt < 4
    folder_year_mismatch: int = 0
    # Joins against the root metadata.csv (AndroZoo `added` datetime and label fields).
    meta_missing: int = 0
    added_null: int = 0
    added_month_mismatch: int = 0
    meta_label_conflicts: int = 0
    meta_vt_conflicts: int = 0
    meta_family_conflicts: int = 0

    def as_dict(self) -> dict[str, Any]:
        out = dict(self.__dict__)
        out["excluded"] = dict(self.excluded)
        return out


@dataclass(frozen=True)
class AddedIndex:
    """metadata.csv sorted by sha256: the `added` datetime and labels for each app."""

    sha: np.ndarray  # S64, sorted
    added: np.ndarray  # int64 epoch seconds; -1 when missing or unparseable
    label: np.ndarray  # float64 (NaN when missing)
    vt: np.ndarray  # float64 (NaN when missing)
    family: np.ndarray  # object (str or None)
    duplicates: int

    def lookup(self, sha: list[str]) -> tuple[np.ndarray, np.ndarray]:
        q = np.array(sha, dtype="S64")
        pos = np.clip(np.searchsorted(self.sha, q), 0, max(len(self.sha) - 1, 0))
        found = (self.sha[pos] == q) if len(self.sha) else np.zeros(len(q), dtype=bool)
        return pos, found


def load_added_index(snapshot: Path) -> AddedIndex | None:
    """Read metadata.csv once (about 80 MB in memory); None if the file is absent."""
    path = snapshot / "metadata.csv"
    if not path.exists():
        log.warning("LAMDA metadata.csv missing: ts falls back to the first of the month")
        return None
    import pyarrow.compute as pc
    import pyarrow.csv as pacsv

    cols = ["sha256", "added", "label", "vt_detection", "family"]
    types = {"sha256": pa.string(), "added": pa.string(), "family": pa.string()}
    types |= {"label": pa.float64(), "vt_detection": pa.float64()}
    table = pacsv.read_csv(
        path, convert_options=pacsv.ConvertOptions(include_columns=cols, column_types=types)
    )
    table = table.take(pc.sort_indices(table, sort_keys=[("sha256", "ascending")]))
    added = pc.strptime(table["added"], format="%Y-%m-%d %H:%M:%S", unit="s", error_is_null=True)
    added_s = pc.fill_null(added.cast(pa.int64()), -1).to_numpy()
    sha = np.array(pc.utf8_lower(table["sha256"]).to_pylist(), dtype="S64")
    return AddedIndex(
        sha=sha,
        added=added_s,
        label=table["label"].to_numpy(),
        vt=table["vt_detection"].to_numpy(),
        family=np.array(table["family"].to_pylist(), dtype=object),
        duplicates=int(len(sha) - len(np.unique(sha))),
    )


def _join_added(meta: pd.DataFrame, index: AddedIndex | None, stats: ChunkStats) -> None:
    """Set `added` and the slotting time `ts`; count every disagreement with metadata.csv.

    `ts` is `added` when it lies in the row's year_month, otherwise the first of that month,
    so the cache unit (chosen by year_month, the dataset's own field) always contains `ts`.
    """
    month_start = pd.to_datetime(meta["year_month"] + "-01", utc=True)
    if index is None or meta.empty:
        meta["added"] = pd.NaT
        meta["ts"] = month_start
        stats.meta_missing += len(meta)
        return
    pos, found = index.lookup(meta["sha256"].tolist())
    stats.meta_missing += int((~found).sum())
    secs = np.where(found, index.added[pos], -1)
    stats.added_null += int((found & (secs < 0)).sum())
    added = pd.to_datetime(np.where(secs >= 0, secs, 0), unit="s", utc=True)
    added = added.where(secs >= 0, pd.NaT)
    meta["added"] = added
    same_month = (added.strftime("%Y-%m") == meta["year_month"].to_numpy()) & (secs >= 0)
    stats.added_month_mismatch += int(((secs >= 0) & ~same_month).sum())
    meta["ts"] = np.where(same_month, added, month_start)
    meta["ts"] = pd.to_datetime(meta["ts"], utc=True)
    label = meta["label"].to_numpy()
    m_label = index.label[pos]
    stats.meta_label_conflicts += int((found & (m_label != label)).sum())
    vt = meta["vt_count"].astype("float64").to_numpy()
    m_vt = index.vt[pos]
    stats.meta_vt_conflicts += int((found & ~np.isclose(vt, m_vt, equal_nan=True)).sum())
    fam = meta["family"].to_numpy(dtype=object)
    m_fam = index.family[pos]
    mal = found & (label == 1)
    stats.meta_family_conflicts += int(sum(1 for i in np.flatnonzero(mal) if fam[i] != m_fam[i]))


def _row_hashes(m: sp.csr_matrix) -> list[str]:
    out = []
    for i in range(m.shape[0]):
        lo, hi = m.indptr[i], m.indptr[i + 1]
        h = hashlib.blake2b(m.indices[lo:hi].tobytes(), digest_size=16)
        h.update(m.data[lo:hi].tobytes())
        out.append(h.hexdigest())
    return out


def _batch_meta(batch: pa.RecordBatch, f: SourceFile, offset: int, stats: ChunkStats):
    n = batch.num_rows
    sha = [
        str(s).strip().lower() if s is not None else "" for s in batch.column("hash").to_pylist()
    ]
    label = batch.column("label").to_pylist()
    family = batch.column("family").to_pylist()
    vt = batch.column("vt_count").to_pylist()
    ym = [parse_month(v) for v in batch.column("year_month").to_pylist()]
    keep = np.ones(n, dtype=bool)
    for i in range(n):
        reason = None
        if ym[i] is None:
            reason = "bad_year_month"
        elif label[i] not in (0, 1):
            reason = "bad_label"
        elif not SHA256.match(sha[i]):
            reason = "bad_sha256"
        if reason:
            keep[i] = False
            stats.excluded[reason] += 1
            continue
        if int(ym[i][:4]) != f.year:
            stats.folder_year_mismatch += 1
        if family[i] is None or family[i] == "":
            if label[i] == 1:
                stats.family_null_malware += 1
            else:
                stats.family_null_benign += 1
        v = vt[i]
        if v is None or (isinstance(v, float) and np.isnan(v)):
            stats.vt_null += 1
            vt[i] = None
        else:
            if float(v) != int(v):
                stats.vt_non_integral += 1
            vt[i] = int(v)
            if (label[i] == 0 and vt[i] != 0) or (label[i] == 1 and vt[i] < 4):
                stats.vt_label_conflicts += 1
    meta = pd.DataFrame(
        {
            "row_id": np.arange(offset, offset + n, dtype=np.int64) + f.index * ROW_ID_STRIDE,
            "sha256": sha,
            "year_month": ym,
            "label": label,
            "family": [x if x not in (None, "") else None for x in family],
            "vt_count": vt,
            "src_file": f.rel,
            "src_split": f.split,
        }
    )
    return meta, keep


def _dense_block(batch: pa.RecordBatch, feats: list[str], stats: ChunkStats) -> np.ndarray:
    block = np.empty((batch.num_rows, len(feats)), dtype=np.int8)
    for j, name in enumerate(feats):
        col = batch.column(name)
        if col.null_count:
            stats.feature_nulls += col.null_count
            raise ValueError(f"{name} has {col.null_count} nulls; refusing to impute silently")
        block[:, j] = col.to_numpy(zero_copy_only=False)
    return block


def stream_chunk(
    group: list[SourceFile],
    feats: list[str],
    batch_size: int,
    stats: ChunkStats,
    index: AddedIndex | None,
):
    """Yield (month, csr, meta) pieces for every batch of every file in the chunk."""
    for f in group:
        pf = pq.ParquetFile(f.path, pre_buffer=False)
        if feature_names(pf.schema_arrow) != feats:
            raise ValueError(f"{f.rel}: feature columns differ from the first file")
        log.info(
            "LAMDA %s: %d rows, %d row groups",
            f.rel,
            pf.metadata.num_rows,
            pf.metadata.num_row_groups,
        )
        offset = 0
        for batch in pf.iter_batches(batch_size=batch_size, use_threads=False):
            meta, keep = _batch_meta(batch, f, offset, stats)
            offset += batch.num_rows
            stats.rows_read += batch.num_rows
            dense = _dense_block(batch, feats, stats)
            stats.max_value = max(stats.max_value, int(dense.max(initial=0)))
            csr = sp.csr_matrix(dense[keep])
            del dense
            meta = meta[keep].reset_index(drop=True)
            stats.nnz += csr.nnz
            meta["fv_hash"] = _row_hashes(csr)
            _join_added(meta, index, stats)
            for month, idx in meta.groupby("year_month", sort=True).indices.items():
                yield month, csr[idx], meta.iloc[idx]


def _write_unit(layout: Layout, month: str, xs: list, metas: list) -> dict[str, Any]:
    X = sp.vstack(xs, format="csr")
    meta = pd.concat(metas, ignore_index=True)
    order = meta.sort_values(["ts", "sha256", "row_id"], kind="stable").index.to_numpy()
    X = X[order]
    meta = meta.iloc[order].reset_index(drop=True)
    meta["vt_count"] = meta["vt_count"].astype("Int16")
    table = pa.Table.from_pandas(meta[META_SCHEMA.names], schema=META_SCHEMA, preserve_index=False)
    unit_dir = layout.unit_dir("lamda", month)
    save_csr(unit_dir / "X.npz", X)
    save_table(unit_dir / "meta.parquet", table)
    files = {layout.rel(unit_dir / n): file_record(unit_dir / n) for n in ("X.npz", "meta.parquet")}
    return {
        "n_rows": int(X.shape[0]),
        "n_malware": int((meta["label"] == 1).sum()),
        "nnz": int(X.nnz),
        "start": unit_start(month).isoformat(),
        "end": unit_end(month).isoformat(),
        "files": files,
    }


def build(
    layout: Layout, snapshot: Path, cache: dict[str, Any], batch_size: int
) -> Iterator[dict[str, Any]]:
    """Build (or resume) the monthly caches, updating ``cache`` in place.

    Yields after every chunk so the caller can persist the manifest (resume point).
    """
    files = source_files(snapshot)
    feats = feature_names(pq.ParquetFile(files[0].path).schema_arrow)
    months = prescan(files)
    index = load_added_index(snapshot)
    cache.setdefault("units", {})
    cache.setdefault("chunks", {})
    cache.update(
        {
            "base_unit": "month",
            "n_features": len(feats),
            "feature_dtype": "int8",
            "x_format": "csr-npz",
            "timestamp": "added (AndroZoo) when inside year_month, else first of the month",
            "metadata_csv_duplicate_sha256": None if index is None else index.duplicates,
            "prescan": {
                f.rel: {m or "invalid": c for m, c in sorted(months[f.index].items(), key=str)}
                for f in files
            },
        }
    )
    for group in chunks(files, months):
        cid = chunk_id(group)
        done = cache["chunks"].get(cid)
        if done and all(
            m in cache["units"] and unit_files_match(layout, cache["units"][m])
            for m in done["units"]
        ):
            log.info("LAMDA chunk %s: up to date, skipped", cid)
            continue
        stats = ChunkStats()
        pieces: dict[str, tuple[list, list]] = defaultdict(lambda: ([], []))
        for month, x, meta in stream_chunk(group, feats, batch_size, stats, index):
            pieces[month][0].append(x)
            pieces[month][1].append(meta)
        for month in sorted(pieces):
            cache["units"][month] = _write_unit(layout, month, *pieces[month])
        cache["chunks"][cid] = {
            "files": [f.rel for f in group],
            "units": sorted(pieces),
            "stats": stats.as_dict(),
        }
        log.info("LAMDA chunk %s: %d months, %d rows", cid, len(pieces), stats.rows_read)
        pieces.clear()
        yield cache
