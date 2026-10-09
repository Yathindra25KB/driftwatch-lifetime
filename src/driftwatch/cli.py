"""Command-line entry point `driftwatch`.

Only `--version` exists in Phase 1. Later phases add `data verify` (Phase 2),
`run` (Phase 4), `grid` (Phase 6) and `reproduce table1` (Phase 7).
"""

import argparse

from driftwatch import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driftwatch",
        description="Time-aware malware-detector lifetime study (pre-release).",
    )
    parser.add_argument("--version", action="version", version=f"driftwatch {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
