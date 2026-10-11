"""SessionStart(compact) re-injection for DriftWatch (Claude Code hook; stdlib only).

After a compaction, prints to stdout (which Claude Code adds to the context):
the hard rules and stop rules from CLAUDE.md, the current phase (git branch
and the IN PROGRESS row of docs/PHASES.md) and the status of every phase.
Output stays well under Claude Code's 10,000-character limit. Always exits 0.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

MAX_CHARS = 8000


def section(text: str, heading: str) -> str:
    """Body of the first `## <heading>...` section, without the heading line."""
    lines, inside, body = text.splitlines(), False, []
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].startswith(heading)
            continue
        if inside:
            body.append(line)
    return "\n".join(body).strip()


def phase_rows(phases_md: str) -> list[list[str]]:
    rows = []
    for line in section(phases_md, "Phases").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].isdigit():
            rows.append(cells)
    return rows


def branch(project: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(project), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def build(project: Path) -> str:
    parts = ["DriftWatch context re-injected after compaction (SessionStart hook)."]
    try:
        claude = (project / "CLAUDE.md").read_text(encoding="utf-8")
        parts += ["## Hard rules", section(claude, "Hard rules"), "## Stop rules"]
        parts.append(section(claude, "Stop rules"))
    except OSError:
        parts.append("CLAUDE.md could not be read; re-read it before continuing.")
    parts.append(f"## Current phase\nBranch: {branch(project)}")
    try:
        rows = phase_rows((project / "docs" / "PHASES.md").read_text(encoding="utf-8"))
        current = [f"Phase {r[0]}: {r[1]}" for r in rows if len(r) > 4 and r[4] == "IN PROGRESS"]
        parts.append("In progress: " + (", ".join(current) or "none recorded"))
        parts.append("## Phase status (docs/PHASES.md)")
        parts += [f"- {r[0]} {r[1]}: {r[4]}" + (f" ({r[6]})" if r[6] else "") for r in rows]
    except (OSError, IndexError):
        parts.append("docs/PHASES.md could not be read; re-read it before continuing.")
    parts.append(
        "Before continuing: re-read docs/PHASES.md and the current prompt in docs/prompts/."
    )
    return "\n".join(parts)[:MAX_CHARS]


def main(stdin_text: str | None = None) -> int:
    try:
        if stdin_text is None:
            stdin_text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(stdin_text)
        except ValueError:
            payload = {}
        cwd = payload.get("cwd") if isinstance(payload, dict) else None
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd or os.getcwd())
        text = build(project)
    except Exception as exc:  # noqa: BLE001 - re-injection must never break a session
        text = f"DriftWatch re-injection failed ({type(exc).__name__}); re-read CLAUDE.md."
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
