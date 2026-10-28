"""Hash the stored predictions and optionally pack them into one private archive.

    uv run python scripts/archive_predictions.py                # write the hash manifest only
    uv run python scripts/archive_predictions.py --zip OUT.zip  # also pack the files into OUT.zip
    uv run python scripts/archive_predictions.py --verify       # check results/ against manifest

The manifest ``docs/predictions_manifest.csv`` lists, for the experiments E0 to E4, the per-slot
predictions, the slot tables, the run records and the ledgers under ``results/`` with their
SHA-256 and size. It is committed (it holds no data); the files themselves are not, and the archive
is meant for examiners who ask for it. Nothing is uploaded anywhere.
"""

from __future__ import annotations

import argparse
import csv
import logging
import zipfile
from pathlib import Path

from driftwatch.data.cache import sha256_file as sha256

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ("e0", "e1", "e2", "e3", "e4")
NAMES = ("predictions.parquet", "slots.parquet", "run.json", "ledger.jsonl")
LOG = logging.getLogger("archive")


def collect(results: Path, experiments: tuple[str, ...] = EXPERIMENTS) -> list[Path]:
    """The archived files, sorted by relative path."""
    found: list[Path] = []
    for exp in experiments:
        base = results / exp
        if base.is_dir():
            found.extend(p for p in base.rglob("*") if p.is_file() and p.name in NAMES)
    return sorted(found, key=lambda p: p.relative_to(results).as_posix())


def manifest_rows(results: Path, files: list[Path]) -> list[dict[str, str | int]]:
    return [
        {
            "path": p.relative_to(results).as_posix(),
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
        }
        for p in files
    ]


def write_manifest(rows: list[dict[str, str | int]], out: Path) -> None:
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def verify(results: Path, manifest: Path) -> list[str]:
    """Paths whose file is missing or whose hash differs from the manifest."""
    problems = []
    with manifest.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            path = results / row["path"]
            if not path.is_file():
                problems.append(f"missing {row['path']}")
            elif sha256(path) != row["sha256"]:
                problems.append(f"changed {row['path']}")
    return problems


def write_zip(results: Path, files: list[Path], out: Path) -> None:
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in files:
            archive.write(path, path.relative_to(results).as_posix())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--manifest", type=Path, default=ROOT / "docs/predictions_manifest.csv")
    parser.add_argument("--zip", type=Path, default=None, help="also pack the files into this zip")
    parser.add_argument("--verify", action="store_true", help="check results/ against the manifest")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.verify:
        problems = verify(args.results, args.manifest)
        for line in problems:
            LOG.error("%s", line)
        LOG.info("%d problems", len(problems))
        return 1 if problems else 0
    files = collect(args.results)
    rows = manifest_rows(args.results, files)
    write_manifest(rows, args.manifest)
    total = sum(int(r["bytes"]) for r in rows)
    LOG.info("%d files, %.2f GiB, manifest %s", len(rows), total / 2**30, args.manifest)
    if args.zip is not None:
        write_zip(args.results, files, args.zip)
        LOG.info("archive %s (%.2f GiB)", args.zip, args.zip.stat().st_size / 2**30)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
