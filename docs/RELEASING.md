# Releasing

How a version of `driftwatch-lifetime` reaches TestPyPI, PyPI, GitHub Releases and Zenodo. The pipeline is `.github/workflows/release.yml`. It uses Trusted Publishing (OpenID Connect), so no API token exists anywhere.

**Irreversible steps.** A PyPI file name, once uploaded, can never be uploaded again, even after deletion. A Zenodo DOI can never be deleted. Each step marked **GO** needs the researcher's explicit go at the time, never a standing one.

## One-time setup (the researcher, in a browser)

| Where | What | Values |
|---|---|---|
| GitHub, repo *Settings → Environments* | Create `testpypi` and `pypi`; give `pypi` a required reviewer (the researcher) | — |
| GitHub, repo *Settings → Pages* | Source: *Deploy from a branch*, branch `gh-pages`, folder `/` | created by the first docs deploy |
| TestPyPI, *Account → Publishing → Add a new pending publisher* (GitHub) | PyPI project name `driftwatch-lifetime`; owner `Yathindra25KB`; repository `driftwatch-lifetime`; workflow `release.yml`; environment `testpypi` | https://test.pypi.org/manage/account/publishing/ |
| PyPI, same page | Same values, environment `pypi` | https://pypi.org/manage/account/publishing/ |
| Zenodo, *Account → GitHub* | Log in with GitHub, then switch the repository `driftwatch-lifetime` **on** before the first release is published | https://zenodo.org/account/settings/github/ |
| GitHub, *Settings → SSH and GPG keys → New SSH key*, type **Signing key** | The public half of the release signing key | see "Signing key" below |

A pending publisher does not reserve the name. If someone else registers `driftwatch-lifetime` before the first upload, the pending publisher is invalidated. Do the first upload soon after adding it. Fallback name: `driftwatch-sec` (ADR-0003).

### Signing key (SSH, once per machine)

```bash
ssh-keygen -t ed25519 -C "yathindrakb25@gmail.com" -f ~/.ssh/driftwatch_signing
git config gpg.format ssh
git config user.signingkey ~/.ssh/driftwatch_signing.pub
echo "yathindrakb25@gmail.com $(cat ~/.ssh/driftwatch_signing.pub)" > ~/.ssh/allowed_signers
git config gpg.ssh.allowedSignersFile ~/.ssh/allowed_signers
```

The private key never leaves the machine and is never committed.

## First release only: the public repository (GO)

The development repository `Yathindra25KB/Driftwatch-` is private and its history contains `docs/source/` (course documents with no stated licence). The public repository is a new one, `Yathindra25KB/driftwatch-lifetime`, made from a filtered copy of that history. The private repository stays as the archive.

1. **Finish the merges first.** Merge the open pull requests into `main` of the development repository (GO), because the filtered copy is taken from what is on `main` and the tags.
2. **Make the filtered copy** (local, never pushes):

   ```bash
   uv run python scripts/make_public_history.py --out ../public-history
   ```

   It clones a mirror, removes `docs/source` from every commit with `git-filter-repo`, and checks that no commit or tree still holds the path, that every tag (including `prereg-v1` to `prereg-v3`) and every commit survived, that no blob is large, and that no secret-shaped text is present. It writes `commit_map.csv` (old and new hash).
3. **Create and fill the public repository (GO, public and permanent).** In a browser or with `gh`, create `Yathindra25KB/driftwatch-lifetime` as an empty public repository, then push only `main` and the tags from the mirror:

   ```bash
   cd ../public-history/mirror.git
   git push https://github.com/Yathindra25KB/driftwatch-lifetime.git main --tags
   ```

4. **Make the commit hashes findable.** Every hash cited in `docs/CLAIMS.md`, `docs/PHASES.md` and the decision records is a hash of the development history, and filtering changed all of them. In a pull request on the public repository, add `commit_map.csv` as `docs/commit_map.csv` and one sentence under the rules in `docs/CLAIMS.md` saying so.
5. **Switch on the repository's services** (the table above): Pages, environments, branch protection, then the pending publishers.

