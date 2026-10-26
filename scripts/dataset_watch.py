"""Dataset-version watch (stdlib only; docs/MAINTENANCE.md, quarterly or before a release).

    uv run python scripts/dataset_watch.py            # compare upstream with data/manifest.json

LAMDA: the Hugging Face revision of IQSeC-Lab/LAMDA against the revision in the manifest.
BODMAS: the newest commit of the authors' project repository (whyisyoung/BODMAS, which hosts
the project page) against the manifest's download time. A change is a prompt to read the
upstream notes, never a reason to rebuild silently: a new dataset version is a CHANGE_REQUEST
with a new manifest, a rerun and an addendum (docs/MAINTENANCE.md).

Exit code 0: no change; 1: something changed upstream; 2: upstream could not be read.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAMDA_API = "https://huggingface.co/api/datasets/{repo_id}"
BODMAS_COMMITS = "https://api.github.com/repos/whyisyoung/BODMAS/commits?per_page=1"

Fetch = Callable[[str], object]


def fetch_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "driftwatch-dataset-watch"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def watch(manifest: dict, fetch: Fetch = fetch_json) -> list[dict]:
    """One row per dataset: name, recorded, upstream, changed."""
    rows = []
    lamda = manifest["datasets"]["lamda"]["source"]
    info = fetch(LAMDA_API.format(repo_id=lamda["repo_id"]))
    upstream = info.get("sha") if isinstance(info, dict) else None
    rows.append(
        {
            "dataset": "lamda",
            "recorded": lamda["revision"],
            "upstream": upstream,
            "changed": upstream != lamda["revision"],
        }
    )
    bodmas = manifest["datasets"]["bodmas"]["source"]
    commits = fetch(BODMAS_COMMITS)
    newest = commits[0]["commit"]["committer"]["date"] if commits else None
    # ISO 8601 UTC strings of the same shape compare correctly as text
    downloaded = bodmas["downloaded_utc"].replace("+00:00", "Z")
    rows.append(
        {
            "dataset": "bodmas",
            "recorded": f"downloaded {downloaded}",
            "upstream": f"newest project commit {newest}",
            "changed": bool(newest and newest > downloaded),
        }
    )
    return rows


def main() -> int:
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    try:
        rows = watch(manifest)
    except OSError as exc:
        print(f"upstream could not be read: {exc}", file=sys.stderr)
        return 2
    for r in rows:
        flag = "CHANGED" if r["changed"] else "same"
        print(f"{r['dataset']:7s} {flag:8s} recorded: {r['recorded']}  upstream: {r['upstream']}")
    return 1 if any(r["changed"] for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
