# Phase 12 checks (26 to 28 Oct 2026)

Evidence for the claims-ledger rows E-70 to E-72. Everything here was run on the development laptop (Windows 11). Nothing was published, uploaded or tagged.

## 1. Installed wheel, empty folder (E-70)

Built at `d183423`: `driftwatch_lifetime-0.1.0-py3-none-any.whl`, 206,715 bytes, 89 files; source archive `driftwatch_lifetime-0.1.0.tar.gz`, 165,857 bytes. `scripts/check_release.py --dist` and `twine check --strict` pass on both. The wheel was installed with `uv pip install` into a fresh Python 3.12 environment and run from a folder that is not a checkout and holds no data:

- `driftwatch --version` printed `driftwatch 0.1.0`;
- `driftwatch smoke --out smoke-report` printed `MATCH: 2 rows, max |diff| 0.000000 (tolerance 0.002)` and exited 0.

The capture is `docs/architecture/img/term-smoke.png`. The same two commands run on fresh Linux and Windows runners in `release.yml` (job `smoke-wheel`) and `clean-room.yml`; those workflows have not run yet because the repository is not public.

## 2. The cleanup commit changed no stored number (E-71)

Baseline taken at `f7dffb5`, before the edits; compared with the working tree of commit `b87c6eb` (stale docstrings, one shared file-hash helper, one shared window-key helper, logging instead of `print`, return annotations):

| Check | Result |
|---|---|
| Smoke run, predictions table | 40 rows, 16 columns in both; only `config_hash` and `window_id` differ (both embed the code version), every probability, decision and label is equal |
| Smoke run, slot table | 4 rows, 30 columns; only `config_hash` and `window_id` differ |
| Smoke run, window table | 2 rows, 51 columns; `config_hash`, `window_id` and `fit_seconds` (a timing) differ |
| `make_tables.py`, `make_e3.py`, `make_e4.py` rebuilt from the stored E1 to E4 predictions | every command exit 0; `git status reports/` empty, so every committed table is reproduced byte for byte |
| `scripts/check_e4_vs_e3.py` | exit 0 |

## 3. Filtered public history, rehearsal (E-72)

`scripts/make_public_history.py --out <scratch>` on the repository at `3a5b519`: 193 commits cloned as a mirror and rewritten with `git filter-repo --path docs/source --invert-paths`. Checks: 0 commits touch `docs/source`; no tree contains it; tags `prereg-v1`, `prereg-v2` and `prereg-v3` survive; the number of commits is unchanged (193); the largest blob is 415,219 bytes (`data/manifest.json`); no secret-shaped text in any revision. The script printed `public history: OK (nothing was pushed)` and wrote a map of 193 old and new hashes. The repository before filtering is 13 MB.

## 4. The deploy step of `docs.yml`, simulated

The shell of the `deploy` job was run, unchanged, against a scratch repository with a bare remote, four times: a branch build (creates the `gh-pages` branch), a tag build (adds `v0.1.0/`), a later branch build with new content (replaces `latest/` and keeps `v0.1.0/`), and the same content again (nothing to publish). Result: `gh-pages` holds `.nojekyll`, `index.html`, `latest/`, `v0.1.0/`, `versions.html` and `versions.json`; three commits were made, the fourth run made none. Not simulated: the GitHub token and Pages hosting.

## Not checked

Anything that needs the public repository: the workflows on GitHub's runners, the Trusted Publisher registration, a TestPyPI upload, the Zenodo record. These are listed in `docs/RELEASING.md` with the go each needs.
