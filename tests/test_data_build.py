"""Phase 2 builders, manifest, verify and memory watchdog, on the synthetic fixture."""

from __future__ import annotations

import json
import shutil
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
from conftest import FIXTURE_ROOT, build_fixture_caches

from driftwatch.cli import main
from driftwatch.data.build import SourceChanged, build_dataset
from driftwatch.data.cache import Layout, load_manifest, sha256_file
from driftwatch.data.loaders import CachedDataset
from driftwatch.data.memory import MemoryCapExceeded, MemoryWatchdog
from driftwatch.data.verify import verify

FIXTURE_LIMIT = 1024 * 1024


def _unit_files(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): sha256_file(p)
        for p in sorted((root / "cache").rglob("*"))
        if p.is_file()
    }


def test_fixture_is_under_one_megabyte():
    size = sum(p.stat().st_size for p in FIXTURE_ROOT.rglob("*") if p.is_file())
    assert 0 < size < FIXTURE_LIMIT


def test_verify_passes_on_fresh_build(built_data):
    assert verify(Layout(built_data), ["lamda", "bodmas"]) == []
    assert main(["data", "verify", "--root", str(built_data)]) == 0


def test_lamda_round_trip(built_data):
    """Every raw parquet row is in the cache once, with identical features and labels."""
    snap = next((FIXTURE_ROOT / "raw" / "lamda").iterdir())
    raw = pd.concat(
        [
            pq.read_table(p).to_pandas().assign(src_file=p.relative_to(snap).as_posix())
            for p in sorted(snap.glob("Baseline/*/*.parquet"))
        ],
        ignore_index=True,
    )
    data = CachedDataset("lamda", built_data)
    xs, metas = zip(*(data.load_unit(u) for u in data.units), strict=True)
    meta = pd.concat(metas, ignore_index=True)
    dense = np.vstack([x.toarray() for x in xs])
    assert len(meta) == len(raw) and meta["row_id"].is_unique
    key = ["sha256", "src_file"]
    raw = raw.rename(columns={"hash": "sha256"})
    raw["_raw"] = np.arange(len(raw))
    meta["_cache"] = np.arange(len(meta))
    joined = meta.merge(raw, on=key, suffixes=("", "_raw"))
    assert len(joined) == len(raw)
    feats = [c for c in raw.columns if c.startswith("feat_")]
    for _, row in joined.iterrows():
        np.testing.assert_array_equal(dense[row["_cache"]], row[feats].to_numpy(np.int8))
    assert (joined["label"] == joined["label_raw"]).all()
    assert (joined["family"] == joined["family_raw"]).all()
    assert (joined["vt_count"].astype(float) == joined["vt_count_raw"]).all()
    assert set(meta["src_split"]) == {"train", "test"}  # the 80/20 split is pooled


def test_bodmas_round_trip(built_data):
    with zipfile.ZipFile(FIXTURE_ROOT / "raw" / "bodmas" / "bodmas.npz") as zf:
        X = np.load(zf.open("X.npy"))
        y = np.load(zf.open("y.npy"))
    data = CachedDataset("bodmas", built_data)
    xs, metas = zip(*(data.load_unit(u) for u in data.units), strict=True)
    meta = pd.concat(metas, ignore_index=True)
    cached = np.vstack(xs)
    order = np.argsort(meta["row_id"].to_numpy())
    np.testing.assert_array_equal(cached[order], X)
    np.testing.assert_array_equal(meta["label"].to_numpy()[order], y)
    assert cached.dtype == np.float32


def test_lamda_timestamps_come_from_added(built_data):
    manifest = load_manifest(Layout(built_data).manifest)
    chunks = manifest["datasets"]["lamda"]["cache"]["chunks"]
    totals = pd.DataFrame([c["stats"] for c in chunks.values()]).sum(numeric_only=True)
    assert totals["added_month_mismatch"] == 1  # planted: added in June, year_month July
    assert totals["meta_missing"] == 2  # planted: one app (two rows) not in metadata.csv
    assert totals["folder_year_mismatch"] == 0
    assert totals["meta_label_conflicts"] == 0
    meta = CachedDataset("lamda", built_data).load_slot("month:2013-06").meta
    assert meta["added"].notna().all() and (meta["ts"] == meta["added"]).all()


def test_bodmas_timestamps_without_offset_are_counted(built_data):
    stats = load_manifest(Layout(built_data).manifest)["datasets"]["bodmas"]["cache"]["stats"]
    assert stats["ts_without_offset"] == 1  # planted; read as UTC
    meta = CachedDataset("bodmas", built_data).load_slot("1w:2018-04-30").meta
    assert str(meta["ts"].iloc[0]) == "2018-05-03 12:00:00+00:00"


