"""Command-line entry point `driftwatch`.

Phase 2 adds `data download|build|verify|inventory`. Later phases add `run` (Phase 4),
`grid` (Phase 6) and `reproduce table1` (Phase 7).
"""

import argparse
import logging
import sys
from pathlib import Path

from driftwatch import __version__

DATASET_CHOICES = ("lamda", "bodmas", "all")


def _datasets(name: str) -> tuple[str, ...]:
    return ("lamda", "bodmas") if name == "all" else (name,)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driftwatch",
        description="Time-aware malware-detector lifetime study (pre-release).",
    )
    parser.add_argument("--version", action="version", version=f"driftwatch {__version__}")
    sub = parser.add_subparsers(dest="command")

    data = sub.add_parser("data", help="download, cache, verify and inventory the datasets")
    data_sub = data.add_subparsers(dest="data_command", required=True)

    def add(name: str, help_text: str, dataset_default: str | None = None):
        p = data_sub.add_parser(name, help=help_text)
        if dataset_default is None:
            p.add_argument("dataset", choices=DATASET_CHOICES)
        else:
            p.add_argument("dataset", choices=DATASET_CHOICES, nargs="?", default=dataset_default)
        p.add_argument("--root", type=Path, default=Path("data"), help="data root (default data)")
        return p

    dl = add("download", "fetch upstream feature files (resumable)")
    dl.add_argument("--revision", help="LAMDA Hugging Face revision (default: current main)")
    dl.add_argument("--manual", action="store_true", help="record manually downloaded BODMAS")

    build = add("build", "stream raw files into per-unit caches (idempotent, resumable)")
    build.add_argument("--memory-cap-gb", type=float, default=1.5)
    build.add_argument("--batch-size", type=int, default=8192, help="rows per streamed batch")
    build.add_argument("--raw-root", type=Path, help="read raw files from another data root")

    add("verify", "check the manifest, file hashes and slot invariants", dataset_default="all")
    inv = add("inventory", "write reports/data_inventory.md with tables and plots", "all")
    inv.add_argument("--out", type=Path, default=Path("reports"))

    sl = add("slice", "slice a dataset into windows, checking C1-C3, and write the manifest", "all")
    sl.add_argument("--length", help="slot length override (default: the ADR-0004 preset)")
    sl.add_argument("--nT", type=int, default=4, help="training slots per window")
    sl.add_argument("--nE", type=int, help="evaluation slots per window (default: to run end)")
    sl.add_argument("--stride", type=int, default=1)
    sl.add_argument("--ratio", type=float, default=0.10, help="target malware ratio (C3)")
    sl.add_argument("--min-malware", type=int, default=50, help="size gate M")
    sl.add_argument("--seed", type=int, default=0)
    sl.add_argument("--memory-cap-gb", type=float, default=1.5)
    sl.add_argument("--out", type=Path, default=Path("results") / "slicing")
    return parser


def _run_data(args: argparse.Namespace) -> int:
    from driftwatch.data.cache import Layout

    layout = Layout(args.root)
    datasets = _datasets(args.dataset)
    if args.data_command == "download":
        from driftwatch.data import download

        for name in datasets:
            try:
                if name == "lamda":
                    download.download_lamda(layout, revision=args.revision)
                else:
                    download.download_bodmas(layout, manual=args.manual)
            except download.ManualDownloadRequired as exc:
                print(exc, file=sys.stderr)
                return 3
        return 0
    if args.data_command == "build":
        from driftwatch.data.build import build_dataset

        raw_layout = Layout(args.raw_root) if args.raw_root else layout
        for name in datasets:
            build_dataset(
                name,
                layout,
                raw_layout=raw_layout,
                memory_cap_bytes=int(args.memory_cap_gb * 1024**3),
                batch_size=args.batch_size,
            )
        return 0
    if args.data_command == "verify":
        from driftwatch.data.verify import verify

        problems = verify(layout, datasets)
        for problem in problems:
            print(f"FAIL {problem}", file=sys.stderr)
        print(f"data verify: {'FAILED' if problems else 'OK'} ({len(problems)} problems)")
        return 1 if problems else 0
    if args.data_command == "inventory":
        from driftwatch.data.inventory import write_inventory

        write_inventory(layout, datasets, args.out)
        return 0
    if args.data_command == "slice":
        from driftwatch.data.presets import cached_source
        from driftwatch.data.slice_run import run_slicing
        from driftwatch.data.slicer import WindowSpec

        spec = WindowSpec(
            nT=args.nT,
            nE=args.nE,
            stride=args.stride,
            target_ratio=args.ratio,
            min_malware=args.min_malware,
            seed=args.seed,
        )
        overrides = {"length": args.length} if args.length else {}
        for name in datasets:
            source = cached_source(name, args.root, **overrides)
            out_dir = args.out / f"{name}-{spec.digest()}"
            summary = run_slicing(
                source, spec, out_dir, memory_cap_bytes=int(args.memory_cap_gb * 1024**3)
            )
            peak_gb = summary["memory"]["peak_bytes"] / 1024**3
            print(
                f"{name}: {summary['windows']} windows, {summary['eval_slots']} evaluation "
                f"slots, {summary['wall_s']} s, peak {peak_gb:.2f} GB, "
                f"{summary['dense_matrices']} densified; manifest in {out_dir}"
            )
        return 0
    raise AssertionError(args.data_command)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "data":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        return _run_data(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
