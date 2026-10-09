# ADR-0001: Tooling and guardrail design

**Status:** PROPOSED (draft; finalised at Phase 1 closeout after the adversarial review)
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

(Details of each hook, the latency measurements and the crash policy are filled in during steps E–H.)

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

## Residual risks
(Final list after the adversarial review in step G.)
