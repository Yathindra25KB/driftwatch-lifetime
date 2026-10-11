"""Leakage canary on a dataset's caches (Build Guide section 8; gate G1).

Shuffle timestamps inside chosen windows and compare a trivial model's AUT with its
random-split score (driftwatch.data.canary). PASS: shuffling closes at least half of the gap
between the time-aware AUT and the random-split F1. FAIL: it does not, so treat the slicer
as broken and fix it first. NO_GAP: the time-aware AUT is already at the random-split level
(nothing decays, or something leaks; an AUT above 0.9 is flagged as a leakage warning).
NO_GAP is inconclusive and exits non-zero: it never counts toward gate G1.

    uv run python scripts/leakage_canary.py bodmas --nT 3 --nE 6
    uv run python scripts/leakage_canary.py lamda --nT 4 --nE 12 --max-windows 3

Exit code: 0 PASS, 1 FAIL, 2 cannot be computed, 3 NO_GAP (inconclusive: not a pass).

Limit: the canary sees a leak only when it closes the gap between the time-aware AUT and
the random-split F1. A small leak that leaves the gap above the band is caught by C1-C3
and the oracle tests, not by this script.

Phase 4 runs this on the real caches with the windows of the accepted ADR-0005. It was
deliberately not run on real data before that ADR was accepted: windows must not be chosen
after looking at real AUT. Results go to results/canary/ (not committed); numbers from this
script enter the report only through docs/CLAIMS.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from driftwatch.data.canary import CanaryError, run_canary
from driftwatch.data.memory import MemoryCapExceeded, MemoryWatchdog
from driftwatch.data.presets import PRESETS, cached_source
from driftwatch.data.slicer import WindowSpec

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("dataset", choices=sorted(PRESETS))
    parser.add_argument("--root", type=Path, default=Path("data"), help="data root")
    parser.add_argument("--length", help="slot length override (default: the ADR-0004 preset)")
    parser.add_argument("--nT", type=int, required=True, help="training slots per window")
    parser.add_argument("--nE", type=int, required=True, help="evaluation slots per window")
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--ratio", type=float, default=0.10, help="target malware ratio (C3)")
    parser.add_argument("--min-malware", type=int, default=50, help="size gate M")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-windows", type=int, default=3, help="windows spread over the run")
    parser.add_argument("--min-gap", type=float, default=0.05)
    parser.add_argument("--min-closure", type=float, default=0.5)
    parser.add_argument("--memory-cap-gb", type=float, default=1.5)
    parser.add_argument("--out", type=Path, help="JSON result (default results/canary/...)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    spec = WindowSpec(
        nT=args.nT,
        nE=args.nE,
        stride=args.stride,
        target_ratio=args.ratio,
        min_malware=args.min_malware,
        seed=args.seed,
    )
    overrides = {"length": args.length} if args.length else {}
    source = cached_source(args.dataset, args.root, **overrides)
    try:
        with MemoryWatchdog(int(args.memory_cap_gb * 1024**3)) as watchdog:
            result = run_canary(
                source,
                spec,
                seed=args.seed,
                max_windows=args.max_windows,
                min_gap=args.min_gap,
                min_closure=args.min_closure,
            )
    except CanaryError as exc:
        print(f"canary cannot be computed: {exc}", file=sys.stderr)
        return 2
    except MemoryCapExceeded as exc:
        print(f"memory cap exceeded: {exc}", file=sys.stderr)
        return 2

    record = result.as_record()
    record.update(
        dataset=args.dataset,
        spec=spec.to_dict(),
        spec_digest=spec.digest(),
        source=source.provenance(),
        memory=watchdog.as_record(),
    )
    out = args.out or ROOT / "results" / "canary" / f"{args.dataset}-{spec.digest()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(record, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )

    print(f"dataset {args.dataset}, {result.n_windows} window(s), spec {spec.digest()}")
    print(f"  AUT with true timestamps     {result.aut_true:.3f}")
    print(f"  AUT with shuffled timestamps {result.aut_shuffled:.3f}")
    print(f"  random-split F1              {result.f1_random:.3f}")
    closure = "n/a" if result.closure is None else f"{result.closure:.2f}"
    label = "INCONCLUSIVE (NO_GAP)" if result.verdict == "NO_GAP" else result.verdict
    print(f"  gap {result.gap:.3f}, closure {closure}  ->  {label}")
    if result.verdict == "NO_GAP":
        print("  no gap to close: nothing decays, or something leaks. This is not a pass.")
    if result.leakage_warning:
        print("  WARNING: time-aware AUT above 0.9: possible leakage (guide section 9)")
    print(f"  wrote {out}")
    return {"PASS": 0, "FAIL": 1, "NO_GAP": 3}[result.verdict]


if __name__ == "__main__":
    raise SystemExit(main())
