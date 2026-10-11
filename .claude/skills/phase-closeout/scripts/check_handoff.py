"""Check that every artifact in a phase prompt's HANDOFF list exists.

Usage: python .claude/skills/phase-closeout/scripts/check_handoff.py NN [--root PATH]

Reads docs/prompts/phase-NN.md, takes the "- " items under "## HANDOFF",
splits comma lists, strips "(notes)", expands "phase-01.md to phase-12.md"
ranges, and prints a table. Exit 1 if anything is missing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RANGE_RE = re.compile(r"^(?P<stem>.*?phase-)(?P<a>\d+)\.md to phase-(?P<b>\d+)\.md$")


def handoff_items(prompt_text: str) -> list[str]:
    items: list[str] = []
    inside = False
    for line in prompt_text.splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## HANDOFF"
            continue
        if not inside or not line.startswith("- "):
            continue
        entry = re.sub(r"\s*\([^)]*\)", "", line[2:])
        for part in (p.strip() for p in entry.split(",")):
            m = RANGE_RE.match(part)
            if m:
                width = len(m.group("a"))
                for n in range(int(m.group("a")), int(m.group("b")) + 1):
                    items.append(f"{m.group('stem')}{n:0{width}d}.md")
            elif part:
                items.append(part)
    return items


def missing(items: list[str], root: Path) -> list[str]:
    absent = []
    for item in items:
        path = root / item
        ok = path.is_dir() if item.endswith("/") else path.exists()
        if not ok:
            absent.append(item)
    return absent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phase", type=int)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    prompt = args.root / "docs" / "prompts" / f"phase-{args.phase:02d}.md"
    items = handoff_items(prompt.read_text(encoding="utf-8"))
    absent = set(missing(items, args.root))
    print(f"HANDOFF check for {prompt.as_posix()}: {len(items)} items")
    for item in items:
        print(f"  {'MISSING' if item in absent else 'ok':7s}  {item}")
    print("All HANDOFF artifacts exist." if not absent else f"{len(absent)} missing.")
    return 1 if absent else 0


if __name__ == "__main__":
    sys.exit(main())
