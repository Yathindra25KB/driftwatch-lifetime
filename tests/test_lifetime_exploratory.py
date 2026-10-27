"""The exploratory lifetime reading of a per-slot F1 curve."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

SPEC = importlib.util.spec_from_file_location(
    "lifetime_exploratory", Path(__file__).resolve().parents[1] / "scripts/lifetime_exploratory.py"
)
assert SPEC and SPEC.loader
lifetime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lifetime)


def frame(f1: list[float], policy: str = "never") -> pd.DataFrame:
    n = len(f1)
    return pd.DataFrame(
        {
            "dataset": ["d"] * n,
            "model": ["m"] * n,
            "policy": [policy] * n,
            "delay": [0.0 if policy == "periodic" else float("nan")] * n,
            "budget_pct": [5.0 if policy == "periodic" else float("nan")] * n,
            "slot_position": range(1, n + 1),
            "mean_f1": f1,
        }
    )


def test_lifetime_is_first_slot_at_least_the_drop_below_the_first() -> None:
    row = lifetime.curve_rows(frame([0.90, 0.88, 0.84, 0.86]))
    assert row["lifetime_slots"] == 3
    assert row["first_f1"] == 0.9


def test_no_lifetime_when_the_drop_is_never_reached() -> None:
    row = lifetime.curve_rows(frame([0.90, 0.89, 0.91, 0.90]))
    assert row["lifetime_slots"] is None


def test_slope_sign_follows_the_trend() -> None:
    assert lifetime.curve_rows(frame([0.9, 0.8, 0.7]))["slope_per_slot"] < 0
    assert lifetime.curve_rows(frame([0.7, 0.8, 0.9]))["slope_per_slot"] > 0


def test_table_has_a_never_and_a_periodic_arm_per_model() -> None:
    both = pd.concat([frame([0.9, 0.8]), frame([0.9, 0.9], policy="periodic")])
    table = lifetime.lifetime_table(both)
    assert sorted(table["arm"]) == ["never", "periodic, delay 0, budget 5%"]
