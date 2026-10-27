# Quality and release

How the project keeps its promises while it changes: the guardrails that run while code is written, the checks that run on every push, and the pipelines that publish a release and keep the project current afterwards.

## Guardrails while working

The repository is developed with an AI coding assistant under a set of hooks that turn the hard rules into blocks. They are part of the repository (`.claude/`), so a reviewer can read exactly what was enforced.

```{mermaid}
flowchart TD
    act["an edit, a shell command or a commit"]
    pre["PreToolUse: guard.py"]
    blk["blocked: message says why;<br/>write an ADR or ask the researcher"]
    ok["allowed"]
    post["PostToolUse: format.py<br/>(ruff on the edited file)"]
    stop["Stop: stop_gate.py<br/>runs the fast tests"]
    red["red tests: keep working"]
    done["session may end"]
    perm["permissions: deny reading secrets,<br/>deny editing data/ and docs/source/"]

    act --> perm --> pre
    pre -->|"locked file, force push, git add data/ or results/,<br/>recursive delete, unlisted download host"| blk
    pre --> ok --> post --> stop
    stop -->|"fail"| red
    stop -->|"pass"| done
```

*Figure 11. The development loop. The guard is a stdlib-only Python script that works from Git Bash, PowerShell and Linux CI; it fails closed when it cannot parse a command that touches a protected operation.*

| Layer | What it enforces | Test |
|---|---|---|
| `guard.py` (PreToolUse) | no edit to the pre-registration after its tag, tagged addenda or committed golden files; no force push; no `git add` of `data/` or `results/`; no recursive delete outside temporary folders; downloads only from an allow-list of hosts | `tests/test_guard.py`, and `scripts/check_guardrails.py`, which runs every scenario against a temporary repository and never the real one |
| `format.py` (PostToolUse) | ruff formats each edited file | the format check in CI |
| `stop_gate.py` (Stop) | the fast tests must pass before a session can finish | the fast suite |
| `permissions` | secrets cannot be read; `data/` and `docs/source/` cannot be edited | settings validated against the published schema (ADR-0001) |
| `tests/test_repo_invariants.py` | the pre-registration equals its tag, no golden file changed, no `data/` or `results/` file is tracked | runs on every stop and in CI |
| Reviewer agents | `leakage-reviewer` (temporal leakage, C1 to C3, delay, calibration) and `stats-reviewer` (statistics, claim traceability), read-only | their findings are recorded under `docs/reviews/` and the fixes carry tests |

A block is a rule, not a bug: when the guard stops a change the response is an ADR or a question to the researcher, never a workaround.

## Tests

| Suite | What it is for |
|---|---|
| fast (`pytest -q`) | unit, property and integration tests on a synthetic fixture; the default and the Stop gate |
| slow (`pytest -m slow`) | whole-grid synthetic runs, the table builders for E3 and E4, the mutation kill matrix, the distribution build |
| golden files | locked expected outputs, e.g. the smoke Table 1; the guard prevents edits |
| mutation matrix | deliberate breakages of the slicer; each must be caught ([W-07](../CLAIMS.md)) |
| guardrail demo | every guard scenario against a throw-away repository |
| spy test | held-back labels are reachable only through the queue (see [simulator](simulator.md)) |
| clean-clone check | a fresh clone installs from the lock file, passes the suites and reproduces Table 1 [E-67](../CLAIMS.md) |

Per-module coverage is in `reports/coverage.md`.

## Continuous integration and release

```{mermaid}
flowchart TB
    tag["signed tag vX.Y.Z pushed"] --> chk["check_release.py<br/>version = tag = CHANGELOG = CITATION"]
    chk --> bld["uv build, twine check --strict,<br/>no data in the files"]
    bld --> smk["install the wheel in a fresh venv;<br/>driftwatch smoke on Linux and Windows"]
    smk --> gate1{{"GO: environment pypi<br/>researcher approves"}}
    gate1 --> pypi["upload to PyPI<br/>(Trusted Publishing, OIDC)"]
    pypi --> draft["draft GitHub Release<br/>(notes from CHANGELOG, files attached)"]
    draft --> gate2{{"GO: researcher publishes<br/>the draft release"}}
    gate2 --> zen["Zenodo integration<br/>mints the DOI"]
```

*Figure 12. The release path. Two irreversible steps, two separate decisions: approving the `pypi` environment uploads the files, and publishing the draft release is what makes Zenodo mint a DOI. No long-lived secret exists: publishing uses short-lived OpenID Connect tokens.*

The other pipelines run on their own triggers:

| Trigger | Workflow | What it does |
|---|---|---|
| push or pull request | `ci.yml` | lint, format check, fast and slow tests, guardrail demonstration, smoke reproduction on Linux; fast tests, guardrails and smoke on Windows |
| push or pull request; weekly | `docs.yml` | strict Sphinx build and external link check |
| merge to `main` | `docs.yml` | deploys the build to `gh-pages/latest/` |
| tag `vX.Y.Z` | `docs.yml` | deploys the build to `gh-pages/vX.Y.Z/`, which stays frozen for that release |
| manual | `release.yml` | rehearsal: the same build and wheel smoke, then upload to TestPyPI |
| manual | `clean-room.yml` | a fresh runner installs from TestPyPI or PyPI with no checkout and runs the smoke; optionally runs the full Table 1 from a clone |
| monthly | `arxiv-audit.yml` | opens an issue listing new candidate papers |

Design choices in the release path:

- **The wheel must work alone.** The smoke job installs the built wheel into an empty virtual environment on Linux and Windows, in a folder that is not a checkout, and runs `driftwatch smoke`. A package that only works from a clone cannot be published.
- **Nothing but code ships.** `scripts/check_release.py` opens the wheel and the source archive and fails on any dataset, result, secret or course document, and on a wheel over one megabyte. The synthetic fixture travels only in the source archive.
- **Irreversible steps are gated.** The PyPI upload and the DOI cannot be undone, so each waits for an explicit decision; rehearsal on TestPyPI comes first ([RELEASING](../RELEASING.md)).
- **Actions are pinned to commit hashes**, with the version in a comment, so a moved tag cannot change what runs in the privileged job.

## Maintenance

Recurring work is documented as prompts, commands and expected outputs in [MAINTENANCE](../MAINTENANCE.md): a monthly arXiv audit (a script finds candidates, a skill triages them into the related-work addendum), a quarterly dependency refresh that must not move any table, a dataset-version watch, a release check and issue triage. The rule that binds all of them: a maintenance change never changes a reported number; if it would, it becomes a pre-registered change request instead.
