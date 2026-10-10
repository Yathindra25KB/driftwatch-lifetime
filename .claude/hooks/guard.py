"""PreToolUse guard for DriftWatch (Claude Code hook; stdlib only).

Reads the hook JSON on stdin. Exit 2 with a reason on stderr blocks the tool call;
exit 0 allows it. It blocks:

- changes to docs/PREREG.md once any prereg-vN tag exists (the proposed content
  must equal the blob at the highest tag), and to docs/prereg/addendum-vN.md
  once prereg-vN exists; deleting or moving prereg tags;
- edits to tests/golden/ files already committed at HEAD;
- edits inside .git/ and to Claude Code settings files other than the project's
  .claude/settings.json (which the `ask` permission rule gates);
- shell writes that mention a locked path, literally, through quotes or through
  a glob, or that touch .git/ or .claude/{settings*,hooks,agents};
- force or destructive pushes (-f, --force, --force-with-lease, +refspec, ...),
  including through git aliases;
- staging anything under data/ or results/ (except data/manifest.json) with
  `git add`, `git update-index` or `git commit <paths>`;
- recursive deletes outside temporary folders and project caches (including
  `pytest --basetemp`);
- downloads from hosts outside ALLOWED_HOSTS.

Crash policy: malformed input fails closed (exit 2). An internal error fails
closed when the call mentions a protected operation and is allowed (exit 0)
with a warning otherwise. `--reviewer-bash` mode lets read-only reviewer
subagents run only `uv run pytest` with test-selection options. Design,
review findings and residual risks: ADR-0001, docs/reviews/guardrail-review.md.
"""

from __future__ import annotations

import base64
import contextlib
import fnmatch
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ALLOWED_HOSTS = frozenset(
    {
        "pypi.org",
        "files.pythonhosted.org",
        "test.pypi.org",
        "test-files.pythonhosted.org",
        "github.com",
        "api.github.com",
        "codeload.github.com",
        "astral.sh",
        "code.claude.com",
        "docs.anthropic.com",
        # Published Claude Code settings schema, linked from the official settings docs.
        "json.schemastore.org",
        # Phase 2 dataset sources (ADR-0001, Phase 2 CHANGE_REQUEST): LAMDA on Hugging Face,
        # BODMAS on the Google Drive folder its authors publish. No other Google host.
        "huggingface.co",
        "drive.google.com",
        "drive.usercontent.google.com",
    }
)
# Hugging Face serves files from cdn-lfs*.huggingface.co and its Xet storage under *.hf.co.
ALLOWED_HOST_SUFFIXES = (".githubusercontent.com", ".huggingface.co", ".hf.co")

CACHE_DIRS = frozenset(
    {".pytest_cache", ".ruff_cache", "__pycache__", ".hypothesis", ".mypy_cache", "build", "dist"}
    | {"htmlcov"}
)

