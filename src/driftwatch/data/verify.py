"""`driftwatch data verify`: the caches are exactly what the manifest says they are.

Checks:
- the manifest's own content hash;
- the sha256 of every raw file and every cache file;
- per unit: row counts, malware counts, timestamps inside the unit's window, timestamps
  sorted;
- across units: every row_id is unique (no row in two units, hence no row in two slots), and
  units are ordered in time. The number of sha256 values found in more than one unit must
  match the number recorded at build time. That count is a dataset property reported by the
  inventory, not a cache defect.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd

from driftwatch.data.cache import Layout, content_hash, load_manifest, sha256_file
from driftwatch.data.loaders import CachedDataset
from driftwatch.data.slots import unit_end, unit_start

log = logging.getLogger(__name__)


def _check_files(layout: Layout, files: dict[str, dict], what: str) -> list[str]:
    problems = []
    for rel, rec in sorted(files.items()):
        path = layout.root / rel
        if not path.exists():
            problems.append(f"{what}: missing {rel}")
        elif path.stat().st_size != rec["bytes"] or sha256_file(path) != rec["sha256"]:
            problems.append(f"{what}: hash mismatch {rel}")
    return problems


def _check_unit(name: str, unit: str, entry: dict, x_rows: int, meta: pd.DataFrame) -> list[str]:
    problems = []
    if x_rows != entry["n_rows"] or len(meta) != entry["n_rows"]:
        problems.append(
            f"{name} {unit}: rows X={x_rows} meta={len(meta)} manifest={entry['n_rows']}"
        )
    if int((meta["label"] == 1).sum()) != entry["n_malware"]:
        problems.append(f"{name} {unit}: malware count differs from the manifest")
    if not meta["label"].isin([0, 1]).all():
        problems.append(f"{name} {unit}: labels outside {{0, 1}}")
    ts = pd.to_datetime(meta["ts"], utc=True)
    start, end = pd.Timestamp(unit_start(unit)), pd.Timestamp(unit_end(unit))
    if len(ts) and (ts.min() < start or ts.max() >= end):
        problems.append(f"{name} {unit}: timestamps outside [{start}, {end})")
    if not ts.is_monotonic_increasing:
        problems.append(f"{name} {unit}: timestamps not sorted")
    return problems


def verify_dataset(layout: Layout, name: str, manifest: dict) -> list[str]:
    entry = manifest["datasets"].get(name)
    if entry is None:
        return [f"{name}: not in manifest"]
    raw_root = entry["source"].get("raw_root")
    raw_layout = Layout(Path(raw_root)) if raw_root else layout
    problems = _check_files(raw_layout, entry["source"]["files"], f"{name} raw")
    cache = entry["cache"]
    for unit, unit_entry in cache["units"].items():
        problems += _check_files(layout, unit_entry["files"], f"{name} cache {unit}")
    if problems:
        return problems  # content checks on tampered files would only add noise

    data = CachedDataset(name, layout.root)
    row_ids: list[np.ndarray] = []
    sha_units: Counter[str] = Counter()
    previous_end = None
    total = 0
    for unit in data.units:
        x, meta = data.load_unit(unit, mmap=True)
        problems += _check_unit(name, unit, cache["units"][unit], x.shape[0], meta)
        if previous_end is not None and unit_start(unit) < previous_end:
            problems.append(f"{name} {unit}: overlaps the previous unit")
        previous_end = unit_end(unit)
        row_ids.append(meta["row_id"].to_numpy())
        sha_units.update(set(meta["sha256"]))
        total += len(meta)
    ids = np.concatenate(row_ids) if row_ids else np.array([], dtype=np.int64)
    if np.unique(ids).size != ids.size:
        problems.append(f"{name}: a row_id appears more than once (row in two units)")
    if total != cache["n_rows"]:
        problems.append(f"{name}: {total} rows, manifest says {cache['n_rows']}")
    cross = sum(1 for c in sha_units.values() if c > 1)
    if cross != cache["cross_unit_sha256"]:
        problems.append(
            f"{name}: {cross} sha256 in several units, build recorded {cache['cross_unit_sha256']}"
        )
    return problems


def verify(layout: Layout, datasets: Iterable[str]) -> list[str]:
    if not layout.manifest.exists():
        return [f"{layout.manifest} missing"]
    manifest = load_manifest(layout.manifest)
    if manifest.get("content_hash") != content_hash(manifest):
        return ["manifest content_hash does not match its contents (edited by hand?)"]
    problems: list[str] = []
    for name in datasets:
        found = verify_dataset(layout, name, manifest)
        log.info("verify %s: %s", name, "OK" if not found else f"{len(found)} problems")
        problems += found
    return problems
