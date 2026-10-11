"""Download the upstream feature files (never samples or binaries) with resume support.

LAMDA comes from Hugging Face at a pinned commit; BODMAS from the Google Drive folder its
authors publish. A Drive quota or permission error is never worked around: it raises
:class:`ManualDownloadRequired` with exact browser steps for the researcher.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from driftwatch.data.cache import Layout, atomic_write_bytes
from driftwatch.data.sources import BODMAS, LAMDA

log = logging.getLogger(__name__)

SOURCE_FILE = "SOURCE.json"


class ManualDownloadRequired(RuntimeError):
    """Automated download failed; the message holds the manual steps."""


def _write_source(path: Path, record: dict[str, Any]) -> None:
    text = json.dumps(record, sort_keys=True, indent=2) + "\n"
    atomic_write_bytes(path, text.encode("utf-8"))


def read_source(raw_dir: Path) -> dict[str, Any]:
    path = raw_dir / SOURCE_FILE
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `driftwatch data download` first")
    return json.loads(path.read_text(encoding="utf-8"))


def hf_environment(layout: Layout) -> dict[str, str]:
    """Keep the Hugging Face and Xet caches on the data drive (C: is nearly full)."""
    home = layout.root.resolve() / "raw" / ".hf_home"
    return {"HF_HOME": str(home), "HF_XET_CACHE": str(home / "xet")}


def download_lamda(layout: Layout, revision: str | None = None) -> Path:
    """Fetch the Baseline subset at a pinned commit into ``raw/lamda/<sha12>/``."""
    for key, value in hf_environment(layout).items():
        os.environ.setdefault(key, value)
    from huggingface_hub import HfApi, snapshot_download  # after the env is set

    info = HfApi().dataset_info(LAMDA.repo_id, revision=revision)
    sha = info.sha
    if not sha:
        raise RuntimeError("Hugging Face returned no commit sha for LAMDA")
    target = layout.raw("lamda") / sha[:12]
    log.info("LAMDA %s at %s -> %s", LAMDA.repo_id, sha, target)
    snapshot_download(
        LAMDA.repo_id,
        repo_type=LAMDA.repo_type,
        revision=sha,
        local_dir=target,
        allow_patterns=list(LAMDA.allow_patterns),
        max_workers=4,
    )
    _write_source(
        target / SOURCE_FILE,
        {
            "dataset": "lamda",
            "repo_id": LAMDA.repo_id,
            "revision": sha,
            "allow_patterns": list(LAMDA.allow_patterns),
            "url": LAMDA.url,
            "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )
    return target


def lamda_raw_dir(layout: Layout) -> Path:
    """The single downloaded LAMDA snapshot (a second one needs a new manifest entry)."""
    candidates = sorted(p for p in layout.raw("lamda").glob("*") if (p / SOURCE_FILE).exists())
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"expected one LAMDA snapshot under {layout.raw('lamda')}, found {len(candidates)}"
        )
    return candidates[0]


def _manual_steps(target: Path, reason: str) -> str:
    files = "\n".join(f"     - {name}" for name in BODMAS.files)
    return (
        f"BODMAS automated download failed ({reason}). Do not retry around the quota.\n"
        "Manual steps:\n"
        f"  1. Open {BODMAS.folder_url} in a browser (signed in to Google if asked).\n"
        "  2. Download these files (right-click > Download):\n"
        f"{files}\n"
        f"  3. Move them into {target.resolve()} (create the folder if needed).\n"
        "  4. Run `uv run driftwatch data download bodmas --manual` to record their hashes,\n"
        "     then `uv run driftwatch data build bodmas`."
    )


def download_bodmas(layout: Layout, manual: bool = False) -> Path:
    """Fetch the BODMAS feature files with gdown, resuming partial files."""
    target = layout.raw("bodmas")
    target.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "dataset": "bodmas",
        "drive_folder_id": BODMAS.drive_folder_id,
        "url": BODMAS.folder_url,
        "method": "manual" if manual else "gdown",
    }
    if manual:
        missing = [n for n in BODMAS.files if not (target / n).exists()]
        if missing:
            raise ManualDownloadRequired(_manual_steps(target, f"missing {missing}"))
        record["file_ids"] = {}
    else:
        import gdown
        from gdown.exceptions import DownloadError, FileURLRetrievalError

        try:
            listing = gdown.download_folder(
                id=BODMAS.drive_folder_id, skip_download=True, quiet=True, use_cookies=False
            )
            ids = {Path(item.path).name: item.id for item in listing}
            record["file_ids"] = {n: ids[n] for n in BODMAS.files if n in ids}
            missing = [n for n in BODMAS.files if n not in ids]
            if missing:
                raise ManualDownloadRequired(_manual_steps(target, f"not in folder: {missing}"))
            for name in BODMAS.files:
                log.info("BODMAS %s (id %s)", name, ids[name])
                gdown.download(
                    id=ids[name],
                    output=str(target / name),
                    resume=True,
                    quiet=False,
                    use_cookies=False,
                )
        except (FileURLRetrievalError, DownloadError) as exc:
            raise ManualDownloadRequired(_manual_steps(target, type(exc).__name__)) from exc
    record["downloaded_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    _write_source(target / SOURCE_FILE, record)
    return target
