"""Release checks used by .github/workflows/release.yml (stdlib only).

    python scripts/check_release.py                  # pyproject, CITATION, CHANGELOG agree
    python scripts/check_release.py --tag v0.1.0     # ... and the tag names that version
    python scripts/check_release.py --dist dist      # built files hold no data and stay small
    python scripts/check_release.py --notes v0.1.0   # print that version's CHANGELOG section

Exit code 0 when every check passes, 1 with one line per problem otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_WHEEL_BYTES = 1_000_000
MAX_SDIST_BYTES = 5_000_000
# top-level folders that must never ship: datasets, results, course documents, local state
FORBIDDEN_ROOTS = ("data/", "results/", "docs/source/", ".claude-state/", ".venv/", ".cache/")
FORBIDDEN_NAMES = (".env", "settings.local.json")
FORBIDDEN_SUFFIXES = (".parquet", ".npz", ".npy", ".jsonl.gz", ".zip", ".pem", ".key")
# the synthetic fixture is the one dataset-shaped file allowed, and only in the sdist
ALLOWED_PREFIXES = ("tests/fixtures/synthetic/",)


def pyproject_version(root: Path = ROOT) -> str:
    return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "version"
    ]


def citation_version(root: Path = ROOT) -> str | None:
    m = re.search(
        r"^version:\s*['\"]?([^'\"\s]+)", (root / "CITATION.cff").read_text("utf-8"), re.M
    )
    return m.group(1) if m else None


def changelog_section(version: str, root: Path = ROOT) -> str | None:
    """Text of the `## [version]` section of CHANGELOG.md, or None if there is none."""
    text = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(
        rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", text, re.M | re.S
    )
    return m.group(1).strip() if m else None


def release_of(version: str) -> str:
    """The final release a pre-release rehearses: 0.1.0rc1 -> 0.1.0 (TestPyPI rehearsals)."""
    return re.sub(r"(a|b|rc)\d+$|\.dev\d+$", "", version)


def check_versions(tag: str | None, root: Path = ROOT) -> list[str]:
    problems = []
    v = pyproject_version(root)
    base = release_of(v)
    cv = citation_version(root)
    if cv != base:
        problems.append(f"CITATION.cff version {cv} != pyproject version {base}")
    if changelog_section(base, root) is None:
        problems.append(f"CHANGELOG.md has no section for {base}")
    if tag and tag != f"v{v}":
        problems.append(f"tag {tag} does not name pyproject version {v} (expected v{v})")
    return problems


def _forbidden(path: str) -> bool:
    """True for a member path (relative to the project root) that must not ship."""
    if path.startswith(ALLOWED_PREFIXES):
        return False
    name = path.rsplit("/", 1)[-1]
    return (
        path.startswith(FORBIDDEN_ROOTS)
        or name in FORBIDDEN_NAMES
        or path.endswith(FORBIDDEN_SUFFIXES)
    )


def _sdist_path(member: str) -> str:
    """An sdist member without its `<name>-<version>/` top folder."""
    return member.split("/", 1)[1] if "/" in member else ""


def check_dist(dist: Path) -> list[str]:
    problems = []
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        return [
            f"expected one wheel and one sdist in {dist}, found {len(wheels)} and {len(sdists)}"
        ]
    wheel, sdist = wheels[0], sdists[0]
    if wheel.stat().st_size > MAX_WHEEL_BYTES:
        problems.append(f"{wheel.name} is {wheel.stat().st_size} bytes (limit {MAX_WHEEL_BYTES})")
    if sdist.stat().st_size > MAX_SDIST_BYTES:
        problems.append(f"{sdist.name} is {sdist.stat().st_size} bytes (limit {MAX_SDIST_BYTES})")
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    problems += [f"{wheel.name}: forbidden member {n}" for n in names if _forbidden(n)]
    if not any(n.endswith("driftwatch/_golden/smoke_table1.csv") for n in names):
        problems.append(f"{wheel.name}: the smoke golden table is missing")
    with tarfile.open(sdist) as tf:
        members = tf.getnames()
    problems += [
        f"{sdist.name}: forbidden member {n}" for n in members if _forbidden(_sdist_path(n))
    ]
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", help="git tag to check against the version (empty: skip)")
    ap.add_argument("--dist", type=Path, help="folder with the built wheel and sdist")
    ap.add_argument("--notes", metavar="TAG", help="print the CHANGELOG section for TAG")
    args = ap.parse_args(argv)
    if args.notes:
        section = changelog_section(args.notes.removeprefix("v"))
        if section is None:
            print(f"CHANGELOG.md has no section for {args.notes}", file=sys.stderr)
            return 1
        print(section)
        return 0
    problems = check_dist(args.dist) if args.dist else check_versions(args.tag or None)
    for p in problems:
        print(p, file=sys.stderr)
    print("release check: " + ("FAIL" if problems else "OK"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
