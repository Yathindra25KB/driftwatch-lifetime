"""Cross-check: E4's periodic arm reproduces E3's random arm exactly. No model fits.

    uv run python scripts/check_e4_vs_e3.py

E4's periodic cells use the E3 conformal path with the random selector, reserved share 0.20,
probability score and budget 1% (docs/prereg/addendum-v3.md), so their stored predictions
must equal those of the E3 random cells at the same delay, budget and seeds, although they
ran at a later code version. The check compares ``predictions_sha256`` from each cell's
``run.json`` (which covers predictions only, not the code version) and writes
``reports/tables/e4_e3_crosscheck.csv``. A mismatch exits non-zero.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ("lamda", "bodmas")
SEED_TAGS = ("s0-4", "s5-9")


def run_record(cell_dir: Path) -> dict | None:
    done = [p for p in cell_dir.glob("*/run.json")
            if json.loads(p.read_text(encoding="utf-8")).get("status") == "complete"]  # fmt: skip
    return json.loads(done[0].read_text(encoding="utf-8")) if len(done) == 1 else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--e3", type=Path, default=ROOT / "results" / "e3")
    ap.add_argument("--e4", type=Path, default=ROOT / "results" / "e4")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "tables")
    args = ap.parse_args(argv)
    rows = []
    for ds in DATASETS:
        for d in (0, 3):
            for tag in SEED_TAGS:
                e4 = run_record(args.e4 / ds / f"e4-periodic-d{d}-b1-{tag}")
                e3 = run_record(args.e3 / ds / f"e3-random-d{d}-b1-r0.2-probability-{tag}")
                status = (
                    "missing" if e4 is None or e3 is None
                    else "match" if e4["predictions_sha256"] == e3["predictions_sha256"]
                    else "MISMATCH"
                )  # fmt: skip
                rows.append({
                    "dataset": ds, "delay": d, "budget_pct": 1.0, "seeds": tag, "status": status,
                    "e4_code_version": None if e4 is None else e4["code_version"],
                    "e3_code_version": None if e3 is None else e3["code_version"],
                    "predictions_sha256": None if e4 is None else e4["predictions_sha256"],
                })  # fmt: skip
    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "e4_e3_crosscheck.csv", index=False, lineterminator="\n")
    print(df.to_string(index=False))
    return 1 if (df["status"] == "MISMATCH").any() else 0


if __name__ == "__main__":
    raise SystemExit(main())
