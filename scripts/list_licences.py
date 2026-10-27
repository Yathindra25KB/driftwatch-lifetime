"""List the licence of every package in uv.lock from its installed metadata (no network).

    uv run python scripts/list_licences.py                    # markdown table on stdout
    uv run python scripts/list_licences.py --check            # exit 1 if any licence is unknown

For each locked package (the project itself excluded) it reads the installed distribution's
metadata: ``License-Expression``, else ``License``, else the ``License ::`` classifiers, in
that order. A package with none of these is reported as ``UNKNOWN`` and has to be looked up by a
person. Whether a package is a direct runtime dependency, a direct development dependency or a
transitive one comes from ``pyproject.toml``.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(spec: str) -> str:
    return norm(re.split(r"[<>=!~;\[ ]", spec.strip(), maxsplit=1)[0])


def locked_packages(lock: Path) -> list[str]:
    data = tomllib.loads(lock.read_text(encoding="utf-8"))
    return sorted(norm(p["name"]) for p in data["package"])


def direct_dependencies(pyproject: Path) -> tuple[set[str], set[str]]:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    runtime = {requirement_name(s) for s in data["project"].get("dependencies", [])}
    dev = {requirement_name(s) for s in data.get("dependency-groups", {}).get("dev", [])}
    return runtime, dev


def licence_of(name: str) -> tuple[str, str, str]:
    """(version, licence, where it was read from) of an installed distribution."""
    try:
        dist = metadata.distribution(name)
    except metadata.PackageNotFoundError:
        return "not installed", "UNKNOWN", "-"
    md = dist.metadata
    expr = (md.get("License-Expression") or "").strip()
    if expr:
        return dist.version, expr, "License-Expression"
    text = (md.get("License") or "").strip()
    if text and len(text) <= 80 and "\n" not in text:
        return dist.version, text, "License"
    classifiers = [
        c.split("::")[-1].strip()
        for c in md.get_all("Classifier") or []
        if c.startswith("License ::")
    ]
    if classifiers:
        return dist.version, "; ".join(classifiers), "classifier"
    if text:
        return dist.version, "see the package's licence text", "License (long text)"
    return dist.version, "UNKNOWN", "-"


def rows(root: Path = ROOT) -> list[dict[str, str]]:
    runtime, dev = direct_dependencies(root / "pyproject.toml")
    out = []
    for name in locked_packages(root / "uv.lock"):
        if name == "driftwatch-lifetime":
            continue
        version, lic, where = licence_of(name)
        kind = (
            "direct, runtime"
            if name in runtime
            else "direct, development"
            if name in dev
            else "transitive"
        )
        out.append(
            {"package": name, "version": version, "licence": lic, "read from": where, "kind": kind}
        )
    return out


def render(table: list[dict[str, str]]) -> str:
    lines = ["| Package | Version | Licence | Read from | Kind |", "|---|---|---|---|---|"]
    for r in table:
        lines.append(
            f"| {r['package']} | {r['version']} | {r['licence']} | {r['read from']} | {r['kind']} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if any licence is unknown")
    args = ap.parse_args(argv)
    table = rows()
    print(render(table))
    unknown = [r["package"] for r in table if r["licence"] == "UNKNOWN"]
    if unknown:
        print(f"\nUNKNOWN: {', '.join(unknown)}", file=sys.stderr)
    return 1 if args.check and unknown else 0


if __name__ == "__main__":
    raise SystemExit(main())
