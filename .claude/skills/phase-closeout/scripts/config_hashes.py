"""Print SHA-256 hashes of every run config (configs/**/*.yaml) and of uv.lock.

Usage: python .claude/skills/phase-closeout/scripts/config_hashes.py [--root PATH]

The output is a Markdown table for the phase's entry in docs/PHASES.md, so a
later reader can tell whether a stored result came from the config as it is now.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_hashes(root: Path) -> list[tuple[str, str]]:
    files = sorted((root / "configs").rglob("*.yaml")) + sorted((root / "configs").rglob("*.yml"))
    return [(p.relative_to(root).as_posix(), sha256(p)) for p in sorted(files)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    rows = config_hashes(args.root)
    lock = args.root / "uv.lock"
    if lock.is_file():
        rows.append(("uv.lock", sha256(lock)))
    print("| File | SHA-256 |\n|---|---|")
    for name, digest in rows:
        print(f"| {name} | `{digest}` |")
    if not any(name.startswith("configs/") for name, _ in rows):
        print("\n(no configs/*.yaml yet)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