READ_ONLY_PROGRAMS = frozenset(
    {
        "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg", "wc", "diff",
        "cmp", "sha256sum", "sha1sum", "md5sum", "file", "stat", "ls", "dir", "echo", "printf",
        "type", "findstr", "nl", "od", "xxd", "cut", "basename", "dirname", "realpath",
        "readlink", "pwd", "get-content", "gc", "select-string", "sls", "get-filehash",
        "get-item", "gi", "get-childitem", "gci", "test-path", "format-hex", "measure-object",
        "write-output", "write-host", "select-object", "where-object", "compare-object",
        "check-jsonschema", "cd", "chdir", "pushd", "popd", "set-location", "sl",
    }
)  # fmt: skip
# git subcommands that cannot change a working-tree file's content.
SAFE_GIT_FOR_LOCKED = frozenset(
    {"diff", "log", "show", "status", "blame", "ls-files", "ls-tree", "cat-file", "rev-parse"}
    | {"grep", "shortlog", "describe", "commit", "add", "tag", "push", "hash-object"}
)
KNOWN_GIT = frozenset(
    [
        "add",
        "am",
        "apply",
        "archive",
        "bisect",
        "blame",
        "branch",
        "bundle",
        "cat-file",
        "checkout",
        "cherry-pick",
        "clean",
        "clone",
        "commit",
        "config",
        "describe",
        "diff",
        "difftool",
        "fetch",
        "for-each-ref",
        "format-patch",
        "gc",
        "grep",
        "hash-object",
        "help",
        "init",
        "log",
        "ls-files",
        "ls-remote",
        "ls-tree",
        "maintenance",
        "merge",
        "mergetool",
        "mv",
        "notes",
        "pack-refs",
        "prune",
        "pull",
        "push",
        "range-diff",
        "rebase",
        "reflog",
        "remote",
        "repack",
        "replace",
        "reset",
        "restore",
        "rev-list",
        "rev-parse",
        "revert",
        "rm",
        "shortlog",
        "show",
        "show-ref",
        "sparse-checkout",
        "stage",
        "stash",
        "status",
        "submodule",
        "switch",
        "symbolic-ref",
        "tag",
        "update-index",
        "update-ref",
        "verify-commit",
        "version",
        "worktree",
    ]
)
COMMIT_VALUE_OPTIONS = frozenset(
    {"-m", "-F", "-c", "-C", "-t", "--author", "--date", "--cleanup", "--fixup", "--squash"}
    | {"--trailer", "--file", "--message", "--reuse-message", "--reedit-message", "--template"}
)
NETWORK_PROGRAMS = frozenset(
    {
        "curl", "wget", "aria2c", "gdown", "huggingface-cli", "hf", "certutil", "bitsadmin",
        "invoke-webrequest", "iwr", "invoke-restmethod", "irm", "start-bitstransfer", "scp",
        "sftp", "rsync", "ftp", "tftp",
    }
)  # fmt: skip
GIT_NETWORK = frozenset({"clone", "fetch", "pull", "ls-remote", "submodule", "remote"})
DELETE_PROGRAMS = frozenset({"rm", "remove-item", "del", "erase", "ri", "rd", "rmdir"})
POSIX_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
WRAPPERS = frozenset({"command", "builtin", "exec", "nohup", "time", "sudo", "doas"})
XARGS_VALUE_OPTIONS = frozenset({"-I", "-i", "-n", "-P", "-L", "-l", "-s", "-d", "-E", "-e", "-a"})
UV_RUN_VALUE_OPTIONS = frozenset(
    {"--with", "--with-editable", "--with-requirements", "--python", "-p", "--project"}
    | {"--directory", "--env-file", "--extra", "--group", "--only-group", "--package", "--index"}
    | {"--default-index", "--index-url", "--extra-index-url", "-i", "--find-links", "-f"}
    | {"--config-file", "--cache-dir", "--python-preference"}
)
PROTECTED_WORDS = re.compile(
    r"prereg|golden|push|\bgit\b|\brm\b|remove-item|\bdel\b|rmdir|\brd\b|clean|://|curl|wget"
    r"|invoke-|rmtree|\biwr\b|\birm\b|data/|results/|\.claude|\.git/",
    re.IGNORECASE,
)
URL_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://(?:[^\s'\"/@]*@)?([^\s'\"/:?#\\]+)")
SCP_RE = re.compile(r"^[\w.-]+@([\w.-]+):")
PY_NET_RE = re.compile(r"urllib|requests\.|http\.client|urlopen|urlretrieve|httpx|aiohttp|socket")
NET_HINT_RE = re.compile(
    r"webclient|downloadfile|downloadstring|downloaddata|httpclient|net\.http|bitstransfer"
    r"|urlretrieve|urlopen|invoke-webrequest|invoke-restmethod"
)
PREREG_TAG_RE = re.compile(r"prereg-v(\d+)")
ADDENDUM_RE = re.compile(r"docs/prereg/addendum-v(\d+)\.md")
PREREG_DIR_RE = re.compile(r"docs/prereg/?(?=$|[\s'\"*;|&)])")
INTERNAL_RE = re.compile(r"(?:^|[\s'\"=/])(?:\.git/|\.claude/(?:settings|hooks/|agents/))")
GLOB_RE = re.compile(r"[*?\[{]")
REDIRECT_SAFE_RE = re.compile(r"\d?>&\d|\d?>\s*(?:/dev/null|\$null|nul)\b", re.IGNORECASE)
QUOTED_RE = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
FUNCTION_DEF_RE = re.compile(r"[\w.-]+\(\)")
SETTINGS_FILE_RE = re.compile(r"(?:managed-)?settings(?:\.local)?\.json")

REVIEWER_UV_FLAGS = frozenset({"--no-sync", "--frozen", "--locked", "--offline", "-q", "--quiet"})
REVIEWER_PYTEST_FLAGS = frozenset(
    {"-q", "-qq", "-v", "-vv", "-x", "--exitfirst", "-l", "--lf", "--last-failed", "--ff"}
    | {"--failed-first", "--co", "--collect-only", "--no-header", "--strict-markers", "-s"}
)
REVIEWER_PYTEST_VALUE = frozenset({"-k", "-m", "--tb", "--maxfail", "--durations"})
REVIEWER_PYTEST_PREFIXES = ("--tb=", "--maxfail=", "--durations=", "-r")
REVIEWER_SAFE_ARG = re.compile(r"[\w.\-/:\[\]]+")


@dataclass(frozen=True)
class Decision:
    block: bool
    reason: str = ""


ALLOW = Decision(False)


def blocked(reason: str) -> Decision:
    return Decision(True, f"DriftWatch guard: {reason}")


class GitError(Exception):
    """git could not be run or returned an error."""


