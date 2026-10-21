"""Regenerate the committed synthetic fixture: `uv run python scripts/make_fixture.py`.

The fixture is seeded, so regenerating it leaves the committed files byte-identical; a diff
means the generator changed. It replaces `tests/fixtures/synthetic/raw`, so run it with a clean
working tree. `--help` only prints this text.
"""

import argparse
import shutil
from pathlib import Path

from driftwatch.data.fixture import write_fixture

TARGET = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthetic"


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.split("\n\n")[0]).parse_args(argv)
    if (TARGET / "raw").exists():
        shutil.rmtree(TARGET / "raw")
    write_fixture(TARGET)
    size = sum(p.stat().st_size for p in TARGET.rglob("*") if p.is_file())
    print(f"fixture written to {TARGET} ({size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
