"""Command-line entry point `driftwatch`.

Phase 2 adds `data download|build|verify|inventory`, Phase 3 `data slice` and Phase 4
`run <config.yaml>` (the E0 baseline). Later phases add `grid` (Phase 6) and
`reproduce table1` (Phase 7).
"""

import argparse
import json
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

    run = sub.add_parser("run", help="run YAML configs (baseline or simulation), store results")
    run.add_argument("config", type=Path, nargs="+", help="one or more configs/*.yaml files")
    run.add_argument("--root", type=Path, default=Path("data"), help="data root (default data)")
    run.add_argument("--out", type=Path, help="results root (default: the config's output)")
    run.add_argument("--memory-cap-gb", type=float, default=1.5)
    run.add_argument("--overwrite", action="store_true", help="replace a finished run")
    run.add_argument(
        "--require-clean", action="store_true", help="refuse a tree with uncommitted changes"
    )
    run.add_argument(
        "--resume",
        action="store_true",
        help="continue an interrupted run of the same config hash from its finished windows",
    )
    run.add_argument(
        "--workers",
        type=int,
        default=1,
        help="runs in parallel, one thread per run (mind LightGBM n_jobs x workers <= cores)",
    )

    rp = sub.add_parser("reproduce", help="rebuild a stored table from the data and compare")
    rp.add_argument("table", choices=("table1",), help="table1 = E0 baselines on BODMAS")
    rp.add_argument("--smoke", action="store_true", help="tiny run on the synthetic fixture")
    rp.add_argument("--data-root", type=Path, default=Path("data"), help="data root")
    rp.add_argument("--out", type=Path, default=Path("reports/reproduction"))
    rp.add_argument("--work-dir", type=Path, help="results and fixture caches go here")
    rp.add_argument("--tolerance", type=float, default=0.002, help="absolute, per numeric cell")
    rp.add_argument("--memory-cap-gb", type=float, default=1.5)
    rp.add_argument(
        "--allow-dirty", action="store_true", help="development only: run on a dirty tree"
    )
    rp.add_argument(
        "--write-reference", action="store_true", help="smoke only: (re)write the golden table"
    )

    gr = sub.add_parser("grid", help="run the pre-registered delay x budget grid (E2), by cell")
    gr.add_argument("spec", type=Path, help="a grid spec such as configs/e2_lamda.yaml")
    gr.add_argument("--chunk", help="i/n: run the i-th of n cost-balanced chunks of cells")
    gr.add_argument("--smoke", action="store_true", help="1 seed, 1 window; prints timing only")
    gr.add_argument("--status", action="store_true", help="planned against complete and failed")
    gr.add_argument("--root", type=Path, default=Path("data"), help="data root (default data)")
    gr.add_argument("--out", type=Path, help="results root (default: the spec's output)")
    gr.add_argument("--memory-cap-gb", type=float, default=1.5)
    gr.add_argument(
        "--allow-code-change", metavar="REASON", help="accept cells from another commit"
    )
    gr.add_argument(
        "--retry-failed", metavar="REASON", help="rerun failed cells; logged as a retry"
    )
    gr.add_argument("--target-chunk-hours", type=float, default=1.0, help="smoke: chunk size")
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


def _run_configs(args: argparse.Namespace) -> list:
    from driftwatch.data.presets import cached_source
    from driftwatch.sim.config import RunConfig
    from driftwatch.sim.runner import run_file, run_many

    if len(args.config) == 1 and args.workers == 1:
        return [
            run_file(
                args.config[0],
                data_root=args.root,
                out_root=args.out,
                memory_cap_gb=args.memory_cap_gb,
                overwrite=args.overwrite,
                require_clean=args.require_clean,
                resume=args.resume,
            )
        ]
    jobs = []
    out_roots = set()
    for path in args.config:
        cfg = RunConfig.from_file(path)
        jobs.append((cfg, cached_source(cfg.dataset, args.root)))
        out_roots.add(str(args.out if args.out is not None else cfg.output))
    if len(out_roots) != 1:
        raise FileExistsError(f"configs write to different roots {sorted(out_roots)}; use --out")
    return run_many(
        jobs,
        out_roots.pop(),
        repo_root=Path(__file__).resolve().parents[2],
        workers=args.workers,
        memory_cap_bytes=int(args.memory_cap_gb * 1024**3),
        overwrite=args.overwrite,
        require_clean=args.require_clean,
        resume=args.resume,
    )


def _run_reproduce(args: argparse.Namespace) -> int:
    """Exit codes: 0 match, 1 mismatch, 2 cannot run, 3 manual data download needed."""
    from driftwatch.data.download import ManualDownloadRequired
    from driftwatch.sim.reproduce import ReproductionError, reproduce_table1

    repo = Path(__file__).resolve().parents[2]
    try:
        report = reproduce_table1(
            repo_root=repo,
            data_root=args.data_root,
            out_dir=args.out,
            work_dir=args.work_dir,
            tolerance=args.tolerance,
            smoke=args.smoke,
            memory_cap_gb=args.memory_cap_gb,
            require_clean=not args.allow_dirty,
            write_reference=args.write_reference,
        )
    except ManualDownloadRequired as exc:
        print(exc, file=sys.stderr)
        return 3
    except (ReproductionError, RuntimeError, FileNotFoundError) as exc:
        print(f"driftwatch reproduce: {exc}", file=sys.stderr)
        return 2
    print(
        f"{report['verdict']}: {report['rows_compared']} rows, max |diff| "
        f"{report['max_abs_diff']:.6f} (tolerance {report['tolerance_abs']}), "
        f"{report['total_wall_s']:.0f} s total ({report['run_wall_s']:.0f} s run)"
    )
    for problem in report["problems"][:10]:
        print(f"  {problem}", file=sys.stderr)
    return 0 if report["verdict"] == "MATCH" else 1


