"""`driftwatch data slice`: a whole-dataset slicing pass with its manifest and run metrics."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from driftwatch.cli import main
from driftwatch.data.presets import cached_source
from driftwatch.data.slice_run import run_slicing
from driftwatch.data.slicer import WindowSpec

SPEC = WindowSpec(nT=1, nE=None, stride=1, target_ratio=0.40, min_malware=2, seed=0)


def test_run_slicing_touches_every_usable_slot_and_writes_the_manifest(built_data, tmp_path):
    source = cached_source("bodmas", built_data, length="1w")
    summary = run_slicing(source, SPEC, tmp_path / "out", memory_cap_bytes=1 << 30)
    slots = pd.read_csv(tmp_path / "out" / "slot_manifest.csv")
    windows = pd.read_csv(tmp_path / "out" / "window_manifest.csv")
    run = json.loads((tmp_path / "out" / "slicing_run.json").read_text(encoding="utf-8"))

    usable = slots[slots["usable"]]
    assert summary["windows"] >= 1
    assert summary["eval_slots"] == int((windows["role"] == "eval").sum())
    # nE=None: every usable slot is trained on or evaluated exactly once per run, so each
    # usable slot of a run longer than nT shows up in the window manifest.
    assert set(windows["slot_id"]) <= set(usable["slot_id"])
    assert (windows[windows["role"] == "eval"]["achieved_ratio"] <= 0.40 + 1e-9).all()
    assert run["run"]["eval_rows"] == summary["eval_rows"] > 0
    assert run["run"]["memory"]["peak_bytes"] > 0 and run["run"]["wall_s"] >= 0
    assert run["source"]["name"] == "bodmas" and run["spec_digest"] == SPEC.digest()


def test_run_slicing_keeps_sparse_sources_sparse(built_data, tmp_path):
    source = cached_source("lamda", built_data)
    spec = WindowSpec(nT=1, nE=None, stride=1, target_ratio=0.40, min_malware=1, seed=0)
    summary = run_slicing(source, spec, tmp_path / "out", memory_cap_bytes=1 << 30)
    assert source.sparse and summary["dense_matrices"] == 0


def test_run_slicing_enforces_the_memory_cap(built_data, tmp_path):
    from driftwatch.data.memory import MemoryCapExceeded

    source = cached_source("bodmas", built_data, length="1w")
    with pytest.raises(MemoryCapExceeded):
        run_slicing(source, SPEC, tmp_path / "out", memory_cap_bytes=1)


def test_cli_slice_command_writes_a_manifest_per_dataset(built_data, tmp_path):
    code = main(
        [
            "data",
            "slice",
            "bodmas",
            "--root",
            str(built_data),
            "--length",
            "1w",
            "--nT",
            "1",
            "--ratio",
            "0.4",
            "--min-malware",
            "2",
            "--out",
            str(tmp_path / "slicing"),
        ]
    )
    assert code == 0
    runs = list((tmp_path / "slicing").glob("bodmas-*/slicing_run.json"))
    assert len(runs) == 1
