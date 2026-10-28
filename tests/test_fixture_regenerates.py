"""The committed synthetic fixture is what the generator writes (contents, see `digest`).

The fixture is the only dataset content in the repository (CLAUDE.md rule 11, under 1 MB). It
is seeded, so regenerating it must change nothing; a difference means the generator or its
inputs changed and the committed fixture, and every golden file built from it, is stale.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from driftwatch.data.fixture import write_fixture

COMMITTED = Path(__file__).resolve().parent / "fixtures" / "synthetic"
LIMIT_BYTES = 1_000_000


def digest(path: Path) -> str:
    """SHA-256 of the file, or of its contents for npz and parquet.

    The containers carry the writer's version: an npz zip differs by platform, and a parquet
    file stores the pandas version in its metadata, so a pandas upgrade changes its bytes while
    every value stays the same (found by the 26 Oct 2026 dependency refresh, pandas 3.0.6 to
    3.1.0). The contents are what the fixture promises.
    """
    if path.suffix == ".npz":
        h = hashlib.sha256()
        with np.load(path) as arrays:
            for name in sorted(arrays.files):
                h.update(name.encode())
                h.update(np.ascontiguousarray(arrays[name]).tobytes())
        return h.hexdigest()
    if path.suffix == ".parquet":
        table = pq.read_table(path).replace_schema_metadata(None)
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        return hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digests(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob("*")) if p.is_file()
    }


def test_regenerating_the_fixture_reproduces_the_committed_files(tmp_path: Path) -> None:
    fresh = tmp_path / "synthetic"
    write_fixture(fresh)
    assert digests(fresh) == digests(COMMITTED)


def test_the_committed_fixture_stays_under_one_megabyte() -> None:
    total = sum(p.stat().st_size for p in COMMITTED.rglob("*") if p.is_file())
    assert total < LIMIT_BYTES, total