def test_rebuild_is_deterministic(tmp_path, built_data):
    other = build_fixture_caches(tmp_path / "data")
    assert _unit_files(other) == _unit_files(built_data)


def test_rebuild_skips_and_resumes(tmp_path):
    root = build_fixture_caches(tmp_path / "data")
    before = {p: p.stat().st_mtime_ns for p in (root / "cache").rglob("*") if p.is_file()}
    victim = next((root / "cache" / "bodmas").rglob("X.npy"))
    victim_hash = sha256_file(victim)
    victim.unlink()
    build_fixture_caches(root)
    assert sha256_file(victim) == victim_hash
    touched = [p for p, t in before.items() if p.exists() and p.stat().st_mtime_ns != t]
    assert set(touched) <= {victim, victim.with_name("meta.parquet")}
    assert verify(Layout(root), ["lamda", "bodmas"]) == []
    builds = load_manifest(Layout(root).manifest)["datasets"]["bodmas"]["builds"]
    assert len(builds) == 2  # every build is recorded, none overwritten


def test_changed_source_is_refused(tmp_path):
    raw = tmp_path / "rawroot"
    shutil.copytree(FIXTURE_ROOT, raw)
    root = tmp_path / "data"
    build_dataset("bodmas", Layout(root), raw_layout=Layout(raw), batch_size=16)
    with (raw / "raw" / "bodmas" / "bodmas_metadata.csv").open("a") as fh:
        fh.write("\n")
    with pytest.raises(SourceChanged):
        build_dataset("bodmas", Layout(root), raw_layout=Layout(raw), batch_size=16)


def test_verify_detects_tampered_cache_byte(tmp_path, built_data):
    root = tmp_path / "data"
    shutil.copytree(built_data, root)
    target = next((root / "cache" / "lamda").rglob("X.npz"))
    data = bytearray(target.read_bytes())
    data[-1] ^= 0xFF
    target.write_bytes(bytes(data))
    problems = verify(Layout(root), ["lamda", "bodmas"])
    assert any("hash mismatch" in p for p in problems)
    assert main(["data", "verify", "--root", str(root)]) == 1


def test_verify_detects_hand_edited_manifest(tmp_path, built_data):
    root = tmp_path / "data"
    shutil.copytree(built_data, root)
    manifest = json.loads((root / "manifest.json").read_text())
    unit = next(iter(manifest["datasets"]["bodmas"]["cache"]["units"].values()))
    unit["n_rows"] += 1
    (root / "manifest.json").write_text(json.dumps(manifest))
    assert verify(Layout(root), ["bodmas"]) == [
        "manifest content_hash does not match its contents (edited by hand?)"
    ]


def test_build_records_memory_and_time(built_data):
    build = load_manifest(Layout(built_data).manifest)["datasets"]["lamda"]["builds"][-1]
    assert build["memory"]["peak_bytes"] > 0
    assert build["memory"]["cap_bytes"] == int(1.5 * 1024**3)
    assert build["cache_bytes"] > 0 and build["memory"]["wall_s"] >= 0


def test_watchdog_aborts_above_the_cap():
    with pytest.raises(MemoryCapExceeded), MemoryWatchdog(cap_bytes=1, interval_s=0.01):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            time.sleep(0.005)
        pytest.fail("watchdog did not interrupt")


def test_watchdog_records_peak_under_the_cap():
    with MemoryWatchdog(cap_bytes=1 << 40) as wd:
        np.ones(1 << 20)
    assert wd.peak_bytes > 0 and wd.exceeded_at is None


def test_inventory_writes_report_tables_and_figures(tmp_path, built_data):
    from driftwatch.data.inventory import write_inventory

    report = write_inventory(Layout(built_data), ["lamda", "bodmas"], tmp_path)
    text = report.read_text(encoding="utf-8")
    assert "## LAMDA" in text and "## BODMAS" in text and "longest_passing_run" in text
    for name in ("lamda_slots_month", "lamda_slots_quarter", "bodmas_slots_4w", "lamda_years"):
        assert (tmp_path / "tables" / f"data_{name}.csv").exists()
    assert (tmp_path / "figures" / "data_lamda_counts.png").exists()
    gates = pd.read_csv(tmp_path / "tables" / "data_lamda_slots_month.csv")
    assert gates.loc[gates["slot"] == "month:2013-02", "pass_M30"].item() == False  # noqa: E712
