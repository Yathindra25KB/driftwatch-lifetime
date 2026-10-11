"""A whole-dataset slicing pass: every window, every evaluation slot, one slot in memory.

This is what ``driftwatch data slice`` runs. It proves the slicer terminates in minutes on
the real caches, stays under the approved peak-memory cap, never densifies a sparse source,
and never trips C1-C3 (a violation raises and ends the run). It also writes the per-slot
manifest. No model is involved; nothing here depends on labels beyond the counts.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import scipy.sparse as sp

from driftwatch.data.memory import MemoryCapExceeded, MemoryWatchdog
from driftwatch.data.slicer import SliceLog, SlotSource, WindowSpec, slice_windows

log = logging.getLogger(__name__)


def run_slicing(
    source: SlotSource, spec: WindowSpec, out_dir: Path | str, *, memory_cap_bytes: int
) -> dict[str, Any]:
    """Slice ``source`` completely, write the manifest under ``out_dir``, return the summary."""
    slicelog = SliceLog()
    counts = {"windows": 0, "train_rows_loaded": 0, "eval_slots": 0, "eval_rows": 0}
    dense_matrices = 0
    started = time.perf_counter()
    with MemoryWatchdog(memory_cap_bytes) as watchdog:
        for window in slice_windows(source, spec, slicelog):
            counts["windows"] += 1
            counts["train_rows_loaded"] += sum(len(s) for s in window.train.slots)
            for slot in window.eval_slots():
                counts["eval_slots"] += 1
                counts["eval_rows"] += len(slot.y)
                if source.sparse and not sp.issparse(slot.X):
                    dense_matrices += 1
    wall = time.perf_counter() - started
    if watchdog.peak_bytes > memory_cap_bytes:
        raise MemoryCapExceeded(
            f"peak memory {watchdog.peak_bytes / 1024**3:.2f} GB crossed the cap "
            f"of {memory_cap_bytes / 1024**3:.2f} GB"
        )
    summary: dict[str, Any] = {
        **counts,
        "dense_matrices": dense_matrices,
        "wall_s": round(wall, 2),
        "memory": watchdog.as_record(),
    }
    slicelog.write(out_dir, spec=spec, source=source, extra=summary)
    log.info(
        "sliced %s: %d windows, %d evaluation slots, %.1f s, peak %.2f GB",
        source.name,
        counts["windows"],
        counts["eval_slots"],
        wall,
        watchdog.peak_bytes / 1024**3,
    )
    return summary
