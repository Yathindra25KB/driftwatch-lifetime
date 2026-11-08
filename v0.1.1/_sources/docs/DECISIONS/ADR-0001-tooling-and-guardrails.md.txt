# ADR-0001: Tooling and guardrail design

**Status:** ACCEPTED (by the researcher, 2026-10-10, after the adversarial review)
**Date:** 2026-10-10
**Deciders:** Yathindra (approves); Claude Code (proposes)
**Phase:** 1

## Context
Most DriftWatch code is written by an AI agent. The research rules are easy to break by accident: never train on the future, never read a label before it arrives, never edit a locked pre-registration, never commit data. Plan §5.2 therefore puts every must-never-happen rule into a mechanism that does not depend on the model cooperating. Constraints: Windows-native machine (Windows 11, Claude Code 2.1.280, Git Bash and PowerShell tools); free tools only; hooks in Python; everything must also run on Linux CI.

## Decision (choice)

### Tooling
- Python 3.12, uv-managed (`python-preference = "only-managed"`, so the venv never lands on the Anaconda interpreter exported via `VIRTUAL_ENV`), `uv.lock` committed, `uv_build` backend, src layout.
- ruff (lint and format), pytest (`slow` marker excluded by default through `addopts`), hypothesis, pre-commit (local hooks calling the locked ruff; no remote hook repos).
- CI: GitHub Actions. `lint-test` on ubuntu-latest (required) and `windows-smoke` on windows-latest; uv pinned to 0.12.3 (the local version); `actions/checkout@v7.0.1` and `astral-sh/setup-uv@v10.2.0` (latest releases on 2026-10-10); `permissions: contents: read`; no secrets.
- `.gitattributes` forces LF in every working copy. The machine has `core.autocrlf=true`, and stable line endings keep file hashes, CLAUDE.md line counts and the PREREG blob comparison identical across OSes.

### Guardrail layers
| Layer | What | Strength |
|---|---|---|
| CLAUDE.md + `.claude/rules/*.md` (`paths:`) | Hard rules, stop rules, commands, workflow | Advisory |
| `.claude/settings.json` permissions | Deny reading secrets and editing `data/**` and `docs/source/**`; ask before push, network, publish and guardrail edits; allow test, lint, driftwatch and read-only git | Enforced by Claude Code |
| PreToolUse guard (`guard.py`) | PREREG/addendum lock by tag, golden-file lock, force-push, `git add` of data/results, recursive deletes, download allowlist | Enforced (exit 2) |
| PostToolUse formatter (`format.py`) | ruff format + ruff check --fix on edited `.py` files | Hygiene |
| Stop gate (`stop_gate.py`) | Fast tests must be green before Claude stops; no loops | Enforced (exit 2) |
| SessionStart `compact` (`reinject.py`) | Re-inject hard rules, current phase, PHASES.md status | Context |
| Reviewer subagents | leakage-reviewer, stats-reviewer: read-only, Bash limited to `uv run pytest` by a frontmatter hook | Independent opinion |
| `phase-closeout` skill | Same closing ritual every phase | Repeatable |
| Tests, CI, `scripts/check_guardrails.py` | Prove that the hooks behave as documented, on Linux and Windows | Scientific guardrail |
| Git tags `prereg-v*` | Lock pre-registrations | Provenance |

### Hook invocation
Every hook in `.claude/settings.json` is a bash command (`"shell": "bash"`, i.e. Git Bash on Windows) of the form:

```
uv run -q --project "$CLAUDE_PROJECT_DIR" --no-sync python "$CLAUDE_PROJECT_DIR/.claude/hooks/<hook>.py"
```

