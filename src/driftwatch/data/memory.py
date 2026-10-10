"""Peak-memory watchdog and wall-clock timer for cache builds.

The researcher approved a 1.5 GB peak-memory cap for this 8 GB laptop (Phase 2). The
watchdog samples the process's resident set in a background thread. If the cap is
crossed, it interrupts the main thread and the build stops with
:class:`MemoryCapExceeded`. On Windows the OS-tracked lifetime peak (``peak_wset``)
is also read at exit, so short spikes between samples are not missed.
"""

from __future__ import annotations

import _thread
import logging
import threading
import time
from dataclasses import dataclass, field
from types import TracebackType

import psutil

log = logging.getLogger(__name__)


class MemoryCapExceeded(MemoryError):
    """The build crossed the approved peak-memory cap."""


@dataclass
class MemoryWatchdog:
    cap_bytes: int
    interval_s: float = 0.05
    peak_sampled: int = 0
    peak_os: int | None = None
    wall_s: float = 0.0
    exceeded_at: int | None = None
    _stop: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _t0: float = 0.0

    @property
    def peak_bytes(self) -> int:
        return max(self.peak_sampled, self.peak_os or 0)

    def _rss(self) -> int:
        return psutil.Process().memory_info().rss

    def _watch(self) -> None:
        while not self._stop.wait(self.interval_s):
            rss = self._rss()
            self.peak_sampled = max(self.peak_sampled, rss)
            if rss > self.cap_bytes and self.exceeded_at is None:
                self.exceeded_at = rss
                log.error("memory cap crossed: %d > %d bytes", rss, self.cap_bytes)
                _thread.interrupt_main()
                return

    def __enter__(self) -> MemoryWatchdog:
        self._t0 = time.perf_counter()
        self.peak_sampled = self._rss()
        self._thread = threading.Thread(target=self._watch, name="memory-watchdog", daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
        self.wall_s = time.perf_counter() - self._t0
        info = psutil.Process().memory_info()
        self.peak_os = getattr(info, "peak_wset", None)
        self.peak_sampled = max(self.peak_sampled, info.rss)
        if self.exceeded_at is not None:
            raise MemoryCapExceeded(
                f"peak memory {self.exceeded_at / 1024**3:.2f} GB crossed the approved cap "
                f"of {self.cap_bytes / 1024**3:.2f} GB"
            ) from exc
        return False

    def as_record(self) -> dict[str, float | int | None]:
        return {
            "cap_bytes": self.cap_bytes,
            "peak_bytes": self.peak_bytes,
            "peak_sampled_bytes": self.peak_sampled,
            "peak_os_bytes": self.peak_os,
            "wall_s": round(self.wall_s, 2),
        }
