"""Regenerate the committed synthetic fixture: `uv run python scripts/make_fixture.py`."""

import shutil
from pathlib import Path

from driftwatch.data.fixture import write_fixture

TARGET = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic"

if __name__ == "__main__":
    if (TARGET / "raw").exists():
        shutil.rmtree(TARGET / "raw")
    write_fixture(TARGET)
    size = sum(p.stat().st_size for p in TARGET.rglob("*") if p.is_file())
    print(f"fixture written to {TARGET} ({size / 1024:.0f} KB)")