- `--project "$CLAUDE_PROJECT_DIR"` keeps it working after a `cd`. `--no-sync` never installs anything; the plain `uv run` form spiked to 4.5 s once while syncing. `-q` hides uv's warning about the Anaconda `VIRTUAL_ENV` exported on this machine, so block messages reach Claude clean.
- Hooks are stdlib-only and call tools through `sys.executable -m ruff|pytest`. The same scripts therefore run unchanged under `scripts/check_guardrails.py` on Linux and Windows.
- Timeouts: guard 15 s, formatter 60 s, Stop gate 150 s (internal pytest cap 120 s, so the gate's own cap fires first), re-injection 15 s.

Measured launch latency (10 Oct 2026, this laptop, Git Bash, median of 10 runs of a no-op hook): `uv run --no-sync` 137 ms; `uv run` with sync check 101 ms median but 4,552 ms max; venv python direct 100 ms; system python 92 ms. End to end through the settings command (`scripts/check_guardrails.py`): guard median 185–193 ms (max 316 ms over 23 calls); reviewer guard 172–181 ms; formatter 345–395 ms; re-injection 172–195 ms; Stop gate 785–812 ms median, about 1 s max. The Stop gate is the only hook near 1 s, which is justified because running the fast tests is its job. On the real repository it takes about as long as `uv run pytest -q` (about 4 s at 192 tests).

### Hook behaviour
- **guard.py** (PreToolUse, matcher `Edit|Write|NotebookEdit|Bash|PowerShell`). Path tools: resolves the target (realpath, separators normalised, case-insensitive comparison). If it is `docs/PREREG.md` and any `prereg-v*` tag exists, the proposed content (Write content, or Edit applied to the current text) must equal the blob at the highest tag, with CRLF normalised; else block. `docs/prereg/addendum-vN.md` is handled the same way once `prereg-vN` exists. A `tests/golden/` file present at HEAD is locked. Shell tools: splits compound commands (`&&`, `||`, `;`, `|`, `&`, newlines), tokenises (POSIX rules for Bash, literal backslashes for PowerShell), strips wrappers (`env`, `command`, `nohup`, `timeout`, `xargs`, PowerShell `&`), recurses into `bash -c`, `cmd /c`, `powershell -Command`/`-EncodedCommand`, `eval`, `Invoke-Expression`, `$(...)` and backticks, and tracks `cd`. It then blocks force/destructive pushes, prereg tag deletion or moves, `git add` that would stage data/ or results/ (explicit paths plus a `git add --dry-run` with the same arguments), recursive deletes outside temp folders and project caches (project paths judged first, even when the project sits in a temp folder), downloads from hosts outside the allowlist, and non-read-only commands that mention a locked path.
- **format.py** (PostToolUse `Edit|Write`): `ruff check --fix --exit-zero` then `ruff format` on the edited `.py` file inside the project; always exit 0.
- **stop_gate.py** (Stop): `stop_hook_active` true means exit 0. Otherwise `pytest -q -x --tb=line`: red gives exit 2 with a 20-line summary; exit code 5 (no tests) is green with a note; the cap blocks once.
- **reinject.py** (SessionStart `compact`): hard rules, stop rules, branch, the IN PROGRESS phase and the phase status list from docs/PHASES.md, under 8,000 characters.

### Crash policy
A crashing hook exits 1, which Claude Code treats as non-blocking (F12). guard.py therefore catches everything:
- Malformed or non-object JSON, a missing `tool_name`/`tool_input`, or a missing `file_path`/`command`: exit 2 (fail closed).
- An internal exception: exit 2 if the raw payload mentions a protected operation (prereg, golden, push, git, rm/Remove-Item/del/rmdir/rd, clean, a URL, curl/wget/Invoke-*, rmtree, data/, results/); otherwise exit 0 with a warning on stderr.
- git unavailable while a lockable path is involved: block.
- A hypothesis property test feeds arbitrary text and arbitrary commands and asserts the guard returns only 0 or 2.
The formatter and re-injection hooks always exit 0. The Stop gate exits 2 only on red tests, the cap or a pytest launch failure, and `stop_hook_active` stops any loop.

### Live verification in Claude Code (10 Oct 2026)
- Hooks took effect as soon as `.claude/settings.json` was written. That matches the hooks page ("Direct edits to hooks in settings files are normally picked up automatically by the file watcher"), so no restart was needed.
- The guard blocked a real fetch from `json.schemastore.org`, until that docs-linked schema host was added to the allowlist. It blocked a real Bash `git push --force origin main` and a real PowerShell `git push -f origin main`. It allowed `rm -rf` of a clone under the system temp folder.
- Permissions denied a real Write to `docs/source/probe.txt` and a real Read of `.env`.
- The PostToolUse formatter reformatted files as they were written; path-scoped rules loaded when matching files were touched; the `phase-closeout` skill appeared in Claude Code's skill list.
- `.claude/settings.json` validates against https://json.schemastore.org/claude-code-settings.json (`check-jsonschema`: "ok -- validation done"). This matters because the settings docs say a schema-rejected file raises a Settings Error and the session can continue without it.

### Change requests
| Date | Change | Authority | Evidence |
|---|---|---|---|
| 10 Oct 2026 | Download allowlist gains `huggingface.co`, `drive.google.com`, `drive.usercontent.google.com` and the suffixes `.huggingface.co` (LFS CDN) and `.hf.co` (Xet storage). Look-alikes (`huggingface.co.evil.com`, `evilhf.co`) and other Google hosts (`docs.google.com`, `google.com`) stay blocked. | Researcher, Phase 2 plan approval (Phase 2 CHANGE_REQUEST noted in docs/PHASES.md "Phase 2 prerequisites") | `tests/test_guard.py` download tests (allowed and blocked cases) |
| 26 Oct 2026 | Download allowlist gains the exact hosts `zenodo.org`, `sandbox.zenodo.org` (Zenodo integration and its metadata dry run), `export.arxiv.org` (monthly arXiv audit API) and `yathindra25kb.github.io` (the docs site, for link checks). No suffix is added: look-alikes (`zenodo.org.evil.com`), other arXiv hosts (`arxiv.org`) and other GitHub Pages sites stay blocked. | Researcher, Phase 12 plan question round (26 Oct 2026) | `tests/test_guard.py` download tests (allowed and blocked cases) |

### Defense in depth
`tests/test_repo_invariants.py` runs on every Stop. It fails if docs/PREREG.md differs from its highest prereg tag, if a LOCKED status names a missing tag, if a committed golden file changed, or if data/ or results/ files are tracked. Any route around the guard (scripts, git history operations) therefore turns the next stop red.

## Validated Claude Code facts (official docs)
All accessed **2026-10-10** through the `claude-code-guide` subagent from `https://code.claude.com/docs/en/<page>.md`. Lines marked (S) came through a summarising fetch and were re-checked when the setting was written.

| # | Fact | Doc |
|---|---|---|
| F1 | Settings precedence: managed > CLI `--settings` > `.claude/settings.local.json` > `.claude/settings.json` > `~/.claude/settings.json`. Permission arrays merge across files; evaluation order is deny, ask, allow; a deny at any level cannot be overridden. | settings#settings-precedence, permissions#settings-precedence |
| F2 | Project `allow` rules apply after the folder is trusted; `deny` and `ask` apply immediately. | settings |
| F3 | Rule syntax `Tool` or `Tool(specifier)`. Bash wildcard written `Bash(git push *)`; a trailing `:*` is equivalent. Compound commands (`&&`, `\|\|`, `;`, `\|`, `&`, newlines) are matched per sub-command. Bash patterns are "fragile" and not a security boundary (options before arguments, variables). | permissions#bash |
| F4 | `PowerShell(...)` rules exist. A Bash rule does not restrict the PowerShell tool. Any Bash **deny** rule turns the PowerShell tool off without warning on Windows with Git Bash. | tools-reference#powershell-tool |
| F5 | `Edit(...)` rules apply to all built-in file-editing tools (Write, NotebookEdit). `Write(...)`, `NotebookEdit(...)` and `MultiEdit(...)` path rules are accepted but never consulted. A `Read` deny also blocks Edit/Write on that path. Read rules apply to Grep/Glob best-effort. | permissions#read-and-edit |
| F6 | Read and Edit deny rules also apply to Bash file commands Claude Code recognises (`cat`, `head`, `tail`, `sed`, `tee`), but not to scripts that open files themselves. | permissions#read-and-edit |
| F7 | Path patterns: `//path` absolute; `~/path` home; `/path` relative to the settings source; `path` or `./path` relative to the current directory; gitignore-style `*` and `**`. On Windows, paths are normalised to POSIX (`C:\x` becomes `/c/x`). | permissions#read-and-edit |
| F8 | MultiEdit is no longer a tool. Current names include Edit, Write, NotebookEdit, Bash, PowerShell, Read, Glob, Grep, WebFetch, Agent. | tools-reference |
| F9 | OS sandboxing exists only on macOS, Linux and WSL2. Native Windows runs commands unsandboxed. | sandboxing |
| F10 | Hook config: event, then matcher group, then handlers. `command` handlers have fields `command`, `args`, `shell` (`bash`/`powershell`), `timeout`, `if`, `statusMessage`, `async`. Matchers: exact names, `\|`-separated lists, otherwise a JS regex. (S) | hooks |
| F11 | Stdin common fields: session_id, transcript_path, cwd, permission_mode, hook_event_name, scratchpad_dir. Pre/PostToolUse add tool_name, tool_input, tool_use_id (+ tool_response). Edit input: file_path, old_string, new_string, replace_all; Write: file_path, content; Bash/PowerShell: command. Stop: stop_hook_active. SessionStart: source ∈ startup, resume, clear, compact, fork. | hooks |
| F12 | Exit 2 blocks PreToolUse (stderr goes to Claude, and the block happens before permission rules), and makes Stop continue (stderr is the reason). PostToolUse exit 2 only shows stderr (the tool already ran). SessionStart stdout on exit 0 is added to context. Other non-zero codes are non-blocking. Exit 1 does not enforce a policy. | hooks |
| F13 | A timed-out command hook does not block the tool call. A mistyped script path leaves the gate silently disabled. Default command timeout is 600 s. | hooks |
| F14 | Shell-form commands run in Git Bash on Windows (PowerShell if Git Bash is absent). Reference scripts as `"$CLAUDE_PROJECT_DIR"/...`, quoted. | hooks, hooks-guide |
| F15 | Stop hooks must check `stop_hook_active` to avoid loops; Claude Code caps consecutive Stop continuations at eight. | hooks |
| F16 | Hooks fire for subagent tool calls too; matching hooks run in parallel; an identical handler defined in several files runs once. | hooks |
| F17 | A hook returning "allow" cannot override a deny or ask rule. | permissions#extend-permissions-with-hooks |
| F18 | CLAUDE.md: "target under 200 lines". Files above the working directory load at launch; subdirectory files load on demand. `.claude/rules/**/*.md` with a `paths:` YAML list load when Read/Write/Edit touches a matching file; rules without `paths` always load. After `/compact`, the root CLAUDE.md and unscoped rules are re-injected and scoped rules reload on demand. | memory, context-window |
| F19 | Subagent frontmatter: name, description, tools (comma string or list), disallowedTools, model, permissionMode, hooks, … `tools` cannot restrict Bash to a pattern (a specifier removes the whole tool). Restrict with settings deny rules or a frontmatter PreToolUse hook (needs workspace trust). (S) | sub-agents |
| F20 | Skills: `.claude/skills/<name>/SKILL.md`; frontmatter name, description, allowed-tools, disable-model-invocation, …; supporting scripts referenced with `${CLAUDE_SKILL_DIR}`; keep SKILL.md under 500 lines. (S) | skills |
| F21 | Plan mode: Shift+Tab, `/plan`, `--permission-mode plan`, or `permissions.defaultMode`. Resume with `claude --continue` / `--resume`; rename with `/rename`. | permission-modes, sessions |
| F22 | Not in docs (verified live instead): whether hook config is snapshotted at session start; whether hooks run in plan mode; matcher case sensitivity; maximum timeout. | n/a |

## Deviations from plan Appendix B (docs win)
| # | Appendix B sketch | Current docs | Applied |
|---|---|---|---|
| 1 | Matchers `Edit\|Write\|MultiEdit` | MultiEdit no longer exists (F8) | `Edit\|Write\|NotebookEdit` (+ `Bash\|PowerShell` for the guard) |
| 2 | Bash-only rules and matcher | PowerShell is a separate tool with separate rules (F4) | PowerShell twins for every ask/allow rule; guard matches PowerShell |
| 3 | `uv run python .claude/hooks/guard.py` (relative) | Runs in the current directory; use `"$CLAUDE_PROJECT_DIR"` (F14) | Commands anchored on `$CLAUDE_PROJECT_DIR`, `shell: "bash"`, explicit timeouts |
| 4 | `Read(./.env)` | `./` means current directory (F7) | `**/`-anchored secret patterns, `/`-anchored project paths |
| 5 | (no Bash deny, but deny is the natural place for blocks) | A Bash deny silently disables PowerShell (F4) | No Bash deny rules; blocking lives in the guard |
| 6 | Sandboxing layer optional | Unavailable on native Windows (F9) | Not used; residual risk |
| 7 | Read deny assumed to cover only the Read tool | Also covers recognised Bash reads (F6) | Kept; stronger than assumed |

## Options considered
- **Rules in CLAUDE.md only.** Cheap, but advisory; the plan rejects it for must-never rules.
- **Static permission denies only.** Cannot express "locked after a tag" (PREREG and golden files must first be created). Bash patterns are not a security boundary (F3).
- **Hooks + permissions + tests (chosen).** Dynamic locks, exit-code enforcement, and behaviour proven by `check_guardrails.py` on two OSes.
- **WSL2 + OS sandbox.** Strongest isolation. The researcher chose Windows-native; recorded as a residual risk.

## Consequences
- The guardrails are only as reliable as the hook process starting. Timeouts and missing interpreters fail open (F13), so `check_guardrails.py` asserts that every hook path resolves and that each hook blocks as designed.
- Changes to `.claude/settings.json` or `.claude/hooks/**` prompt the researcher (ask rules).

## Review
An independent adversarial review and a code review ran on 10 Oct 2026; see `docs/reviews/guardrail-review.md`. Of 21 findings, 20 were fixed with regression tests (commit `6cdb589`), among them two critical reviewer-mode escapes and glob or quote bypasses of the shell lock check. One was accepted as fail-closed behaviour. Since then the guard additionally:
- resolves git aliases;
- unwraps `uv run`/`uvx` and `( )`/`{ }` grouping;
- blocks dynamic command names, `.git/` internals, non-shared settings files, `git update-index`/`git commit` of data paths, `pytest --basetemp` outside temp, and WebClient or `python -m pip` downloads;
- matches globs against locked files.

## Residual risks
These are known limits that a PreToolUse hook cannot close, or that are accepted. They are listed so nobody over-trusts the guardrails.
1. **Hooks fail open when they cannot start.** This happens when `uv`, Git Bash or the venv is missing (`rm -rf .venv` is blocked, but other routes exist), when a hook times out, or when `.claude/settings.json` becomes schema-invalid, because Claude Code can then continue without it (settings docs). Mitigation: `scripts/check_guardrails.py` in CI checks that every hook path resolves and every hook fires; `settings.json` is validated against the published schema; timeouts are generous.
2. **Shell analysis is heuristic.** Paths assembled at run time (`f=docs/PRE; echo x > ${f}REG.md`), interpreters reading code from files or stdin (`python tool.py`, `python - <<EOF`), PowerShell `-File` scripts, `Start-Process`, git filters/hooks/`core.hooksPath`, `GIT_DIR` tricks and heredoc bodies consumed by other programs can all write without the guard seeing the target. The Claude Code docs say the same of Bash permission patterns ("not a security boundary"). Mitigation: `tests/test_repo_invariants.py` fails on any PREREG drift, golden-file change or tracked data, and the Stop gate runs it before every finish; CLAUDE.md hard rule 7; reviewers.
3. **Git history operations can change locked content without naming it** (`git reset --hard <pre-tag>`, a branch switch, `stash pop`, merges). They are detected at the next Stop by the invariant tests, not prevented.
4. **No OS sandbox on native Windows** (F9). The download allowlist applies only to recognised network programs and hints; other programs can still open connections.
5. **Read deny rules do not cover scripts that open files themselves** (F6). Secrets outside the listed names, or read through a script, remain readable. Keep secrets out of the project and the home directory where possible.
6. **Reviewer subagent hooks need workspace trust.** Without it, Claude Code skips their frontmatter hooks (sub-agents docs) and reviewer Bash falls back to the project-wide guard only. That still blocks destructive operations but allows arbitrary read-only commands. Reviewers never have Write, Edit, NotebookEdit or PowerShell.
7. **Guardrail edits rely on a human reading the prompt.** Changes to `.claude/settings.json` and `.claude/hooks/**` through the Edit tool are gated by `ask` rules; approving one carelessly can weaken the guardrails.
8. **`CLAUDE_PROJECT_DIR` is the folder where the session started.** Starting Claude Code in a subfolder would shift every project-relative check. Always start it at the repository root (README quick start).
9. **Strictness costs some false positives.** A command that mentions a locked or internal path and contains any non-read-only segment is blocked, and `git add` of a missing path fails closed. Split such commands, or use the Edit tool, which asks first.
10. **Lock tags exist only locally until pushed.** The CI checkout fetches no tags, so the PREREG invariant is enforced on the researcher's machine and through the Stop gate, not in CI. Push `prereg-v*` tags once they are created (Phase 6).
