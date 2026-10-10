"""Regression tests for the Phase 2 leakage review (findings 1-8, 10-12).

Negative tests write a cache that is internally consistent (files re-hashed and manifest
re-saved), but wrong, and require `verify` to catch it. A hash check alone would not.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from conftest import FIXTURE_ROOT, build_fixture_caches

from driftwatch.data import build as build_module
from driftwatch.data.build import build_dataset
from driftwatch.data.cache import (
    Layout,
    file_record,
    load_manifest,
    save_dense,
    save_manifest,
    save_table,
    sha256_file,
)
from driftwatch.data.loaders import PUBLIC_COLUMNS, CachedDataset, PublicSlot
from driftwatch.data.slots import build_slots
from driftwatch.data.verify import verify

# --- helpers -----------------------------------------------------------------------------


def _copy(built: Path, tmp: Path) -> Path:
    root = tmp / "data"
    shutil.copytree(built, root)
    return root


def _rewrite(root: Path, dataset: str, unit: str, meta=None, X=None) -> None:
    """Rewrite one unit's files and record their new hashes, as a buggy builder would."""
    layout = Layout(root)
    unit_dir = layout.unit_dir(dataset, unit)
    if meta is not None:
        schema = pq.read_schema(unit_dir / "meta.parquet")
        table = pa.Table.from_pandas(meta[schema.names], schema=schema, preserve_index=False)
        save_table(unit_dir / "meta.parquet", table)
    if X is not None:
        save_dense(unit_dir / "X.npy", X)
    manifest = load_manifest(layout.manifest)
    entry = manifest["datasets"][dataset]["cache"]["units"][unit]
    entry["files"] = {rel: file_record(root / rel) for rel in entry["files"]}
    save_manifest(layout.manifest, manifest)


def _bodmas_units(root: Path) -> tuple[CachedDataset, list[str]]:
    data = CachedDataset("bodmas", root)
    return data, [u for u in data.units if data.load_unit(u)[1].shape[0] >= 3]


# --- finding 4: verify proves its invariants ----------------------------------------------


def test_verify_catches_row_outside_its_unit(tmp_path, built_data):
    root = _copy(built_data, tmp_path)
    data, units = _bodmas_units(root)
    _, meta = data.load_unit(units[0])
    meta.loc[0, "ts"] = pd.Timestamp("2001-01-01", tz="UTC")
    _rewrite(root, "bodmas", units[0], meta=meta)
    problems = verify(Layout(root), ["bodmas"])
    assert any("outside" in p for p in problems)


def test_verify_catches_unsorted_timestamps(tmp_path, built_data):
    root = _copy(built_data, tmp_path)
    data, units = _bodmas_units(root)
    x, meta = data.load_unit(units[0])
    order = np.arange(len(meta))[::-1]
    _rewrite(root, "bodmas", units[0], meta=meta.iloc[order].reset_index(drop=True), X=x[order])
    assert any("not sorted" in p for p in verify(Layout(root), ["bodmas"]))


def test_verify_catches_row_in_two_units(tmp_path, built_data):
    root = _copy(built_data, tmp_path)
    data, units = _bodmas_units(root)
    first = data.load_unit(units[0])[1]
    _, meta = data.load_unit(units[1])
    meta.loc[0, "row_id"] = first["row_id"].iloc[0]
    _rewrite(root, "bodmas", units[1], meta=meta)
    assert any("row_id appears more than once" in p for p in verify(Layout(root), ["bodmas"]))


def test_verify_catches_x_meta_misalignment(tmp_path, built_data):
    root = _copy(built_data, tmp_path)
    data, units = _bodmas_units(root)
    x, _ = data.load_unit(units[0])
    swapped = np.array(x)
    swapped[[0, 1]] = swapped[[1, 0]]
    _rewrite(root, "bodmas", units[0], X=swapped)
    assert any("misaligned" in p for p in verify(Layout(root), ["bodmas"]))


def test_verify_catches_lamda_month_routing(tmp_path, built_data):
    root = _copy(built_data, tmp_path)
    data = CachedDataset("lamda", root)
    _, meta = data.load_unit("2013-01")
    meta.loc[0, "year_month"] = "2013-02"
    _rewrite(root, "lamda", "2013-01", meta=meta)
    assert any("year_month differs" in p for p in verify(Layout(root), ["lamda"]))


def test_verify_catches_unit_file_outside_cache_dir(tmp_path, built_data):
    root = _copy(built_data, tmp_path)
    layout = Layout(root)
    manifest = load_manifest(layout.manifest)
    unit = next(iter(manifest["datasets"]["bodmas"]["cache"]["units"].values()))
    old_rel = next(iter(unit["files"]))
    stray = root / "cache" / "bodmas" / "v0" / "stray.npy"
    stray.parent.mkdir(parents=True)
    shutil.copy(root / old_rel, stray)
    unit["files"][layout.rel(stray)] = unit["files"].pop(old_rel)
    save_manifest(layout.manifest, manifest)
    assert any("is outside" in p for p in verify(layout, ["bodmas"]))


# --- finding 3: resume never mixes builds ---------------------------------------------------


