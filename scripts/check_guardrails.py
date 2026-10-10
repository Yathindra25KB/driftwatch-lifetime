"""Demonstrate that every DriftWatch guardrail fires, without touching the real repository.

Usage: uv run python scripts/check_guardrails.py

Builds a throwaway git repository in a temporary folder, copies the guardrail
files into it, and drives each hook through the exact command string that
.claude/settings.json gives Claude Code (bash -> uv run -> hook script), with
CLAUDE_PROJECT_DIR pointing at the temporary repository. Also checks that the
settings, hooks, agents and skill match the documented schema (ADR-0001), times
every hook call, and confirms the real repository's git status is unchanged.
Prints a pass/fail table and exits 1 if any scenario fails. Runs on Windows and
Linux, locally and in CI.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / ".claude" / "settings.json"
GIT = ["git", "-c", "user.name=guardrail-check", "-c", "user.email=check@example.invalid"]
GIT += ["-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", "-c", "core.autocrlf=false"]

# Documented facts (ADR-0001, code.claude.com docs accessed 2026-10-10).
TOOL_NAMES = {"Edit", "Write", "NotebookEdit", "Bash", "PowerShell", "Read", "Glob", "Grep"}
TOOL_NAMES |= {"WebFetch", "WebSearch", "Agent", "Skill"}
EVENTS = {"PreToolUse", "PostToolUse", "Stop", "SessionStart", "PreCompact", "PostCompact"}
HANDLER_FIELDS = {"type", "command", "args", "shell", "timeout", "if", "statusMessage", "async"}
RULE_RE = re.compile(r"^(?P<tool>[A-Za-z]+)(\((?P<spec>.+)\))?$")


@dataclass
class Report:
    rows: list[tuple[str, str, str, bool]] = field(default_factory=list)
    timings: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def check(self, name: str, expected: str, got: str, ok: bool) -> None:
        self.rows.append((name, expected, got, ok))


# --- hook invocation exactly as settings.json defines it ---------------------------------


def find_bash() -> str | None:
    if os.name == "nt":  # Claude Code uses Git Bash; System32\bash.exe is the WSL launcher.
        candidates = []
        git = shutil.which("git")
        if git:
            git_root = Path(git).resolve().parents[1]
            candidates += [git_root / "bin" / "bash.exe", git_root / "usr" / "bin" / "bash.exe"]
        candidates += [Path(r"C:\Program Files\Git\bin\bash.exe")]
        return next((str(c) for c in candidates if c.is_file()), None)
    return shutil.which("bash")


def hook_command(settings: dict, event: str, tool: str | None = None) -> str:
    for group in settings["hooks"][event]:
        matcher = group.get("matcher", "")
        if event == "SessionStart" and matcher != "compact":
            continue
        if tool is None or tool in matcher.split("|"):
            return group["hooks"][0]["command"]
    raise KeyError(f"no {event} hook for {tool}")


def run_hook(
    report: Report, label: str, command: str, payload: dict | str, project: Path, bash: str | None
) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["UV_PROJECT_ENVIRONMENT"] = (
        sys.prefix
    )  # reuse this venv read-only; --no-sync never edits it
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    if bash:
        argv = [bash, "-c", command]
    else:  # no bash: run the script directly with this interpreter
        script = re.search(r"\.claude/hooks/\w+\.py", command).group(0)  # type: ignore[union-attr]
        argv = [
            sys.executable,
            str(project / script),
            *(["--reviewer-bash"] * ("--reviewer-bash" in command)),
        ]
    start = time.perf_counter()
    result = subprocess.run(
        argv, input=stdin.encode("utf-8"), capture_output=True, env=env, cwd=project, timeout=300
    )
    report.timings[label].append((time.perf_counter() - start) * 1000)
    return result


# --- temporary repository ----------------------------------------------------------------


def git(repo: Path, *args: str) -> str:
    out = subprocess.run([*GIT, "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return out.stdout


def build_repo(tmp: Path) -> Path:
    repo = tmp / "repo"
    repo.mkdir()
    shutil.copytree(
        ROOT / ".claude", repo / ".claude", ignore=shutil.ignore_patterns("__pycache__")
    )
    for rel in ("CLAUDE.md", "pyproject.toml", ".gitignore", ".gitattributes", "docs/PHASES.md"):
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, repo / rel)
    files = {
        "docs/PREREG.md": "# PREREG\n\nRQ1: registered text\n",
        "tests/golden/expected.csv": "slot,f1\n1,0.9\n",
        "tests/test_ok.py": "def test_ok():\n    assert True\n",
        "src/keep.py": "x = 1\n",
    }
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text, encoding="utf-8", newline="\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "temp repo for guardrail check")
    (repo / "data").mkdir()
    (repo / "data" / "raw.bin").write_bytes(b"\x00feature-file-stand-in")
    return repo


# --- schema checks -----------------------------------------------------------------------


def schema_checks(report: Report, settings: dict) -> None:
    perms = settings.get("permissions", {})
    rules = [(kind, r) for kind in ("deny", "ask", "allow") for r in perms.get(kind, [])]
    bad = [
        r for _, r in rules if not RULE_RE.match(r) or RULE_RE.match(r)["tool"] not in TOOL_NAMES
    ]
    report.check(
        "settings: permission rules use documented Tool(spec) syntax",
        "none bad",
        str(bad or "none bad"),
        not bad,
    )
    ignored = [r for _, r in rules if r.startswith(("Write(", "MultiEdit(", "NotebookEdit("))]
    report.check(
        "settings: no path rules Claude Code never consults (F5)",
        "none",
        str(ignored or "none"),
        not ignored,
    )
    bash_deny = [r for r in perms.get("deny", []) if r.startswith("Bash")]
    report.check(
        "settings: no Bash deny rule (would disable PowerShell, F4)",
        "none",
        str(bash_deny or "none"),
        not bash_deny,
    )
    twins = []
    for kind in ("ask", "allow"):
        for r in perms.get(kind, []):
            if r.startswith("Bash(") and "PowerShell(" + r[5:] not in perms.get(kind, []):
                twins.append(r)
    report.check(
        "settings: every Bash ask/allow rule has a PowerShell twin (F4)",
        "none missing",
        str(twins or "none missing"),
        not twins,
    )
    secrets = {"Read(**/.env)", "Read(**/secrets/**)", "Edit(/data/**)"} <= set(
        perms.get("deny", [])
    )
    report.check(
        "settings: secrets read and data/ edit denied",
        "denied",
        "denied" if secrets else "missing",
        secrets,
    )

    problems = []
    hooks = settings.get("hooks", {})
    for event, groups in hooks.items():
        if event not in EVENTS:
            problems.append(f"unknown event {event}")
        for group in groups:
            for tool in filter(None, group.get("matcher", "").split("|")):
                if event in ("PreToolUse", "PostToolUse") and tool not in TOOL_NAMES:
                    problems.append(f"{event} matcher names unknown tool {tool}")
            for handler in group.get("hooks", []):
                extra = set(handler) - HANDLER_FIELDS
                cmd = handler.get("command", "")
                script = re.search(r"\.claude/hooks/\w+\.py", cmd)
                if extra:
                    problems.append(f"{event}: undocumented fields {sorted(extra)}")
                if handler.get("type") != "command" or handler.get("shell") != "bash":
                    problems.append(f"{event}: handler must be a bash command")
                if not isinstance(handler.get("timeout"), int):
                    problems.append(f"{event}: missing integer timeout (timeouts fail open, F13)")
                if '"$CLAUDE_PROJECT_DIR' not in cmd:
                    problems.append(
                        f"{event}: command not anchored on quoted $CLAUDE_PROJECT_DIR (F14)"
                    )
                if not script or not (ROOT / script.group(0)).is_file():
                    problems.append(
                        f"{event}: hook script missing (missing scripts fail open, F13)"
                    )
    pre = {t for g in hooks.get("PreToolUse", []) for t in g.get("matcher", "").split("|")}
    if not {"Edit", "Write", "NotebookEdit", "Bash", "PowerShell"} <= pre:
        problems.append(
            "PreToolUse guard does not cover Edit, Write, NotebookEdit, Bash, PowerShell"
        )
    if not any(g.get("matcher") == "compact" for g in hooks.get("SessionStart", [])):
        problems.append("no SessionStart hook with matcher compact")
    report.check(
        "settings: hooks match the documented schema",
        "no problems",
        "; ".join(problems) or "no problems",
        not problems,
    )

    for path in sorted((ROOT / ".claude" / "hooks").glob("*.py")):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
            ok = True
        except SyntaxError:
            ok = False
        report.check(
            f"hook file parses: {path.name}", "parses", "parses" if ok else "syntax error", ok
        )

    agent_problems = []
    for agent in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        fm = agent.read_text(encoding="utf-8").split("---\n")[1]
        tools = set(map(str.strip, re.search(r"^tools: (.+)$", fm, re.M).group(1).split(",")))
        if not tools <= {"Read", "Grep", "Glob", "Bash"} or "--reviewer-bash" not in fm:
            agent_problems.append(agent.name)
    report.check(
        "agents: reviewers are read-only (Bash limited to tests)",
        "read-only",
        str(agent_problems or "read-only"),
        not agent_problems,
    )
    skill = (ROOT / ".claude" / "skills" / "phase-closeout" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    ok = skill.startswith("---\nname: phase-closeout\ndescription:")
    report.check(
        "skill: phase-closeout frontmatter has name and description",
        "valid",
        "valid" if ok else "invalid",
        ok,
    )
    lines = len((ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
    report.check("CLAUDE.md under 200 lines", "< 200", str(lines), lines < 200)


# --- behaviour checks --------------------------------------------------------------------


def behaviour_checks(report: Report, settings: dict, repo: Path, bash: str | None) -> None:
    guard_cmd = hook_command(settings, "PreToolUse", "Bash")

    def guard(name: str, payload: dict | str, expect: int) -> None:
        if isinstance(payload, dict):
            payload = {**payload, "cwd": str(repo), "hook_event_name": "PreToolUse"}
        r = run_hook(report, "guard (PreToolUse)", guard_cmd, payload, repo, bash)
        verdict = {0: "allowed", 2: "blocked"}
        reason = r.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        got = f"{verdict.get(r.returncode, f'exit {r.returncode}')}" + (
            f" ({reason[0][:60]})" if r.returncode == 2 else ""
        )
        report.check(name, verdict[expect], got, r.returncode == expect)

    prereg = str(repo / "docs" / "PREREG.md")
    edit = {
        "tool_name": "Edit",
        "tool_input": {"file_path": prereg, "old_string": "registered", "new_string": "changed"},
    }
    guard("PREREG edit before any prereg tag", edit, 0)
    git(repo, "tag", "prereg-v1")
    guard("PREREG edit after temporary prereg-v1 tag", edit, 2)
    guard(
        "PREREG edit via traversal docs/../docs/PREREG.md",
        {**edit, "tool_input": {**edit["tool_input"], "file_path": "docs/../docs/PREREG.md"}},
        2,
    )
    write_same = {
        "tool_name": "Write",
        "tool_input": {"file_path": prereg, "content": "# PREREG\n\nRQ1: registered text\n"},
    }
    guard("PREREG Write identical to tagged blob", write_same, 0)
    for cmd in (
        "sed -i s/RQ1/RQ9/ docs/PREREG.md",
        "echo x > docs/PREREG.md",
        "git tag -d prereg-v1",
    ):
        guard(f"shell write/untag: {cmd}", {"tool_name": "Bash", "tool_input": {"command": cmd}}, 2)
    guard(
        "PowerShell write: Set-Content docs\\PREREG.md",
        {"tool_name": "PowerShell", "tool_input": {"command": "Set-Content docs\\PREREG.md x"}},
        2,
    )
    golden = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "tests/golden/expected.csv",
            "old_string": "0.9",
            "new_string": "0.8",
        },
    }
    guard("committed golden file edit", golden, 2)
    for cmd in (
        "git push --force",
        "git push -f origin main",
        "git push origin +main",
        "git push --force-with-lease",
        "git push -uf origin main",
    ):
        guard(f"force push: {cmd}", {"tool_name": "Bash", "tool_input": {"command": cmd}}, 2)
    guard(
        "force push in PowerShell: git push -f",
        {"tool_name": "PowerShell", "tool_input": {"command": "git push -f"}},
        2,
    )
    guard(
        "normal push: git push -u origin main",
        {"tool_name": "Bash", "tool_input": {"command": "git push -u origin main"}},
        0,
    )
    guard(
        "git add data/raw.bin",
        {"tool_name": "Bash", "tool_input": {"command": "git add data/raw.bin"}},
        2,
    )
    guard(
        "git add -f data/raw.bin",
        {"tool_name": "Bash", "tool_input": {"command": "git add -f data/raw.bin"}},
        2,
    )
    guard(
        "git add -A while data/ is git-ignored",
        {"tool_name": "Bash", "tool_input": {"command": "git add -A"}},
        0,
    )
    guard(
        "recursive delete: rm -rf src",
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf src"}},
        2,
    )
    guard(
        "recursive delete: rm -rf .pytest_cache",
        {"tool_name": "Bash", "tool_input": {"command": "rm -rf .pytest_cache"}},
        0,
    )
    guard(
        "download from unlisted host",
        {"tool_name": "Bash", "tool_input": {"command": "curl -O https://example.com/x"}},
        2,
    )
    guard("malformed hook JSON", "{not json", 2)

    reviewer_cmd = guard_cmd.replace('guard.py"', 'guard.py" --reviewer-bash')
    for cmd, expect in (("uv run pytest -q", 0), ("rm notes.txt", 2)):
        r = run_hook(
            report,
            "guard --reviewer-bash",
            reviewer_cmd,
            {"tool_name": "Bash", "tool_input": {"command": cmd}},
            repo,
            bash,
        )
        report.check(
            f"reviewer subagent Bash: {cmd}",
            "allowed" if expect == 0 else "blocked",
            f"exit {r.returncode}",
            r.returncode == expect,
        )

    ugly = repo / "src" / "ugly.py"
    ugly.write_text("import os\nx=[1,2 ,3]\n", encoding="utf-8")
    r = run_hook(
        report,
        "format (PostToolUse)",
        hook_command(settings, "PostToolUse", "Write"),
        {"tool_name": "Write", "tool_input": {"file_path": str(ugly)}, "cwd": str(repo)},
        repo,
        bash,
    )
    text = ugly.read_text(encoding="utf-8")
    report.check(
        "formatter ran (ruff check --fix + format)",
        "x = [1, 2, 3]",
        repr(text.strip()),
        r.returncode == 0 and text == "x = [1, 2, 3]\n",
    )

    stop_cmd = hook_command(settings, "Stop")
    red = repo / "tests" / "test_red.py"
    red.write_text("def test_deliberately_failing():\n    assert 1 == 2\n", encoding="utf-8")
    r = run_hook(
        report,
        "stop_gate (Stop)",
        stop_cmd,
        {"stop_hook_active": False, "cwd": str(repo)},
        repo,
        bash,
    )
    err = r.stderr.decode("utf-8", "replace")
    report.check(
        "Stop gate refuses while a test fails",
        "exit 2 + summary",
        f"exit {r.returncode}",
        r.returncode == 2 and "failing" in err,
    )
    r = run_hook(
        report,
        "stop_gate (Stop)",
        stop_cmd,
        {"stop_hook_active": True, "cwd": str(repo)},
        repo,
        bash,
    )
    report.check(
        "Stop gate does not loop (stop_hook_active=true)",
        "exit 0",
        f"exit {r.returncode}",
        r.returncode == 0,
    )
    red.unlink()
    r = run_hook(
        report,
        "stop_gate (Stop)",
        stop_cmd,
        {"stop_hook_active": False, "cwd": str(repo)},
        repo,
        bash,
    )
    report.check(
        "Stop gate passes when tests are green", "exit 0", f"exit {r.returncode}", r.returncode == 0
    )

    r = run_hook(
        report,
        "reinject (SessionStart compact)",
        hook_command(settings, "SessionStart"),
        {"source": "compact", "cwd": str(repo)},
        repo,
        bash,
    )
    out = r.stdout.decode("utf-8", "replace")
    ok = (
        r.returncode == 0
        and "Hard rules" in out
        and "In progress: Phase 1" in out
        and len(out) < 10_000
    )
    report.check(
        "SessionStart(compact) re-injects rules and phase",
        "rules + phase",
        f"exit {r.returncode}, {len(out)} chars",
        ok,
    )


# --- main --------------------------------------------------------------------------------


def real_status() -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain", "--ignored"],
        capture_output=True,
        text=True,
    ).stdout


def main() -> int:
    report = Report()
    before = real_status()
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    schema_checks(report, settings)
    bash = find_bash()
    report.check(
        "Git Bash/bash available for hook commands",
        "found",
        bash or "not found (direct mode)",
        True,
    )
    with tempfile.TemporaryDirectory(
        prefix="driftwatch-guardrails-", ignore_cleanup_errors=True
    ) as tmp:
        repo = build_repo(Path(tmp))
        behaviour_checks(report, settings, repo, bash)
    report.check(
        "real repository unchanged",
        "same git status",
        "same" if real_status() == before else "CHANGED",
        real_status() == before,
    )

    width = max(len(r[0]) for r in report.rows)
    print(f"{'#':>3}  {'scenario':<{width}}  result  expected -> got")
    for i, (name, expected, got, ok) in enumerate(report.rows, 1):
        print(f"{i:>3}  {name:<{width}}  {'PASS' if ok else 'FAIL':6}  {expected} -> {got}")
    print("\nHook latency through the settings.json command (bash -> uv run -> python), ms:")
    for label, values in report.timings.items():
        median, worst = statistics.median(values), max(values)
        print(f"  {label:<34} calls {len(values):>3}  median {median:7.0f}  max {worst:7.0f}")
    failed = sum(not ok for *_, ok in report.rows)
    print(f"\n{len(report.rows) - failed}/{len(report.rows)} scenarios passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
