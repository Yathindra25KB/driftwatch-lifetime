"""Reproduce Table 1 (E0 baselines on BODMAS): wraps `driftwatch reproduce table1`.

    uv sync --frozen
    uv run python scripts/reproduce_table1.py            # full: data, run, compare (about 20 min)
    uv run python scripts/reproduce_table1.py --smoke    # fixture, a few minutes, for CI

Exit codes: 0 match, 1 mismatch, 2 cannot run, 3 the data download needs the manual path
(docs/data_cards/bodmas.md). The report is written to reports/reproduction/.
"""

from __future__ import annotations

import sys

from driftwatch.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["reproduce", "table1", *sys.argv[1:]]))
