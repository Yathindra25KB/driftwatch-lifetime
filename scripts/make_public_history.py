"""Make a filtered copy of the repository history for the public repository (local only).

    uvx git-filter-repo --version                       # the tool this script drives
    uv run python scripts/make_public_history.py --out ../public-history

Clones this repository as a mirror into --out/mirror.git, removes the paths that must not be
public from every commit with git-filter-repo (default: docs/source, the course documents that
carry no licence), verifies the result and writes --out/commit_map.csv (old and new commit hash).
Every commit hash changes when the first commit is rewritten, so the hashes cited in
docs/CLAIMS.md, docs/PHASES.md and the ADRs can be found again only through that map.

It never pushes and never touches this repository. Pushing the result to a new public
repository is a separate, researcher-gated step (docs/RELEASING.md). Exit code 0 when every
check passes, 1 when one fails, 2 when git-filter-repo is not available.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DROP = ("docs/source",)
MAX_BLOB_BYTES = 10_000_000
REQUIRED_TAG_PREFIX = "prereg-v"
# secret shapes worth stopping for: cloud and GitHub tokens, PyPI tokens, private key blocks
SECRET_PATTERN = (
    r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{20,}"
    r"|pypi-AgE[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return out.stdout


def revisions(repo: Path) -> list[str]:
    return git(repo, "rev-list", "--all").split()


def touching(repo: Path, path: str) -> list[str]:
    """Commits on any ref that touch `path`."""
    return git(repo, "log", "--all", "--format=%H", "--", path).split()


def present_in_trees(repo: Path, path: str) -> list[str]:
    """Revisions whose tree contains anything under `path`."""
    return [
        rev
        for rev in revisions(repo)
        if git(repo, "ls-tree", "-r", "--name-only", rev, "--", path).strip()
    ]


def largest_blob(repo: Path) -> int:
    objects = subprocess.run(
        ["git", "-C", str(repo), "rev-list", "--objects", "--all"],
        check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip
    sizes = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "--batch-check=%(objecttype) %(objectsize)"],
        input=objects, check=True, capture_output=True, text=True,
    ).stdout  # fmt: skip
    blobs = [int(s.split()[1]) for s in sizes.splitlines() if s.startswith("blob ")]
    return max(blobs, default=0)


def secret_hits(repo: Path) -> list[str]:
    """Lines matching a secret shape in any revision (empty list: none found)."""
    revs = revisions(repo)
    hits: list[str] = []
    for i in range(0, len(revs), 50):  # keep each command line short
        res = subprocess.run(
            ["git", "-C", str(repo), "grep", "-I", "-l", "-E", SECRET_PATTERN, *revs[i : i + 50]],
            capture_output=True, text=True,
        )  # fmt: skip
        hits += res.stdout.split()
    return hits


def verify(repo: Path, source: Path, dropped: tuple[str, ...]) -> list[str]:
    """Problems with the filtered repository; an empty list means every check passed."""
    problems = []
    for path in dropped:
        if touching(repo, path):
            problems.append(f"{len(touching(repo, path))} commit(s) still touch {path}")
        if present_in_trees(repo, path):
            problems.append(f"{path} is still present in a tree")
    src_tags = set(git(source, "tag").split())
    new_tags = set(git(repo, "tag").split())
    if src_tags - new_tags:
        problems.append(f"tags lost: {sorted(src_tags - new_tags)}")
    if not any(t.startswith(REQUIRED_TAG_PREFIX) for t in new_tags):
        problems.append("no prereg-v* tag survived")
    if len(revisions(repo)) != len(revisions(source)):
        problems.append("the number of commits changed")
    if (size := largest_blob(repo)) > MAX_BLOB_BYTES:
        problems.append(f"a blob of {size} bytes is larger than {MAX_BLOB_BYTES}")
    if hits := secret_hits(repo):
        problems.append(f"secret-shaped text in {len(hits)} file revision(s): {hits[:3]}")
    return problems


def write_commit_map(repo: Path, out: Path) -> int:
    """Old and new hash of every commit, from git-filter-repo's own record."""
    raw = (repo / "filter-repo" / "commit-map").read_text(encoding="utf-8").splitlines()[1:]
    pairs = [ln.split() for ln in raw if re.fullmatch(r"[0-9a-f]{40} [0-9a-f]{40}", ln)]
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["old", "new"])
        writer.writerows((old, new) for old, new in pairs if set(new) != {"0"})
    return len(pairs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True, help="a new, empty folder")
    ap.add_argument("--source", type=Path, default=ROOT, help="repository to copy")
    ap.add_argument("--drop", action="append", help="path to remove (default docs/source)")
    args = ap.parse_args(argv)
    dropped = tuple(args.drop or DEFAULT_DROP)
    if args.out.exists() and any(args.out.iterdir()):
        print(f"{args.out} is not empty", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    mirror = args.out / "mirror.git"
    subprocess.run(["git", "clone", "-q", "--mirror", str(args.source), str(mirror)], check=True)
    cmd = ["uvx", "git-filter-repo", "--force"]
    for path in dropped:
        cmd += ["--path", path]
    cmd.append("--invert-paths")
    try:
        subprocess.run(cmd, cwd=mirror, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"git-filter-repo failed or is not available: {exc}", file=sys.stderr)
        return 2
    problems = verify(mirror, args.source, dropped)
    n = write_commit_map(mirror, args.out / "commit_map.csv")
    print(f"filtered {n} commits into {mirror}; commit map: {args.out / 'commit_map.csv'}")
    for p in problems:
        print(f"PROBLEM: {p}", file=sys.stderr)
    print("public history: " + ("FAIL" if problems else "OK (nothing was pushed)"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
