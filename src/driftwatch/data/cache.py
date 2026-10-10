"""On-disk layout, atomic writes, file hashing and the content-hashed data manifest.

Layout under a data root (default ``data/``)::

    raw/<dataset>/...                 upstream files as downloaded
    cache/<dataset>/v1/units/<unit>/  one folder per base unit (month or ISO week)
    build_logs/<dataset>-<utc>.json   peak memory, wall-clock, disk size, params
    manifest.json                     sources, file hashes, row counts, builds

The manifest is canonical JSON with a top-level ``content_hash`` over everything else, so
any edit that does not go through :func:`save_manifest` is detected by ``data verify``.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import scipy.sparse as sp

from driftwatch.data.sources import CACHE_VERSION

log = logging.getLogger(__name__)

MANIFEST_SCHEMA = 1
_CHUNK = 1 << 20
# Fixed zip timestamp so a rebuilt CSR file is byte-identical (np.savez stamps "now").
_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class Layout:
    root: Path

    def raw(self, dataset: str) -> Path:
        return self.root / "raw" / dataset

    def cache(self, dataset: str) -> Path:
        return self.root / "cache" / dataset / CACHE_VERSION

    def unit_dir(self, dataset: str, unit: str) -> Path:
        return self.cache(dataset) / "units" / unit

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def build_logs(self) -> Path:
        return self.root / "build_logs"

    def rel(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    return {"sha256": sha256_file(path), "bytes": path.stat().st_size}


def _tmp(path: Path) -> Path:
    return path.with_name(path.name + ".tmp")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp(path)
    tmp.write_bytes(data)
    os.replace(tmp, path)


def save_csr(path: Path, matrix: sp.csr_matrix) -> None:
    """Write a CSR matrix that ``scipy.sparse.load_npz`` reads, byte-for-byte reproducibly."""
    matrix = sp.csr_matrix(matrix)
    arrays = {
        "format": np.array("csr"),
        "shape": np.array(matrix.shape, dtype=np.int64),
        "data": matrix.data,
        "indices": matrix.indices,
        "indptr": matrix.indptr,
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, arr in arrays.items():
            info = zipfile.ZipInfo(f"{name}.npy", date_time=_ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            member = io.BytesIO()
            np.lib.format.write_array(member, np.asarray(arr), allow_pickle=False)
            zf.writestr(info, member.getvalue())
    atomic_write_bytes(path, buf.getvalue())


def save_dense(path: Path, matrix: np.ndarray) -> None:
    buf = io.BytesIO()
    np.lib.format.write_array(buf, np.ascontiguousarray(matrix), allow_pickle=False)
    atomic_write_bytes(path, buf.getvalue())


def save_table(path: Path, table: pa.Table) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp(path)
    pq.write_table(table, tmp, compression="zstd")
    os.replace(tmp, path)


# --- manifest ---------------------------------------------------------------------------


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def content_hash(manifest: dict[str, Any]) -> str:
    body = {k: v for k, v in manifest.items() if k != "content_hash"}
    return "sha256:" + hashlib.sha256(_canonical(body)).hexdigest()


def empty_manifest() -> dict[str, Any]:
    return {"schema_version": MANIFEST_SCHEMA, "datasets": {}}


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_manifest()
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    manifest = dict(manifest)
    manifest["content_hash"] = content_hash(manifest)
    text = json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    atomic_write_bytes(path, text.encode("utf-8"))


def unit_files_match(layout: Layout, entry: dict[str, Any]) -> bool:
    """True when every file a manifest unit entry names exists with the recorded hash."""
    for rel, rec in entry.get("files", {}).items():
        path = layout.root / rel
        if not path.exists() or path.stat().st_size != rec["bytes"]:
            return False
        if sha256_file(path) != rec["sha256"]:
            return False
    return bool(entry.get("files"))


def code_version(repo: Path | None = None) -> str:
    """Git commit of the code that built a cache, with ``-dirty`` for uncommitted changes."""
    cwd = repo or Path(__file__).resolve().parents[3]
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=cwd, capture_output=True, text=True
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=cwd,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except OSError:
        return "unknown"
    return (head or "unknown") + ("-dirty" if dirty else "")


def dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
