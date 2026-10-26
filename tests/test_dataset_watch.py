"""scripts/dataset_watch.py: upstream changes are flagged against the manifest (no network)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


dw = load_script("dataset_watch")

MANIFEST = {
    "datasets": {
        "lamda": {"source": {"repo_id": "IQSeC-Lab/LAMDA", "revision": "abc"}},
        "bodmas": {"source": {"downloaded_utc": "2026-10-10T13:21:46+00:00"}},
    }
}


def fake(lamda_sha: str, bodmas_date: str):
    def fetch(url: str):
        if "huggingface" in url:
            return {"sha": lamda_sha}
        return [{"commit": {"committer": {"date": bodmas_date}}}]

    return fetch


def test_no_change() -> None:
    rows = dw.watch(MANIFEST, fake("abc", "2021-01-01T00:00:00Z"))
    assert [r["changed"] for r in rows] == [False, False]


def test_new_lamda_revision_and_newer_bodmas_commit_are_flagged() -> None:
    rows = dw.watch(MANIFEST, fake("def", "2026-11-01T00:00:00Z"))
    assert [r["changed"] for r in rows] == [True, True]


def test_the_real_manifest_has_the_fields_the_watch_reads() -> None:
    import json

    manifest = json.loads((ROOT / "data" / "manifest.json").read_text(encoding="utf-8"))
    rows = dw.watch(manifest, fake("x", "2000-01-01T00:00:00Z"))
    assert rows[0]["recorded"] == manifest["datasets"]["lamda"]["source"]["revision"]
