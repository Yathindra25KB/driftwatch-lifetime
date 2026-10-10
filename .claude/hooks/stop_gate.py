"""Stop gate for DriftWatch (Claude Code hook; stdlib only).

When Claude tries to finish, run the fast tests (the `slow` marker is excluded
by pytest's addopts).

- `stop_hook_active` is true: exit 0 at once, so the gate can never loop.
- Tests red: a short failure summary on stderr, exit 2 (Claude keeps working).
- Tests green: exit 0. No tests collected (pytest exit 5): green, with a note.
- The run is capped at CAP_SECONDS; hitting the cap blocks once with a note.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

CAP_SECONDS = 120
SUMMARY_LINES = 20


def main(stdin_text: str | None = None, cap: int = CAP_SECONDS) -> int:
    if stdin_text is None:
        stdin_text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(stdin_text)
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    if payload.get("stop_hook_active") is True:
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd())
    command = [sys.executable, "-m", "pytest", "-q", "-x", "--tb=line", "-p", "no:cacheprovider"]
    try:
        result = subprocess.run(
            command,
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=cap,
        )
    except subprocess.TimeoutExpired:
        print(
            f"Stop gate: fast tests exceeded the {cap} s cap. Mark long tests `slow` or fix the "
            "hang before finishing.",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(f"Stop gate: could not run pytest ({exc}).", file=sys.stderr)
        return 2
    if result.returncode == 0:
        return 0
    if result.returncode == 5:
        print("Stop gate: no tests collected; treated as green.", file=sys.stderr)
        return 0
    tail = (result.stdout + result.stderr).strip().splitlines()[-SUMMARY_LINES:]
    print("Stop gate: fast tests are failing; fix them before finishing.", file=sys.stderr)
    print("\n".join(tail), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
