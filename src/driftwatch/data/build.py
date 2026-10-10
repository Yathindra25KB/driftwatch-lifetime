"""`driftwatch data build`: run a dataset builder under the memory watchdog.

The manifest is persisted after every chunk (LAMDA) or batch of weeks (BODMAS), so an
interrupted build resumes where it stopped. A rebuild over unchanged raw files skips
every unit whose files already match. If the raw files changed, the build refuses: a
new dataset version needs a new data root and manifest entry, never a silent overwrite.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from driftwatch.data.cache import (
    Layout,
    atomic_write_bytes,
    code_version,
    dir_size,
    file_record,
    load_manifest,
    save_manifest,
)
from driftwatch.data.download import lamda_raw_dir, read_source
from driftwatch.data.memory import MemoryWatchdog
from driftwatch.data.sources import CACHE_VERSION

log = logging.getLogger(__name__)


class SourceChanged(RuntimeError):
    """Raw files differ from the ones the existing cache was built from."""


def _raw_files(raw_dir: Path, raw_layout: Layout) -> dict[str, dict[str, Any]]:
    paths = sorted(
        p
        for p in raw_dir.rglob("*")
        if p.is_file() and ".cache" not in p.relative_to(raw_dir).parts and p.suffix != ".part"
    )
    return {raw_layout.rel(p): file_record(p) for p in paths}


def _cross_unit_sha256(layout: Layout, dataset: str, units: dict[str, Any]) -> int:
    seen: Counter[str] = Counter()
    for unit in units:
        meta = pq.read_table(layout.unit_dir(dataset, unit) / "meta.parquet", columns=["sha256"])
        seen.update(set(meta.column(0).to_pylist()))
    return sum(1 for c in seen.values() if c > 1)


def build_dataset(
    dataset: str,
    layout: Layout,
    raw_layout: Layout | None = None,
    memory_cap_bytes: int = int(1.5 * 1024**3),
    batch_size: int = 8192,
) -> dict[str, Any]:
    raw_layout = raw_layout or layout
    raw_dir = lamda_raw_dir(raw_layout) if dataset == "lamda" else raw_layout.raw(dataset)
    source = read_source(raw_dir)
    files = _raw_files(raw_dir, raw_layout)
    manifest = load_manifest(layout.manifest)
    entry = manifest["datasets"].setdefault(dataset, {})
    old_files = entry.get("source", {}).get("files")
    if old_files is not None and old_files != files:
        raise SourceChanged(
            f"{dataset}: raw files differ from the manifest; build into a new data root "
            "and record a new manifest entry instead of overwriting"
        )
    entry["source"] = {**source, "raw_dir": raw_layout.rel(raw_dir), "files": files}
    if raw_layout.root.resolve() != layout.root.resolve():
        entry["source"]["raw_root"] = str(raw_layout.root.resolve())
    cache = entry.setdefault("cache", {})
    cache["version"] = CACHE_VERSION
    cache["dir"] = layout.rel(layout.cache(dataset))
    params = {"batch_size": batch_size, "memory_cap_bytes": memory_cap_bytes}
    started = datetime.now(UTC)

    with MemoryWatchdog(memory_cap_bytes) as watchdog:
        if dataset == "lamda":
            from driftwatch.data import lamda

            steps = lamda.build(layout, raw_dir, cache, batch_size)
        elif dataset == "bodmas":
            from driftwatch.data import bodmas

            steps = bodmas.build(layout, raw_dir, cache, batch_size)
        else:
            raise ValueError(dataset)
        for _ in steps:
            save_manifest(layout.manifest, manifest)  # resume point
        cache["n_rows"] = sum(u["n_rows"] for u in cache["units"].values())
        cache["n_malware"] = sum(u["n_malware"] for u in cache["units"].values())
        cache["cross_unit_sha256"] = _cross_unit_sha256(layout, dataset, cache["units"])

    record = {
        "started_utc": started.isoformat(timespec="seconds"),
        "code_version": code_version(),
        "params": params,
        "memory": watchdog.as_record(),
        "cache_bytes": dir_size(layout.cache(dataset)),
        "raw_bytes": sum(f["bytes"] for f in files.values()),
        "n_rows": cache["n_rows"],
    }
    entry.setdefault("builds", []).append(record)
    save_manifest(layout.manifest, manifest)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    log_path = layout.build_logs / f"{dataset}-{stamp}.json"
    atomic_write_bytes(log_path, (json.dumps(record, indent=2) + "\n").encode())
    log.info(
        "%s: %d rows in %d units; peak %.2f GB (cap %.2f GB); %.1f s; cache %.1f MB",
        dataset,
        cache["n_rows"],
        len(cache["units"]),
        watchdog.peak_bytes / 1024**3,
        memory_cap_bytes / 1024**3,
        watchdog.wall_s,
        record["cache_bytes"] / 1024**2,
    )
    return record
