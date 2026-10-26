"""Zenodo metadata dry run on the sandbox (stdlib only; docs/RELEASING.md step 5).

    uv run python scripts/zenodo_dry_run.py --check     # offline: .zenodo.json is well formed
    uv run python scripts/zenodo_dry_run.py             # sandbox draft from .zenodo.json
    uv run python scripts/zenodo_dry_run.py --delete ID # remove that sandbox draft

The sandbox (sandbox.zenodo.org) is a separate site with its own accounts; nothing created
there mints a real DOI. The personal access token (scope deposit:write) is read with getpass
at the prompt or from ZENODO_SANDBOX_TOKEN, and is never written to disk. The draft is never
published by this script.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://sandbox.zenodo.org/api/deposit/depositions"
REQUIRED = ("title", "upload_type", "description", "creators", "license", "access_right")
RELATIONS = {"isSupplementTo", "isDocumentedBy", "isIdenticalTo", "isPartOf", "references"}


def load(root: Path = ROOT) -> dict:
    return json.loads((root / ".zenodo.json").read_text(encoding="utf-8"))


def check(meta: dict) -> list[str]:
    """Offline checks of the fields the Zenodo GitHub integration reads."""
    problems = [f"missing field {k}" for k in REQUIRED if not meta.get(k)]
    if meta.get("upload_type") != "software":
        problems.append("upload_type must be software")
    for c in meta.get("creators", []):
        if "," not in c.get("name", ""):
            problems.append(f"creator name {c.get('name')!r} must be 'Family, Given'")
    for r in meta.get("related_identifiers", []):
        if r.get("relation") not in RELATIONS:
            problems.append(f"unexpected relation {r.get('relation')!r}")
        if not str(r.get("identifier", "")).startswith("https://"):
            problems.append(f"identifier {r.get('identifier')!r} is not an https URL")
    return problems


def _request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
    return json.loads(raw) if raw else {}


def _token() -> str:
    return os.environ.get("ZENODO_SANDBOX_TOKEN") or getpass.getpass("sandbox token: ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="offline check only")
    ap.add_argument("--delete", type=int, metavar="ID", help="delete a sandbox draft")
    args = ap.parse_args(argv)
    meta = load()
    problems = check(meta)
    for p in problems:
        print(p, file=sys.stderr)
    if problems or args.check:
        print("zenodo metadata: " + ("FAIL" if problems else "OK"))
        return 1 if problems else 0
    try:
        if args.delete:
            _request("DELETE", f"{API}/{args.delete}", _token())
            print(f"deleted sandbox draft {args.delete}")
            return 0
        draft = _request("POST", API, _token(), {"metadata": meta})
    except urllib.error.HTTPError as exc:
        print(f"sandbox refused the metadata: HTTP {exc.code}: {exc.read().decode()[:2000]}")
        return 1
    print(f"draft {draft['id']} created (not published): {draft['links']['html']}")
    print(f"remove it with: uv run python scripts/zenodo_dry_run.py --delete {draft['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