def _run_grid(args: argparse.Namespace) -> int:
    from driftwatch.data.presets import cached_source
    from driftwatch.sim import grid

    spec = grid.GridSpec.from_file(args.spec)
    default_out = Path(spec.output) if not args.smoke else Path("results/e2_smoke") / spec.dataset
    out = args.out if args.out is not None else default_out
    if args.status:
        report = grid.status(spec, out)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    chunk = grid.parse_chunk(args.chunk) if args.chunk else None
    source = cached_source(spec.dataset, args.root)
    repo = Path(__file__).resolve().parents[2]
    results = grid.run_grid(
        spec,
        source,
        out,
        repo_root=repo,
        chunk=chunk,
        smoke=args.smoke,
        require_clean=not args.smoke,  # smoke measures time and is never evidence
        memory_cap_bytes=int(args.memory_cap_gb * 1024**3),
        allow_code_change=args.allow_code_change,
        retry_reason=args.retry_failed,
        on_cell=lambda r: print(
            f"{r.cell_id}: {r.status}" + (f" {r.wall_s:.0f} s" if r.wall_s else "")
        ),
    )
    failed = [r for r in results if r.status == "failed"]
    if args.smoke:
        _print_extrapolation(spec, source, results, args.target_chunk_hours)
    for r in failed:
        print(f"FAILED {r.cell_id}: {r.reason}", file=sys.stderr)
    return 1 if failed or any(r.stop for r in results) else 0


def _print_extrapolation(spec, source, results, target_hours: float) -> None:
    """Timing only: seconds per unit by cell shape, then the planned grid in hours and chunks."""
    import math

    from driftwatch.sim import grid

    cells, units, _ = grid.plan(spec, source)
    smoke_secs = {r.cell_id: r.wall_s for r in results if r.wall_s and r.units}
    smoke_units = {r.cell_id: r.units for r in results if r.wall_s and r.units}
    est = grid.extrapolate(spec, smoke_secs, units, smoke_units)
    print()
    print("smoke timing (seconds per window x seed x model unit)")
    for cid, s in sorted(smoke_secs.items()):
        print(f"  {cid:60s} {s / smoke_units[cid]:7.2f} s/unit  ({smoke_units[cid]} units)")
    print()
    print("extrapolation to the full grid")
    for cid, secs in sorted(est["per_cell_s"].items()):
        print(f"  {cid:60s} {units[cid]:5d} units  {secs / 3600:6.2f} h")
    total = est["total_s"]
    n_chunks = max(1, math.ceil(total / (target_hours * 3600)))
    parts = grid.assign_chunks(est["per_cell_s"], n_chunks)
    print()
    print(
        f"total {total / 3600:.2f} h over {len(cells)} cells; "
        f"{n_chunks} chunks of about {target_hours:g} h:"
    )
    for i, part in enumerate(parts, 1):
        hours = sum(est["per_cell_s"][c] for c in part) / 3600
        print(f"  --chunk {i}/{n_chunks}: {len(part)} cells, {hours:.2f} h")
    if est["unmeasured"]:
        print(f"unmeasured cells (no smoke cell of their shape): {est['unmeasured']}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "data":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        return _run_data(args)
    if args.command == "run":
        from driftwatch.sim.config import ConfigError

        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        try:
            summaries = _run_configs(args)
        except (ConfigError, FileExistsError) as exc:
            print(f"driftwatch run: {exc}", file=sys.stderr)
            return 2
        except RuntimeError as exc:
            if "dirty" not in str(exc):
                raise
            print(f"driftwatch run: {exc}", file=sys.stderr)
            return 2
        for summary in summaries:
            print(
                f"{summary.n_windows} window rows, {summary.n_slot_rows} slot rows, "
                f"{summary.n_prediction_rows} predictions, {summary.wall_s:.1f} s\n"
                f"config hash {summary.config_hash}\n"
                f"predictions sha256 {summary.predictions_sha256}\n"
                f"results in {summary.dir}"
            )
        return 0
    if args.command == "reproduce":
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        return _run_reproduce(args)
    if args.command == "grid":
        from driftwatch.sim.config import ConfigError
        from driftwatch.sim.grid import CodeVersionMismatch, GridError

        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        try:
            return _run_grid(args)
        except (ConfigError, GridError, CodeVersionMismatch, ValueError) as exc:
            print(f"driftwatch grid: {exc}", file=sys.stderr)
            return 2
        except RuntimeError as exc:
            if "dirty" not in str(exc):
                raise
            print(f"driftwatch grid: {exc}", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
