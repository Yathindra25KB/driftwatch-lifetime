"""Window options per dataset, derived from slot counts only (input to ADR-0005).

Nothing here loads features or trains a model, so the options cannot be tuned on results.
For a ratio and a size gate it lists the maximal runs of usable slots (with how many slots
are already below the target ratio) and, for a grid of (nT, nE, stride), how many rolling
windows a source yields and how much the windows reuse evaluation slots.
"""

from __future__ import annotations

from typing import Any

from driftwatch.data.constraints import target_malware_count
from driftwatch.data.slicer import SlotSource, WindowSpec, _usable_runs, plan_slots, plan_windows


def _spec(nT: int, nE: int | None, stride: int, ratio: float, min_malware: int) -> WindowSpec:
    return WindowSpec(nT=nT, nE=nE, stride=stride, target_ratio=ratio, min_malware=min_malware)


def segment_table(source: SlotSource, *, ratio: float, min_malware: int) -> list[dict[str, Any]]:
    """One row per maximal run of consecutive usable slots."""
    planned = plan_slots(source, _spec(1, 1, 1, ratio, min_malware))
    out = []
    for i, run in enumerate(_usable_runs(planned)):
        below = sum(1 for p in run if p.n_malware < target_malware_count(p.n_benign, ratio))
        out.append(
            {
                "segment": i,
                "first": run[0].ref.slot_id,
                "last": run[-1].ref.slot_id,
                "n_slots": len(run),
                "n_below_target": below,
                "min_malware_kept": min(p.n_malware_kept for p in run),
                "min_rows": min(p.n_rows for p in run),
                "max_rows": max(p.n_rows for p in run),
            }
        )
    return out


def run_lengths(source: SlotSource, *, ratio: float, min_malware: int) -> list[int]:
    return [s["n_slots"] for s in segment_table(source, ratio=ratio, min_malware=min_malware)]


def candidate_windows(
    source: SlotSource, *, nT: int, nE: int | None, stride: int, ratio: float, min_malware: int
) -> dict[str, Any]:
    spec = _spec(nT, nE, stride, ratio, min_malware)
    schedule = plan_windows(plan_slots(source, spec), spec)
    evals = [r.slot_id for w in schedule.windows for r in w.eval]
    distinct = len(set(evals))
    return {
        "nT": nT,
        "nE": nE,
        "stride": stride,
        "ratio": ratio,
        "min_malware": min_malware,
        "n_windows": len(schedule.windows),
        "n_eval_slots_distinct": distinct,
        "eval_reuse": (len(evals) / distinct) if distinct else 0.0,
        "slots_per_window": None if nE is None else nT + nE,
    }
