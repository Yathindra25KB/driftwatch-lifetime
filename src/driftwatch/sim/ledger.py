"""The grid's progress ledger: an append-only JSONL log of cell events.

Kept apart from the driver so that table code can read a ledger without importing the
simulator or any model code. One line per event; the last event of a cell is its state.
Smoke events (one seed, one window) are never counted as finished cells of the real grid.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LEDGER_NAME = "ledger.jsonl"

# --- ledger -----------------------------------------------------------------------------------

EVENTS = ("started", "complete", "failed", "invalidated", "retry", "flag")


@dataclass
class CellState:
    cell_id: str
    status: str = "planned"  # planned | running | complete | failed | invalidated
    code_version: str | None = None
    config_hash: str | None = None
    dir: str | None = None
    wall_s: float | None = None
    max_fit_s: float | None = None
    peak_gb: float | None = None
    reason: str | None = None
    flags: list[str] = field(default_factory=list)
    attempts: int = 0


class Ledger:
    """Append-only JSONL: one line per event, the last event of a cell is its state."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def append(self, event: str, cell_id: str, **fields: Any) -> dict[str, Any]:
        if event not in EVENTS:
            raise ValueError(f"unknown ledger event {event!r}")
        row = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "event": event,
            "cell_id": cell_id,
            **fields,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        return row

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def state(self, cell_ids: Iterable[str] = (), *, smoke: bool = False) -> dict[str, CellState]:
        return fold_events(self.events(), cell_ids, smoke=smoke)


def fold_events(
    rows: Iterable[dict[str, Any]], cell_ids: Iterable[str] = (), *, smoke: bool = False
) -> dict[str, CellState]:
    """The state of every cell from its events, in the order given.

    Smoke events and real events never mix: a smoke run (one seed, one window) is not a
    finished cell, and the real driver must not see it as one.
    """
    out = {c: CellState(c) for c in cell_ids}
    for row in rows:
        if bool(row.get("smoke")) != smoke:
            continue
        st = out.setdefault(row["cell_id"], CellState(row["cell_id"]))
        ev = row["event"]
        if ev == "started":
            st.status, st.attempts = "running", st.attempts + 1
            st.code_version = row.get("code_version")
            st.config_hash = row.get("config_hash")
        elif ev == "complete":
            st.status = "complete"
            for k in ("code_version", "config_hash", "dir", "wall_s", "max_fit_s", "peak_gb"):
                setattr(st, k, row.get(k, getattr(st, k)))
            st.reason = None
        elif ev == "failed":
            st.status, st.reason = "failed", row.get("reason")
        elif ev == "invalidated":
            st.status, st.reason = "invalidated", row.get("reason")
        elif ev == "flag":
            st.flags.append(str(row.get("flag")))
        # "retry" only documents why a failed cell was run again; "started" follows it
    return out


def merged_ledger_events(root: Path | str) -> list[dict[str, Any]]:
    """Events of every ``ledger*.jsonl`` under ``root`` (chunks may have run on other machines)."""
    rows: list[dict[str, Any]] = []
    for p in sorted(Path(root).glob("ledger*.jsonl")):
        rows += Ledger(p).events()
    return sorted(rows, key=lambda r: r["ts"])  # stable: file order breaks ties
