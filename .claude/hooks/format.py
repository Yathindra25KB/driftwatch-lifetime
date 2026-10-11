"""PostToolUse formatter for DriftWatch (Claude Code hook; stdlib only).

After an Edit or Write on a Python file inside the project, runs
`ruff check --fix` and then `ruff format` on that file with the project's
locked ruff. It never fails the tool call: it always exits 0 and reports
problems on stderr only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 20


def target_file(payload: dict) -> tuple[Path, Path] | None:
    tool_input = payload.get("tool_input")
    text = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(text, str) or not text.endswith((".py", ".pyi")):
        return None
    cwd = Path(payload.get("cwd") or os.getcwd())
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or cwd).resolve()
    path = Path(text)
    path = (path if path.is_absolute() else cwd / path).resolve()
    if not path.is_file() or not path.is_relative_to(project):
        return None
    return path, project


def main(stdin_text: str | None = None) -> int:
    try:
        if stdin_text is None:
            stdin_text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        payload = json.loads(stdin_text)
        found = target_file(payload) if isinstance(payload, dict) else None
        if found is None:
            return 0
        path, project = found
        for args in (["check", "--fix", "--exit-zero", "--quiet"], ["format", "--quiet"]):
            subprocess.run(
                [sys.executable, "-m", "ruff", *args, str(path)],
                cwd=project,
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
            )
    except Exception as exc:  # noqa: BLE001 - a formatter must never fail the tool call
        print(f"DriftWatch formatter: skipped ({type(exc).__name__}: {exc})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
