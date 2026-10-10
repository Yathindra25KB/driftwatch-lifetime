"""Base units and slot schemes.

Caches are stored per **base unit**: a calendar month for LAMDA (its timestamps are
YYYY-MM) and an ISO week (Monday 00:00 UTC) for BODMAS. A **slot** is one or more
consecutive base units:

- ``month`` and ``quarter``: calendar-aligned.
- ``1w``, ``2w`` and ``4w``: consecutive ISO weeks, anchored at the first week that holds
  data.

Every slot between the first and the last populated unit is listed. Slots with no rows are
marked as gaps (LAMDA 2015), because rolling windows must never span a gap. Choosing among
these candidates is ADR-0004's job, not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

SLOT_LENGTHS = {"lamda": ("month", "quarter"), "bodmas": ("1w", "2w", "4w")}
BASE_UNIT = {"lamda": "month", "bodmas": "week"}
_WEEKS = {"1w": 1, "2w": 2, "4w": 4}


@dataclass(frozen=True)
class Slot:
    slot_id: str
    start: datetime  # inclusive, UTC
    end: datetime  # exclusive, UTC
    units: tuple[str, ...]  # populated base units inside the slot, in time order
    index: int  # position in the scheme, counting gaps

    @property
    def is_gap(self) -> bool:
        return not self.units


# --- base units ---------------------------------------------------------------------------


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def week_key(day: date) -> str:
    iso = day.isocalendar()
    return f"{iso.year:04d}-W{iso.week:02d}"


def unit_start(unit: str) -> datetime:
    if "-W" in unit:
        year, week = unit.split("-W")
        return datetime.fromisocalendar(int(year), int(week), 1).replace(tzinfo=UTC)
    year, month = unit.split("-")
    return datetime(int(year), int(month), 1, tzinfo=UTC)


def _add_months(start: datetime, months: int) -> datetime:
    total = start.year * 12 + start.month - 1 + months
    return start.replace(year=total // 12, month=total % 12 + 1)


def unit_end(unit: str) -> datetime:
    start = unit_start(unit)
    return start + timedelta(weeks=1) if "-W" in unit else _add_months(start, 1)


# --- slot schemes -------------------------------------------------------------------------


def _check(dataset: str, length: str) -> None:
    if length not in SLOT_LENGTHS.get(dataset, ()):
        raise ValueError(f"slot length {length!r} is not a candidate for {dataset}")


def build_slots(dataset: str, length: str, units: list[str]) -> list[Slot]:
    """All slots from the first to the last populated unit, gaps included, in time order."""
    _check(dataset, length)
    if not units:
        return []
    ordered = sorted(units, key=unit_start)
    first, last_end = unit_start(ordered[0]), unit_end(ordered[-1])
    if length in ("month", "quarter"):
        step = 1 if length == "month" else 3
        cursor = first if length == "month" else first.replace(month=(first.month - 1) // 3 * 3 + 1)

        def advance(s: datetime) -> datetime:
            return _add_months(s, step)

        def label(s: datetime) -> str:
            if length == "month":
                return f"month:{s:%Y-%m}"
            return f"quarter:{s.year}Q{(s.month - 1) // 3 + 1}"
    else:
        width = timedelta(weeks=_WEEKS[length])
        cursor = first

        def advance(s: datetime) -> datetime:
            return s + width

        def label(s: datetime) -> str:
            return f"{length}:{s:%Y-%m-%d}"

    slots: list[Slot] = []
    position = 0
    while cursor < last_end:
        end = advance(cursor)
        inside = tuple(u for u in ordered if cursor <= unit_start(u) < end)
        slots.append(Slot(label(cursor), cursor, end, inside, len(slots)))
        position += len(inside)
        cursor = end
    if position != len(ordered):
        raise AssertionError("every populated unit must fall in exactly one slot")
    return slots


def slot_by_id(dataset: str, length: str, units: list[str], slot_id: str) -> Slot:
    for slot in build_slots(dataset, length, units):
        if slot.slot_id == slot_id:
            return slot
    raise KeyError(f"no slot {slot_id!r} in {dataset} {length}")
