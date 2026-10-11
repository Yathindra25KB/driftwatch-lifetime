"""Fit-time benchmark at the largest training window, per model and dataset (Phase 4).

    uv run python scripts/bench_fit.py configs/e0_bodmas.yaml configs/e0_lamda.yaml

For each config it plans every E0 variant (features-free), picks the training window with
the most rows, loads it once and fits each configured model, plus LightGBM in both profiles,
several times. It records wall time, peak memory, whether two fits give byte-identical
probabilities, and the machine (cores, RAM). The model rows load training rows only. The
last row per dataset runs the runner's random-split step (it loads evaluation rows and fits
both comparators) to measure time and peak memory; its F1 values are discarded unprinted.
Nothing printed or stored is a score, so nothing here can steer a choice by AUT.

The 60 s rule (guide E2, PROTOCOL section 4): a fit over 60 s means the fast profile, then
row or feature subsampling, then a smaller grid. ``within_60s`` is judged on the median.
Results go to reports/tables/fit_times.csv (committed after a CLAIMS row) and
results/bench/fit_times.json (not committed).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import psutil

from driftwatch.data.cache import code_version
from driftwatch.data.memory import MemoryWatchdog
from driftwatch.data.presets import cached_source
from driftwatch.data.slicer import plan_slots, plan_windows, slice_windows
from driftwatch.models import make_model
from driftwatch.sim.config import RunConfig, package_versions
from driftwatch.sim.runner import _random_split, _spec_for

ROOT = Path(__file__).resolve().parents[1]
LIMIT_S = 60.0
MEMORY_CAP = int(1.5 * 1024**3)  # the cap approved for data work; reported against, not enforced
HARD_STOP = int(6 * 1024**3)  # the watchdog only prevents the machine from swapping
PROBE_ROWS = 2000  # training rows scored for the determinism check (no evaluation data)


def largest_training_window(source: Any, cfg: RunConfig, pooled: bool = False) -> dict[str, Any]:
    """The E0 window with most rows, by plan counts (no features read).

    ``pooled`` counts training plus evaluation rows (what the random-split step stacks) and
    skips the single-run variant, which has no random split.
    """
    best: dict[str, Any] | None = None
    for variant in cfg.variants:
        if pooled and variant == "single_run":
            continue
        spec = _spec_for(cfg, variant, cfg.seeds[0])
        planned = plan_slots(source, spec)
        counts = {p.ref.slot_id: p for p in planned}
        schedule = plan_windows(planned, spec)
        for position, window in enumerate(schedule.windows):
            refs = (*window.train, *window.eval) if pooled else window.train
            rows = sum(counts[r.slot_id].n_rows for r in refs)
            if best is None or rows > best["n_rows"]:
                best = {
                    "variant": variant,
                    "position": position,
                    "spec": spec,
                    "n_rows": rows,
                    "first_slot": window.train[0].slot_id,
                    "last_slot": window.train[-1].slot_id,
                }
    if best is None:
        raise SystemExit(f"{cfg.name}: no window in any variant")
    return best


def timed_fit(spec: dict[str, Any], X: Any, y: np.ndarray, repeats: int) -> dict[str, Any]:
    fits: list[float] = []
    peaks: list[int] = []
    probes: list[bytes] = []
    info: dict[str, Any] = {}
    predict_s = 0.0
    for _ in range(repeats):
        det = make_model(spec, seed=0)
        with MemoryWatchdog(HARD_STOP, interval_s=0.02) as wd:
            t0 = time.perf_counter()
            det.fit(X, y, "bench")
            fits.append(time.perf_counter() - t0)
            t1 = time.perf_counter()
            p = det.predict_proba(X[:PROBE_ROWS], "bench")
            predict_s = time.perf_counter() - t1
        peaks.append(wd.peak_sampled)  # this fit's resident peak, data already loaded included
        probes.append(p.tobytes())
        info = {k: det.fit_info.get(k) for k in ("converged", "n_iter", "n_trees")}
    return {
        "fit_seconds": fits,
        "fit_median_s": statistics.median(fits),
        "fit_max_s": max(fits),
        "peak_bytes": max(peaks),
        "predict_probe_s": predict_s,
        "deterministic": len(set(probes)) == 1,
        **info,
    }


def bench_config(config_path: Path, root: Path, repeats: int) -> list[dict[str, Any]]:
    cfg = RunConfig.from_file(config_path)
    source = cached_source(cfg.dataset, root)
    big = largest_training_window(source, cfg)
    (window,) = slice_windows(source, big["spec"], only=[big["position"]])
    X, y = window.train.X, window.train.y
    meta = {
        "config": cfg.name,
        "dataset": cfg.dataset,
        "variant": big["variant"],
        "train_first": big["first_slot"],
        "train_last": big["last_slot"],
        "n_rows": int(len(y)),
        "n_malware": int((y == 1).sum()),
        "n_features": int(X.shape[1]),
        "sparse": bool(hasattr(X, "tocsr")),
    }
    specs = [dict(m) for m in cfg.models]
    for m in cfg.models:  # time both LightGBM profiles whichever the config uses
        if m["name"] == "lgbm":
            other = "default" if m.get("profile", "fast") == "fast" else "fast"
            specs.append({**m, "profile": other})
    rows = []
    for spec in specs:
        label = spec["name"] + (f"-{spec['profile']}" if "profile" in spec else "")
        log = logging.getLogger("bench_fit")
        log.info("%s: %s on %d rows x %d features", cfg.name, label, len(y), X.shape[1])
        result = timed_fit(spec, X, y, repeats)
        rows.append(
            {
                **meta,
                "model": label,
                **result,
                "within_60s": result["fit_median_s"] <= LIMIT_S,
                "within_1_5gb": result["peak_bytes"] <= MEMORY_CAP,
                "configured": spec in [dict(m) for m in cfg.models],
            }
        )
    if cfg.random_split:
        rows.append(_random_split_row(cfg, source, meta))
    return rows


def _random_split_row(cfg: RunConfig, source: Any, meta: dict[str, Any]) -> dict[str, Any]:
    """Peak memory and time of the runner's random-split step on the largest pooled window.

    It runs the runner's own code, fits every configured model and discards the F1 values:
    only seconds and resident memory are recorded.
    """
    big = largest_training_window(source, cfg, pooled=True)
    (window,) = slice_windows(source, big["spec"], only=[big["position"]])
    ctx = SimpleNamespace(cfg=cfg, source=source)
    with MemoryWatchdog(HARD_STOP, interval_s=0.02) as wd:
        t0 = time.perf_counter()
        n_mal = int((window.train.y == 1).sum())
        _random_split(ctx, window, big["spec"], cfg.seeds[0], n_mal)  # type: ignore[arg-type]
        seconds = time.perf_counter() - t0
    return {
        **meta,
        "variant": big["variant"],
        "train_first": big["first_slot"],
        "train_last": big["last_slot"],
        "n_rows": big["n_rows"],  # pooled rows of the window
        "n_malware": None,
        "model": "random-split step (all configured models)",
        "fit_median_s": seconds,
        "fit_max_s": seconds,
        "peak_bytes": wd.peak_sampled,
        "deterministic": None,
        "within_60s": seconds <= LIMIT_S,
        "within_1_5gb": wd.peak_sampled <= MEMORY_CAP,
        "configured": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("configs", nargs="+", type=Path)
    parser.add_argument("--root", type=Path, default=Path("data"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--csv", type=Path, default=ROOT / "reports" / "tables" / "fit_times.csv")
    parser.add_argument("--json", type=Path, default=ROOT / "results" / "bench" / "fit_times.json")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    vm = psutil.virtual_memory()
    machine = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "physical_cores": psutil.cpu_count(logical=False),
        "ram_total_bytes": vm.total,
        "ram_available_bytes": vm.available,
        "code_version": code_version(ROOT),
        "packages": package_versions(),
    }
    rows: list[dict[str, Any]] = []
    for path in args.configs:
        rows.extend(bench_config(path, args.root, args.repeats))

    frame = pd.DataFrame(rows).drop(columns=["fit_seconds"])
    frame["peak_gb"] = (frame["peak_bytes"] / 1024**3).round(2)
    shown = [
        "dataset", "model", "n_rows", "n_features", "fit_median_s", "fit_max_s", "peak_gb",
        "deterministic", "within_60s", "within_1_5gb", "configured",
    ]  # fmt: skip
    print(frame[shown].to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print(
        f"\nmachine: {machine['physical_cores']} cores / {machine['cpu_count']} threads, "
        f"{machine['ram_total_bytes'] / 1024**3:.2f} GB RAM, {machine['processor']}"
    )
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    frame.drop(columns=["peak_bytes"]).round(3).to_csv(args.csv, index=False, lineterminator="\n")
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(
        json.dumps({"machine": machine, "rows": rows}, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.csv} and {args.json}")
    over = frame[~frame["within_60s"] & frame["configured"]]
    if len(over):
        print(
            "A configured fit exceeds 60 s: fast profile, then subsampling, then shrink the grid."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