def git(cwd: Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise GitError(str(exc)) from exc
    if out.returncode != 0:
        raise GitError(out.stderr.strip() or f"git {' '.join(args)} failed")
    return out.stdout


# --- paths -------------------------------------------------------------------------------


def native(text: str) -> str:
    """Normalise separators; map Git Bash paths (/e/x, /tmp) to Windows paths."""
    p = os.path.expanduser(text.strip()).replace("\\", "/")
    if os.name == "nt":
        drive = re.match(r"^/([a-zA-Z])(?=/|$)", p)
        if drive:
            p = f"{drive.group(1)}:/{p[3:]}"
        elif p == "/tmp" or p.startswith("/tmp/"):
            p = tempfile.gettempdir().replace("\\", "/") + p[4:]
    return p


def resolve(text: str, cwd: Path) -> Path | None:
    try:
        path = Path(native(text))
        if not path.is_absolute():
            path = cwd / path
        return Path(os.path.realpath(path))
    except (OSError, ValueError):
        return None


def relative_to(path: Path, root: Path) -> str | None:
    """POSIX-style path of `path` inside `root`, '' for root itself, None if outside."""
    try:
        rel = os.path.relpath(path, os.path.realpath(root))
    except ValueError:  # different drive on Windows
        return None
    rel = rel.replace("\\", "/")
    if rel == ".." or rel.startswith("../"):
        return None
    return "" if rel == "." else rel


def temp_roots(scratch: str | None) -> list[Path]:
    names = [tempfile.gettempdir(), *(os.environ.get(v) for v in ("TEMP", "TMP", "TMPDIR"))]
    if scratch:
        names.append(scratch)
    if os.name != "nt":
        names.append("/tmp")
    return [Path(os.path.realpath(n)) for n in names if n]


def inside_temp(path: Path, scratch: str | None, allow_root: bool) -> bool:
    for root in temp_roots(scratch):
        rel = relative_to(path, root)
        if rel is None:
            continue
        if rel or allow_root:
            return True
    return False


# --- locks -------------------------------------------------------------------------------


def prereg_tags(project: Path) -> list[str]:
    return [
        t for t in git(project, "tag", "--list", "prereg-v*").split() if PREREG_TAG_RE.fullmatch(t)
    ]


def highest_prereg_tag(tags: list[str]) -> str:
    return max(tags, key=lambda t: int(PREREG_TAG_RE.fullmatch(t).group(1)))  # type: ignore[union-attr]


def lock_for(rel_cf: str, project: Path) -> tuple[str, str] | None:
    """(tag, tagged path) if the casefolded project path is a locked prereg file."""
    if rel_cf == "docs/prereg.md":
        tags = prereg_tags(project)
        return (highest_prereg_tag(tags), "docs/PREREG.md") if tags else None
    m = ADDENDUM_RE.fullmatch(rel_cf)
    if m and f"prereg-v{m.group(1)}" in prereg_tags(project):
        return f"prereg-v{m.group(1)}", f"docs/prereg/addendum-v{m.group(1)}.md"
    return None


def golden_files(project: Path) -> list[str]:
    return git(project, "ls-tree", "-r", "--name-only", "HEAD", "--", "tests/golden").splitlines()


def golden_committed(project: Path, rel: str) -> bool:
    return bool(git(project, "ls-tree", "--name-only", "HEAD", "--", rel).strip())


def locked_paths(project: Path) -> dict[str, str]:
    """Casefolded project path -> label, for every file currently locked."""
    paths: dict[str, str] = {}
    tags = prereg_tags(project)
    if tags:
        paths["docs/prereg.md"] = "docs/PREREG.md"
        for t in tags:
            n = PREREG_TAG_RE.fullmatch(t).group(1)  # type: ignore[union-attr]
            paths[f"docs/prereg/addendum-v{n}.md"] = f"docs/prereg/addendum-v{n}.md"
    for rel in golden_files(project):
        paths[rel.casefold()] = rel
    return paths


def normalise_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def proposed_content(tool: str, tool_input: dict, target: Path) -> str | None:
    if tool == "Write":
        content = tool_input.get("content")
        return content if isinstance(content, str) else None
    if tool == "Edit":
        old, new = tool_input.get("old_string"), tool_input.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str):
            return None
        try:
            current = normalise_text(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            return None
        old, new = normalise_text(old), normalise_text(new)
        if not old or old not in current:
            return None
        count = -1 if tool_input.get("replace_all") else 1
        return current.replace(old, new, count)
    return None  # NotebookEdit and unknown edit tools: content cannot be checked


def check_file_tool(tool: str, tool_input: dict, cwd: Path, project: Path) -> Decision:
    key = "notebook_path" if "notebook_path" in tool_input else "file_path"
    text = tool_input.get(key)
    if not isinstance(text, str) or not text.strip():
        return blocked(f"{tool} call without {key}; failing closed.")
    target = resolve(text, cwd)
    if target is None:
        return blocked(f"cannot resolve path {text!r}; failing closed.")
    rel = relative_to(target, project)
    rel_cf = rel.casefold() if rel is not None else None
    name_cf = target.name.casefold()
    is_settings = SETTINGS_FILE_RE.fullmatch(name_cf) and (
        target.parent.name.casefold() == ".claude" or name_cf.startswith("managed")
    )
    # The shared .claude/settings.json is gated by an `ask` permission rule instead.
    if is_settings and rel_cf != ".claude/settings.json":
        return blocked(
            f"{text} is a Claude Code settings file that could disable the guardrails; "
            "ask the researcher."
        )
    if rel_cf is None:
        return ALLOW
    if rel_cf == ".git" or rel_cf.startswith(".git/"):
        return blocked(f"direct edits inside .git/ ({rel}) are not allowed; use git commands.")
    if rel_cf == "docs/prereg.md" or rel_cf.startswith("docs/prereg/"):
        try:
            lock = lock_for(rel_cf, project)
        except GitError:
            return blocked(f"cannot read prereg tags for {rel}; failing closed.")
        if lock:
            tag, tagged_path = lock
            proposed = proposed_content(tool, tool_input, target)
            try:
                expected = git(project, "show", f"{tag}:{tagged_path}")
            except GitError:
                expected = None
            if (
                proposed is None
                or expected is None
                or (normalise_text(proposed) != normalise_text(expected))
            ):
                return blocked(
                    f"{rel} is locked by tag {tag}. Put changes in a new addendum "
                    "(docs/prereg/addendum-vN.md) that the researcher approves."
                )
    if rel_cf.startswith("tests/golden/"):
        try:
            committed = golden_committed(project, rel or "")
        except GitError:
            return blocked(f"cannot verify whether {rel} is a locked golden file; failing closed.")
        if committed:
            return blocked(f"{rel} is a committed golden file and is locked. Ask the researcher.")
    return ALLOW


# --- shell parsing -----------------------------------------------------------------------


def split_segments(command: str, posix: bool) -> list[str]:
    """Split on unquoted && || ; | & and newlines (redirections like 2>&1 stay intact)."""
    segments: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i, n = 0, len(command)
    while i < n:
        c = command[i]
        if quote:
            buf.append(c)
            if c == quote:
                quote = None
            elif c == "\\" and posix and quote == '"' and i + 1 < n:
                buf.append(command[i + 1])
                i += 1
        elif c in "'\"":
            quote = c
            buf.append(c)
        elif c == "\\" and posix and i + 1 < n:
            buf.extend((c, command[i + 1]))
            i += 1
        elif command.startswith(("&&", "||"), i):
            segments.append("".join(buf))
            buf = []
            i += 1
        elif c in ";|&\n\r":
            prev = buf[-1] if buf else ""
            if (c == "&" and (prev in "<>" or command[i + 1 : i + 2] == ">")) or (
                c == "|" and prev == ">"
            ):
                buf.append(c)
            else:
                segments.append("".join(buf))
                buf = []
        else:
            buf.append(c)
        i += 1
    segments.append("".join(buf))
    return [s.strip() for s in segments if s.strip()]


def tokenize(segment: str, posix: bool) -> list[str] | None:
    lexer = shlex.shlex(segment, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    lexer.escape = "\\" if posix else ""  # backslash is literal in PowerShell
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    # Drop grouping syntax so `(git push -f)`, `{ git push -f; }` and `& { ... }` are seen as
    # plain commands; keep the `{}` placeholder of find/xargs; drop `name()` function headers.
    out = []
    for tok in tokens:
        if tok == "{}":
            out.append(tok)
            continue
        if FUNCTION_DEF_RE.fullmatch(tok):
            continue
        stripped = tok.strip("(){}")
        if stripped:
            out.append(stripped)
    return out


def program_name(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].casefold()
    return name[:-4] if name.endswith(".exe") else name


def strip_wrappers(tokens: list[str]) -> list[str]:
    i = 0
    while i < len(tokens):
        tok, name = tokens[i], program_name(tokens[i])
        if tok in ("&", ".") or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tok) or name in WRAPPERS:
            i += 1
        elif name == "uvx" or (name == "uv" and i + 1 < len(tokens) and tokens[i + 1] == "run"):
            i += 1 if name == "uvx" else 2
            while i < len(tokens) and tokens[i].startswith("-"):
                opt = tokens[i].split("=", 1)[0]
                i += 2 if opt in UV_RUN_VALUE_OPTIONS and "=" not in tokens[i] else 1
        elif name in ("env", "nice", "stdbuf", "timeout"):
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                takes_value = tokens[i] in ("-n", "-u", "-s", "-k", "-o", "-e", "-i")
                i += 2 if takes_value and name != "env" or tokens[i] == "-u" else 1
            if name == "timeout" and i < len(tokens) and re.fullmatch(r"[\d.]+[smhd]?", tokens[i]):
                i += 1
        else:
            break
    return tokens[i:]


def git_subcommand(args: list[str]) -> tuple[str, list[str], str | None, dict[str, str]]:
    """(subcommand, its args, -C directory, inline aliases from -c alias.X=...)."""
    i, cdir, aliases = 0, None, {}
    while i < len(args):
        a = args[i]
        if a == "-C":
            cdir = args[i + 1] if i + 1 < len(args) else None
            i += 2
        elif a == "-c":
            value = args[i + 1] if i + 1 < len(args) else ""
            key, _, val = value.partition("=")
            if key.casefold().startswith("alias."):
                aliases[key[6:].casefold()] = val
            i += 2
        elif a in ("--git-dir", "--work-tree", "--namespace", "--config-env"):
            i += 2
        elif a.startswith("-"):
            i += 1
        else:
            return a.casefold(), args[i + 1 :], cdir, aliases
    return "", [], cdir, aliases


def short_flags(arg: str) -> str:
    """Letters of a short-option cluster such as -uf, else ''."""
    return arg[1:] if re.fullmatch(r"-[A-Za-z]+", arg) else ""


def expand_braces(pattern: str, limit: int = 64) -> list[str]:
    m = re.search(r"\{([^{}]*,[^{}]*)\}", pattern)
    if not m:
        return [pattern]
    out: list[str] = []
    for alt in m.group(1).split(","):
        out += expand_braces(pattern[: m.start()] + alt + pattern[m.end() :], limit)
        if len(out) >= limit:
            break
    return out[:limit]


# --- command checks ----------------------------------------------------------------------


def is_read_only(command: str, posix: bool) -> bool:
    unquoted = QUOTED_RE.sub("", command)  # redirection happens only outside quotes
    if ">" in REDIRECT_SAFE_RE.sub("", unquoted):
        return False
    for segment in split_segments(command, posix):
        tokens = tokenize(segment, posix)
        if tokens is None:
            return False
        tokens = strip_wrappers(tokens)
        if not tokens:
            continue
        prog, args = program_name(tokens[0]), tokens[1:]
        if prog == "git":
            if git_subcommand(args)[0] not in SAFE_GIT_FOR_LOCKED:
                return False
        elif prog == "sed":
            if any(a.startswith(("-i", "--in-place")) for a in args):
                return False
        elif prog not in READ_ONLY_PROGRAMS:
            return False
    return True


def glob_hits(text: str, cwd: Path, project: Path, locked: dict[str, str]) -> list[str]:
    """Locked files matched by glob or brace patterns in a casefolded, unquoted command."""
    cwd_rel = (relative_to(cwd, project) or "").casefold()
    project_prefix = str(Path(os.path.realpath(project))).replace("\\", "/").casefold() + "/"
    hits: list[str] = []
    for raw in re.split(r"[\s=<>|;&()]+", text):
        if not raw or not GLOB_RE.search(raw):
            continue
        for pattern in expand_braces(raw):
            if pattern.startswith(project_prefix):
                pattern = pattern[len(project_prefix) :]
            elif pattern.startswith("/") or re.match(r"[a-z]:/", pattern):
                continue
            joined = posixpath.normpath(posixpath.join(cwd_rel, pattern))
            for path_cf, label in locked.items():
                basename = path_cf.rsplit("/", 1)[-1]
                if fnmatch.fnmatchcase(path_cf, joined) or (
                    "/" not in pattern and fnmatch.fnmatchcase(basename, pattern)
                ):
                    hits.append(label)
    return hits


def check_locked_mentions(command: str, posix: bool, ctx: dict) -> Decision:
    text = re.sub(r"['\"]", "", command.replace("\\", "/").casefold())  # quotes cannot hide paths
    locked: list[str] = []
    if INTERNAL_RE.search(text):
        locked.append(".git/ or .claude/ settings, hooks or agents")
    mentions_prereg = "prereg.md" in text
    addenda = set(re.findall(r"addendum-v(\d+)", text))
    mentions_dir = bool(PREREG_DIR_RE.search(text))
    mentions_golden = "tests/golden" in text
    has_glob = bool(GLOB_RE.search(text))
    if not (locked or mentions_prereg or addenda or mentions_dir or mentions_golden or has_glob):
        return ALLOW
    project = ctx["project"]
    try:
        if mentions_prereg or addenda or mentions_dir:
            tags = prereg_tags(project)
            if tags and (mentions_prereg or mentions_dir):
                locked.append("docs/PREREG.md or docs/prereg/")
            locked += [f"addendum-v{n}" for n in addenda if f"prereg-v{n}" in tags]
        if mentions_golden and golden_files(project):
            locked.append("tests/golden/")
        if has_glob:
            locked += glob_hits(text, ctx["cwd"], project, locked_paths(project))
    except GitError:
        if not (mentions_prereg or addenda or mentions_dir or mentions_golden):
            return ALLOW if not locked else _locked_decision(command, posix, locked)
        return blocked(
            "command touches a lockable path and the lock state cannot be read; failing closed."
        )
    return _locked_decision(command, posix, locked)


def _locked_decision(command: str, posix: bool, locked: list[str]) -> Decision:
    if locked and not is_read_only(command, posix):
        unique = ", ".join(dict.fromkeys(locked))
        return blocked(
            f"command may write to locked files ({unique}). Only read-only commands may touch "
            "them; changes go into an addendum, an ADR or the Edit tool (which asks first)."
        )
    return ALLOW


def check_push(rest: list[str]) -> Decision:
    for a in rest:
        al = a.casefold()
        flags = short_flags(a)
        if al in (
            "--force",
            "--mirror",
            "--prune",
            "--delete",
            "--force-if-includes",
        ) or al.startswith("--force-with-lease"):
            return blocked(f"destructive push option {a} is not allowed.")
        if flags and ("f" in flags or "d" in flags):
            return blocked(f"destructive push option {a} (force/delete) is not allowed.")
        if not a.startswith("-") and a.startswith(("+", ":")):
            return blocked(f"refspec {a} forces or deletes a remote ref; not allowed.")
    return ALLOW


def check_tag(rest: list[str]) -> Decision:
    destructive = any(
        a.casefold() in ("-d", "--delete", "-f", "--force")
        or set(short_flags(a).lower()) & {"d", "f"}
        for a in rest
    )
    if destructive and any(a.casefold().startswith("prereg-v") for a in rest):
        return blocked(
            "deleting or moving a prereg-v* tag is not allowed; tags lock pre-registrations."
        )
    return ALLOW


def is_data_path(rel_cf: str) -> bool:
    first = rel_cf.split("/", 1)[0]
    return first in ("data", "results") and rel_cf != "data/manifest.json"


def first_data_path(args: list[str], gcwd: Path, value_options: frozenset[str]) -> str | None:
    """First argument (or the path part of mode,sha,path) that points into data/ or results/."""
    try:
        top = Path(git(gcwd, "rev-parse", "--show-toplevel").strip())
    except GitError:
        return None  # not a repository: the git command itself will fail
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in value_options:
            skip = True
            continue
        if a.startswith("-"):
            continue
        for candidate in dict.fromkeys((a, a.rsplit(",", 1)[-1])):
            target = resolve(candidate, gcwd)
            rel = relative_to(target, top) if target else None
            if rel and is_data_path(rel.casefold()):
                return a
    return None


def check_add(rest: list[str], gcwd: Path) -> Decision:
    try:
        top = Path(git(gcwd, "rev-parse", "--show-toplevel").strip())
    except GitError:
        return blocked("cannot locate the git repository for `git add`; failing closed.")
    explicit = first_data_path(rest, gcwd, frozenset({"--chmod"}))
    if explicit:
        return blocked(f"`git add {explicit}` would stage data/ or results/; never commit data.")
    interactive = ("-p", "--patch", "-i", "--interactive", "-e", "--edit", "-n", "--dry-run")
    dry_args = [a for a in rest if a not in interactive]
    try:
        out = git(gcwd, "add", "--dry-run", *dry_args)
    except GitError as exc:
        return blocked(f"could not verify `git add` with a dry run ({exc}); failing closed.")
    for line in out.splitlines():
        m = re.match(r"add '(.*)'$", line.strip())
        if not m:
            continue
        target = resolve(m.group(1), gcwd)
        rel = relative_to(target, top) if target else None
        if rel is None or is_data_path(rel.casefold()):
            return blocked(
                f"`git add` would stage {m.group(1)}; data/ and results/ are never committed."
            )
    return ALLOW


def check_git(args: list[str], ctx: dict, cwd: Path, depth: int = 0) -> Decision:
    sub, rest, cdir, inline_aliases = git_subcommand(args)
    gcwd = (resolve(cdir, cwd) if cdir else None) or cwd
    if sub and sub not in KNOWN_GIT:
        if depth > 3:
            return blocked("git alias nesting is too deep to check; failing closed.")
        value = inline_aliases.get(sub)
        if value is None:
            try:
                value = git(gcwd, "config", "--get", f"alias.{sub}").strip() or None
            except GitError:
                value = None
        if value and value.startswith("!"):
            inner = value[1:] + " " + " ".join(shlex.quote(r) for r in rest)
            return evaluate_shell(inner, {**ctx, "cwd": gcwd}, posix=True, depth=depth + 1)
        if value:
            try:
                expanded = shlex.split(value)
            except ValueError:
                return blocked(f"git alias {sub} cannot be parsed; failing closed.")
            return check_git([*expanded, *rest], ctx, gcwd, depth + 1)
    if sub == "push":
        return check_push(rest)
    if sub == "tag":
        return check_tag(rest)
    if sub == "update-ref" and any("refs/tags/prereg-v" in a.casefold() for a in rest):
        return blocked("changing refs/tags/prereg-v* is not allowed.")
    if sub in ("add", "stage"):
        return check_add(rest, gcwd)
    if sub == "update-index":
        if "--index-info" in rest or "--stdin" in rest:
            return blocked("`git update-index` reading paths from stdin cannot be checked.")
        path = first_data_path(rest, gcwd, frozenset())
        if path:
            return blocked(f"`git update-index` would stage {path}; never commit data.")
    if sub == "commit":
        path = first_data_path(rest, gcwd, COMMIT_VALUE_OPTIONS)
        if path:
            return blocked(f"`git commit {path}` would commit data/ or results/.")
    return ALLOW


def safe_delete_target(text: str, cwd: Path, project: Path, scratch: str | None) -> bool:
    if any(ch in text for ch in "$%`"):
        return False
    norm = text.replace("\\", "/")
    head = re.split(r"[*?\[]", norm, maxsplit=1)[0]
    has_glob = head != norm
    if has_glob:
        head = head.rsplit("/", 1)[0] if "/" in head else "."
    path = resolve(head or "/", cwd)
    if path is None:
        return False
    # Inside the project only cache folders may go, even if the project sits in a temp folder.
    rel = relative_to(path, project)
    if rel is not None:
        parts = rel.casefold().split("/") if rel else []
        return any(part in CACHE_DIRS or part.endswith(".egg-info") for part in parts)
    return inside_temp(path, scratch, allow_root=has_glob)


def is_recursive_flag(arg: str, prog: str) -> bool:
    al = arg.casefold()
    if al in ("--recursive", "/s"):
        return True
    if al.startswith("-") and not al.startswith("--"):
        name = al[1:]
        if name and "recurse".startswith(name) and name.startswith("r"):
            return True
        if prog == "rm" and re.fullmatch(r"[a-z]{1,3}", name) and "r" in name:
            return True
    return False


def check_delete(prog: str, args: list[str], ctx: dict, xargs: bool) -> Decision:
    cwd, project, scratch = ctx["cwd"], ctx["project"], ctx["scratch"]
    targets: list[str] = []
    if prog in DELETE_PROGRAMS:
        recursive, skip = False, False
        for a in args:
            al = a.casefold()
            if skip:
                skip = False
                continue
            if is_recursive_flag(a, prog):
                recursive = True
            elif re.fullmatch(r"/[a-z]", al) and prog in ("rd", "rmdir", "del", "erase"):
                continue  # cmd switches such as /q
            elif al.startswith("-"):
                skip = al.lstrip("-") in ("include", "exclude", "filter", "credential", "stream")
            else:
                targets.append(a)
        if not recursive:
            return ALLOW
    elif prog == "find" and ("-delete" in args or ("-exec" in args and "rm" in args)):
        for a in args:
            if a.startswith(("-", "(", "!")):
                break
            targets.append(a)
        targets = targets or ["."]
    elif prog == "git":
        sub, rest, cdir, _ = git_subcommand(args)
        letters = "".join(short_flags(a) for a in rest)
        if sub != "clean" or "n" in letters or "--dry-run" in rest:
            return ALLOW
        if not (set(letters) & {"d", "x", "X"}):
            return ALLOW
        targets = [cdir or "."]
    else:
        return ALLOW
    if xargs or not targets:
        return blocked(f"recursive delete with targets that cannot be checked ({prog}).")
    for t in targets:
        if not safe_delete_target(t, cwd, project, scratch):
            return blocked(f"recursive delete of {t!r} is outside temporary folders and caches.")
    return ALLOW


def check_basetemp(tokens: list[str], ctx: dict) -> Decision:
    """pytest empties --basetemp before a run, so it is a recursive delete."""
    for j, tok in enumerate(tokens):
        if not tok.startswith("--basetemp"):
            continue
        target = (
            tok.split("=", 1)[1] if "=" in tok else (tokens[j + 1] if j + 1 < len(tokens) else "")
        )
        if not target or not safe_delete_target(target, ctx["cwd"], ctx["project"], ctx["scratch"]):
            return blocked(f"pytest --basetemp {target!r} would delete a folder outside temp.")
    return ALLOW


def host_allowed(host: str) -> bool:
    host = host.casefold().rstrip(".")
    return host in ALLOWED_HOSTS or host.endswith(ALLOWED_HOST_SUFFIXES)


def check_network(prog: str, args: list[str], segment: str) -> Decision:
    hosts = [m.group(1) for m in URL_RE.finditer(segment)]
    hosts += [m.group(1) for a in args if (m := SCP_RE.match(a))]
    is_python = prog.startswith("python") or prog == "py"
    python_net = is_python and "-c" in args and PY_NET_RE.search(segment)
    is_net = (
        prog in NETWORK_PROGRAMS or bool(python_net) or bool(NET_HINT_RE.search(segment.casefold()))
    )
    if prog == "git":
        is_net = git_subcommand(args)[0] in GIT_NETWORK
    elif hosts and (
        is_python or prog in ("pip", "pip3", "uv", "uvx", "pipx", "conda", "npm", "npx")
    ):
        is_net = True
    if not is_net:
        return ALLOW
    if not hosts and prog != "git" and any(not a.startswith("-") for a in args):
        return blocked(f"cannot determine the download host for {prog}; failing closed.")
    for host in hosts:
        if not host_allowed(host):
            return blocked(f"download host {host} is not on the allowlist (see ADR-0001).")
    return ALLOW


def nested_command(prog: str, args: list[str]) -> tuple[str, bool] | None:
    """Inner command text and its posix flag for bash -c, cmd /c, powershell -Command, eval."""
    if prog in POSIX_SHELLS:
        for j, a in enumerate(args):
            if re.fullmatch(r"-[a-z]*c[a-z]*", a) and j + 1 < len(args):
                return args[j + 1], True
    if prog == "cmd":
        for j, a in enumerate(args):
            if a.casefold() in ("/c", "/k"):
                return " ".join(args[j + 1 :]), False
    if prog in ("powershell", "pwsh"):
        for j, a in enumerate(args):
            al = a.casefold()
            if al in ("-encodedcommand", "-enc", "-e", "-ec") and j + 1 < len(args):
                try:
                    return base64.b64decode(args[j + 1]).decode("utf-16-le"), False
                except (ValueError, UnicodeDecodeError):
                    return "\x00undecodable", False
            if len(al) > 1 and "-command".startswith(al):
                return " ".join(args[j + 1 :]), False
    if prog == "eval":
        return " ".join(args), True
    if prog in ("invoke-expression", "iex"):
        return " ".join(args), False
    return None


def evaluate_shell(command: str, ctx: dict, posix: bool, depth: int = 0) -> Decision:
    if depth > 4:
        return blocked("command nesting is too deep to check; failing closed.")
    if "\x00undecodable" in command:
        return blocked("encoded command cannot be decoded and checked; failing closed.")
    decision = check_locked_mentions(command, posix, ctx)
    if decision.block:
        return decision
    if posix:
        for inner in re.findall(r"\$\(([^()]*)\)|`([^`]*)`", command):
            decision = evaluate_shell(inner[0] or inner[1], ctx, posix, depth + 1)
            if decision.block:
                return decision
    cwd = ctx["cwd"]
    for segment in split_segments(command, posix):
        tokens = tokenize(segment, posix)
        if tokens is None:
            if PROTECTED_WORDS.search(segment):
                return blocked(
                    "command cannot be parsed and touches a protected operation; failing closed."
                )
            continue
        tokens = strip_wrappers(tokens)
        if not tokens:
            continue
        if any(ch in tokens[0] for ch in "$`") and PROTECTED_WORDS.search(segment):
            return blocked("command name comes from a variable or substitution; failing closed.")
        prog, args = program_name(tokens[0]), tokens[1:]
        xargs = False
        if prog == "xargs":
            j = 0
            while j < len(args) and args[j].startswith("-"):
                j += 2 if args[j] in XARGS_VALUE_OPTIONS else 1
            if j >= len(args):
                continue
            xargs, prog, args = True, program_name(args[j]), args[j + 1 :]
        if prog in ("cd", "set-location", "sl", "chdir", "pushd") and args:
            new = resolve(args[-1], cwd) if "$" not in args[-1] else None
            cwd = new or cwd
            continue
        local = {**ctx, "cwd": cwd}
        nested = nested_command(prog, args)
        if nested is not None:
            decision = evaluate_shell(nested[0], local, nested[1], depth + 1)
            if decision.block:
                return decision
        if prog == "git":
            decision = check_git(args, local, cwd, depth)
            if decision.block:
                return decision
        if (prog.startswith("python") or prog == "py") and re.search(r"rmtree|removedirs", segment):
            return blocked("recursive delete from Python code cannot be checked; failing closed.")
        for decision in (
            check_delete(prog, args, local, xargs),
            check_basetemp(tokens, local),
            check_network(prog, args, segment),
        ):
            if decision.block:
                return decision
    return ALLOW


# --- entry points ------------------------------------------------------------------------


def evaluate(payload: dict, project_dir: Path | None = None) -> Decision:
    tool, tool_input = payload.get("tool_name"), payload.get("tool_input")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return blocked("hook input lacks tool_name or tool_input; failing closed.")
    cwd_text = payload.get("cwd")
    cwd = Path(cwd_text) if isinstance(cwd_text, str) and cwd_text else Path.cwd()
    project = Path(project_dir or os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
    scratch = (
        payload.get("scratchpad_dir") if isinstance(payload.get("scratchpad_dir"), str) else None
    )
    edits_a_file = re.search(r"edit|write", tool, re.IGNORECASE) and (
        "file_path" in tool_input or "notebook_path" in tool_input
    )
    if tool in ("Edit", "Write", "NotebookEdit") or edits_a_file:
        return check_file_tool(tool, tool_input, cwd, project)
    if tool in ("Bash", "PowerShell"):
        command = tool_input.get("command")
        if not isinstance(command, str):
            return blocked(f"{tool} call without a command string; failing closed.")
        ctx = {"cwd": cwd, "project": project, "scratch": scratch}
        return evaluate_shell(command, ctx, posix=tool == "Bash")
    return ALLOW


def reviewer_check(payload: dict) -> Decision:
    """Reviewer subagents may run only `uv run [safe flags] pytest [test selection]`."""
    tool = payload.get("tool_name")
    if tool not in ("Bash", "PowerShell"):
        return ALLOW
    deny = blocked(
        "reviewer subagents are read-only; the only shell command allowed is "
        "`uv run pytest` with test-selection options (-q -x -k -m --tb, test paths)."
    )
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or re.search(r"[\n\r;&|<>$`]", command):
        return deny
    tokens = tokenize(command, posix=tool == "Bash")
    if not tokens or tokens[:2] != ["uv", "run"]:
        return deny
    i = 2
    while i < len(tokens) and tokens[i].startswith("-"):
        if tokens[i] not in REVIEWER_UV_FLAGS:
            return deny
        i += 1
    if i >= len(tokens) or tokens[i] != "pytest":
        return deny
    rest, j = tokens[i + 1 :], 0
    while j < len(rest):
        tok = rest[j]
        if tok in REVIEWER_PYTEST_VALUE:
            j += 2
            continue
        if tok in REVIEWER_PYTEST_FLAGS or tok.startswith(REVIEWER_PYTEST_PREFIXES):
            j += 1
            continue
        if (
            tok.startswith(("-", "/", "\\"))
            or ".." in tok
            or re.match(r"[A-Za-z]:", tok)
            or not REVIEWER_SAFE_ARG.fullmatch(tok)
        ):
            return deny
        j += 1
    return ALLOW


def report(reason: str) -> int:
    print(reason, file=sys.stderr)
    return 2


def main(argv: list[str] | None = None, stdin_text: str | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    with contextlib.suppress(AttributeError, ValueError):
        sys.stderr.reconfigure(errors="replace")  # type: ignore[union-attr]
    if stdin_text is None:
        stdin_text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(stdin_text)
    except (ValueError, RecursionError):
        return report("DriftWatch guard: hook input is not valid JSON; failing closed.")
    if not isinstance(payload, dict):
        return report("DriftWatch guard: hook input is not a JSON object; failing closed.")
    try:
        decision = reviewer_check(payload) if "--reviewer-bash" in argv else evaluate(payload)
    except Exception as exc:  # noqa: BLE001 - the crash policy needs every error
        if PROTECTED_WORDS.search(stdin_text):
            return report(
                f"DriftWatch guard: internal error ({type(exc).__name__}: {exc}); "
                "failing closed for a protected operation."
            )
        print(f"DriftWatch guard: internal error ({type(exc).__name__}); allowed.", file=sys.stderr)
        return 0
    return report(decision.reason) if decision.block else 0


if __name__ == "__main__":
    sys.exit(main())