## Every release

1. **Branch and changes.** Work on a branch and merge to `main` through a pull request with CI green.
2. **Version.** Choose the next version (semantic versioning; before 1.0.0, a minor bump may break the CLI). Set it in `pyproject.toml` and `CITATION.cff` (`version`, `date-released`). Move the `[Unreleased]` notes in `CHANGELOG.md` into a dated section. `python scripts/check_release.py` must print `OK`.
3. **Audits** (all clean, with evidence in the pull request):
   - `uv run pytest -q` and `uv run pytest -q -m slow`; `uv run ruff check . && uv run ruff format --check .`; `uv run python scripts/check_guardrails.py`
   - `uv run python scripts/claims_audit.py` (PASS); `uv run python scripts/check_bib.py`
   - `uv run python scripts/list_licences.py`, with `docs/licence_audit.md` updated if anything changed
   - docs: `uv run --group docs sphinx-build -W --keep-going -b html docs docs/_build/html` and `-b linkcheck`
   - architecture PDF: `uvx --with playwright python scripts/export_architecture_pdf.py` prints the architecture section to `reports/architecture_report.pdf` with the Edge or Chrome that is installed (nothing is downloaded; Playwright is only a driver and is not a project dependency). Look at every page: the script checks that each diagram was drawn, not how it looks. The release workflow attaches the file to the draft release when it is committed.
4. **Rehearsal (GO).** Push a commit with version `X.Y.ZrcN` to a branch. Run *Actions → Release → Run workflow*, target `testpypi`. Then run *Actions → Clean room → Run workflow*, source `testpypi`. Both OS legs must pass. Release candidates go to TestPyPI only.
5. **Zenodo metadata dry run** (first release, or when `.zenodo.json` changes). `uv run python scripts/zenodo_dry_run.py` sends `.zenodo.json` to sandbox.zenodo.org as an unpublished draft, using a sandbox token that you type at its prompt (never stored). Read the rendered draft, then delete it.
6. **Tag (GO for PyPI).** On `main`, at the merged release commit:

   ```bash
   git tag -s vX.Y.Z -m "DriftWatch X.Y.Z"
   git tag -v vX.Y.Z            # must say "Good signature"
   git push origin vX.Y.Z
   ```

   The workflow runs: build → wheel smoke on Linux and Windows → `pypi` environment approval (**GO**, uploads to PyPI) → a **draft** GitHub Release with the notes and files attached.
7. **Publish the release (GO for the DOI).** Open the draft on GitHub (*Releases*), read the notes and the attached files, then click **Publish release**. Zenodo mints the DOI only when a release is published, and a DOI can never be deleted, so this is a separate decision from the upload. Check that the Zenodo integration is switched on for the repository *before* this click.
8. **After the release.**
   - Put the version DOI and the concept DOI in `CITATION.cff` (`identifiers`) and the README badge, through a pull request.
   - Run *Clean room* with source `pypi`.
   - Check that the docs at `/vX.Y.Z/` are live.
   - Add the evidence (run URLs, DOI) to `docs/CLAIMS.md` and `docs/PHASES.md`.

## If something goes wrong

| Problem | Do |
|---|---|
| The build or smoke job fails | Nothing was published. Fix on a branch; delete the tag locally and remotely only if it is not a `prereg-v*` tag (the guard blocks those) |
| PyPI rejects the upload with "Private :: Do Not Upload" | Intended: the classifier must be removed in the release commit (ADR-0003) |
| A bad file reached PyPI | Yank it on PyPI (*Manage → Releases → Yank*) and release X.Y.Z+1. Never delete and re-upload the same version |
| The DOI record has wrong metadata | Edit the metadata on Zenodo (allowed); the files of a published version are frozen, so fix them in the next version |
