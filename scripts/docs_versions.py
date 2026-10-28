"""Index the versioned documentation on the gh-pages branch (stdlib only).

    python scripts/docs_versions.py <site-root>

The site root holds one folder per version: `latest/` (built from main) and `vX.Y.Z/` (one per
release tag). This writes `versions.json`, a `versions.html` page that links every version,
an `index.html` that redirects to `latest/`, and `.nojekyll`. Run by .github/workflows/docs.yml
after it copies a fresh build into place.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

VERSION_DIR = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def versions(root: Path) -> list[dict[str, str]]:
    """`latest` first, then released versions, newest first."""
    released = sorted(
        (tuple(int(g) for g in m.groups()), p.name)
        for p in root.iterdir()
        if p.is_dir() and (m := VERSION_DIR.match(p.name))
    )
    out = []
    if (root / "latest").is_dir():
        out.append({"name": "latest", "url": "latest/", "note": "built from main"})
    out += [{"name": n, "url": f"{n}/", "note": "release"} for _, n in reversed(released)]
    return out


def write_index(root: Path) -> list[dict[str, str]]:
    found = versions(root)
    (root / "versions.json").write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
    items = "\n".join(
        f'<li><a href="{html.escape(v["url"])}">{html.escape(v["name"])}</a>'
        f" ({html.escape(v['note'])})</li>"
        for v in found
    )
    (root / "versions.html").write_text(
        "<!doctype html><meta charset=utf-8><title>DriftWatch documentation versions</title>"
        f"<h1>DriftWatch documentation versions</h1><ul>\n{items}\n</ul>\n",
        encoding="utf-8",
    )
    (root / "index.html").write_text(
        '<!doctype html><meta charset=utf-8><meta http-equiv="refresh" content="0; url=latest/">'
        '<link rel="canonical" href="latest/"><title>DriftWatch</title>'
        '<a href="latest/">DriftWatch documentation</a>\n',
        encoding="utf-8",
    )
    (root / ".nojekyll").write_text("", encoding="utf-8")
    return found


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or not Path(args[0]).is_dir():
        print(
            __doc__.strip().splitlines()[0] + "\nusage: docs_versions.py <site-root>",
            file=sys.stderr,
        )
        return 2
    found = write_index(Path(args[0]))
    print(", ".join(v["name"] for v in found) or "no versions yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
