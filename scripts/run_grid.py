"""Run the E2 grid: a thin wrapper around ``driftwatch grid`` (same arguments).

    uv run python scripts/run_grid.py configs/e2_bodmas.yaml --smoke
    uv run python scripts/run_grid.py configs/e2_bodmas.yaml --chunk 1/3

See docs/GRID.md for chunks, the ledger and the Kaggle/Colab path.
"""

from __future__ import annotations

import sys

from driftwatch.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["grid", *sys.argv[1:]]))