def test_changed_builder_rebuilds_every_unit(tmp_path, monkeypatch):
    root = build_fixture_caches(tmp_path / "data")
    files = [p for p in (root / "cache" / "bodmas").rglob("*") if p.is_file()]
    before = {p: p.stat().st_mtime_ns for p in files}
    monkeypatch.setattr(build_module, "builder_fingerprint", lambda dataset: "changed-logic")
    build_dataset("bodmas", Layout(root), raw_layout=Layout(FIXTURE_ROOT), batch_size=16)
    assert all(p.stat().st_mtime_ns != t for p, t in before.items())
    units = load_manifest(Layout(root).manifest)["datasets"]["bodmas"]["cache"]["units"]
    assert {u["builder"] for u in units.values()} == {"changed-logic"}


def test_old_cache_version_is_archived_not_mixed(tmp_path):
    root = build_fixture_caches(tmp_path / "data")
    layout = Layout(root)
    manifest = load_manifest(layout.manifest)
    manifest["datasets"]["bodmas"]["cache"]["version"] = "v0"
    save_manifest(layout.manifest, manifest)
    build_dataset("bodmas", layout, raw_layout=Layout(FIXTURE_ROOT), batch_size=16)
    entry = load_manifest(layout.manifest)["datasets"]["bodmas"]
    assert [c["version"] for c in entry["previous_caches"]] == ["v0"]
    assert verify(layout, ["bodmas"]) == []


# --- finding 12: hashes and caches do not depend on the batch size --------------------------


def test_cache_is_independent_of_batch_size(tmp_path):
    roots = []
    for size in (16, 4096):
        root = tmp_path / f"b{size}"
        build_dataset("lamda", Layout(root), raw_layout=Layout(FIXTURE_ROOT), batch_size=size)
        roots.append(root)
    a, b = (
        {p.relative_to(r).as_posix(): sha256_file(p) for p in (r / "cache").rglob("*.*")}
        for r in roots
    )
    assert a == b


# --- findings 2, 5, 8, 10: timestamps ------------------------------------------------------


def test_iso_year_boundary_weeks(built_data):
    data = CachedDataset("bodmas", built_data)
    w01 = pd.to_datetime(data.load_unit("2020-W01")[1]["ts"], utc=True)
    assert {d.isoformat() for d in w01.dt.date} >= {"2019-12-30", "2019-12-31"}
    w53 = pd.to_datetime(data.load_unit("2020-W53")[1]["ts"], utc=True)
    assert [d.isoformat() for d in w53.dt.date] == ["2020-12-31"]


def test_bodmas_rows_carry_timestamp_flags(built_data):
    data = CachedDataset("bodmas", built_data)
    meta = pd.concat([data.load_unit(u)[1] for u in data.units], ignore_index=True)
    assert int(meta["ts_naive"].sum()) == 1
    tie = meta[meta["ts"] == pd.Timestamp("2019-09-09", tz="UTC")]
    assert len(tie) == 3 and tie["ts_date_only"].all() and (tie["ts_tie_count"] == 3).all()


def test_lamda_ts_source_marks_fallback_rows(built_data):
    data = CachedDataset("lamda", built_data)
    meta = pd.concat([data.load_unit(u)[1] for u in data.units], ignore_index=True)
    # planted: one `added` outside its month and two rows missing from metadata.csv
    assert (meta["ts_source"] == "month_start").sum() == 3


def test_missing_lamda_metadata_is_an_error(tmp_path):
    raw = tmp_path / "raw_root"
    shutil.copytree(FIXTURE_ROOT, raw)
    next((raw / "raw" / "lamda").glob("*/metadata.csv")).unlink()
    with pytest.raises(FileNotFoundError, match="added"):
        build_dataset("lamda", Layout(tmp_path / "data"), raw_layout=Layout(raw), batch_size=16)


# --- finding 1: the public view carries no label information -------------------------------


def test_public_view_holds_features_and_row_ids_only(built_data):
    s = CachedDataset("bodmas", built_data).load_slot("2w:2019-08-26")
    public = s.public()
    assert isinstance(public, PublicSlot) and PUBLIC_COLUMNS == ("row_id",)
    assert set(vars(public)) == {"dataset", "slot_id", "X", "row_id"}
    np.testing.assert_array_equal(public.row_id, s.meta["row_id"].to_numpy())
    public.row_id[0] = -1  # a copy: a consumer cannot write back into the slot
    assert s.meta["row_id"].iloc[0] != -1


# --- findings 6, 7: partial slots and the explicit anchor -----------------------------------


def test_partial_quarter_is_flagged(built_data):
    quarters = {s.slot_id: s for s in CachedDataset("lamda", built_data).slots("quarter")}
    q1 = quarters["quarter:2013Q1"]
    assert q1.is_partial and q1.missing_units == ("2013-03",)
    assert not quarters["quarter:2015Q1"].is_partial  # fully empty is a gap, not partial


def test_week_anchor_fixes_slot_ids():
    anchor = datetime(2019, 8, 26, tzinfo=UTC)
    units = ["2019-W36", "2019-W38"]
    assert [s.slot_id for s in build_slots("bodmas", "2w", units)][0] == "2w:2019-09-02"
    anchored = build_slots("bodmas", "2w", units, anchor=anchor)
    assert [s.slot_id for s in anchored] == ["2w:2019-08-26", "2w:2019-09-09"]
    assert anchored[0].missing_units == ("2019-W35",)
    with pytest.raises(ValueError, match="Monday"):
        build_slots("bodmas", "2w", units, anchor=datetime(2019, 8, 27, tzinfo=UTC))
