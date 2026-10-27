"""The result store's unit checkpoints: resumable without duplicate rows (sim.md rule)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from driftwatch.sim.results import PredictionHasher, ResultStore, iter_blocks

H = "d" * 64


def key(window: str, slot: str, **extra):
    return {
        "variant": "rolling",
        "model": "lr",
        "ratio": 0.1,
        "seed": 0,
        "window_id": window,
        "slot_id": slot,
        **extra,
    }


def fill_unit(store: ResultStore, unit: str, n_slots: int = 2) -> None:
    """One unit = one window: n_slots prediction blocks, slot rows and a window row."""
    assert store.begin_unit(unit) is False
    with store.predictions() as write:
        for s in range(n_slots):
            rows = np.arange(3, dtype=np.int64) + 10 * s
            write(
                key(unit, f"s{s}"),
                row_id=rows,
                y_true=np.array([0, 1, 0], dtype=np.int8),
                proba=np.array([0.1, 0.9, 0.4], dtype=np.float32) + 0.01 * s,
                pred=np.array([0, 1, 0], dtype=np.int8),
            )
            store.add_slot({"variant": "rolling", "window_id": unit, "slot_id": f"s{s}", "f1": 0.5})
    store.add_window({"variant": "rolling", "window_id": unit, "aut": 0.75})
    store.end_unit()


def read(d: Path):
    return (
        pd.read_parquet(d / "predictions.parquet"),
        pd.read_parquet(d / "slots.parquet"),
        pd.read_parquet(d / "windows.parquet"),
    )


def test_units_merge_in_visit_order_and_leave_the_final_layout(tmp_path: Path) -> None:
    store = ResultStore(tmp_path, H)
    for u in ("w0", "w1", "w2"):
        fill_unit(store, u)
    d = store.finalize({"config_hash": H})
    preds, slots, windows = read(d)
    assert list(preds["window_id"].unique()) == ["w0", "w1", "w2"]
    assert len(preds) == 3 * 2 * 3 and len(slots) == 6 and len(windows) == 3
    assert not (d / "units").exists()  # checkpoints are removed once merged


def test_new_key_columns_default_for_baseline_rows(tmp_path: Path) -> None:
    store = ResultStore(tmp_path, H)
    fill_unit(store, "w0")
    preds, *_ = read(store.finalize({"config_hash": H}))
    assert set(preds["series"]) == {"time_aware"} and set(preds["policy"]) == {"never"}
    assert preds["selector"].isna().all() and preds["delay"].isna().all()


def test_a_resumed_run_equals_an_uninterrupted_one_and_has_no_duplicates(tmp_path: Path) -> None:
    full = ResultStore(tmp_path / "full", H)
    for u in ("w0", "w1", "w2", "w3"):
        fill_unit(full, u)
    want = read(full.finalize({"config_hash": H}))

    root = tmp_path / "resumed"
    crashed = ResultStore(root, H)
    fill_unit(crashed, "w0")
    fill_unit(crashed, "w1")
    assert crashed.begin_unit("w2") is False  # w2 starts, then the process dies
    with crashed.predictions() as write:
        write(
            key("w2", "s0"),
            row_id=np.arange(3, dtype=np.int64),
            y_true=np.zeros(3, dtype=np.int8),
            proba=np.zeros(3, dtype=np.float32),
            pred=np.zeros(3, dtype=np.int8),
        )
    del crashed  # never committed

    resumed = ResultStore(root, H, resume=True)
    assert resumed.begin_unit("w0") is True and resumed.unit_n_slots == 2
    assert resumed.unit_n_windows == 1
    resumed.end_unit()
    assert resumed.begin_unit("w1") is True
    resumed.end_unit()
    fill_unit(resumed, "w2")
    fill_unit(resumed, "w3")
    got = read(resumed.finalize({"config_hash": H}))

    for g, w in zip(got, want, strict=True):
        pd.testing.assert_frame_equal(g.reset_index(drop=True), w.reset_index(drop=True))
    keys = ["window_id", "slot_id", "row_id"]
    assert not got[0].duplicated(keys).any()


def test_replayed_blocks_rebuild_the_same_prediction_hash(tmp_path: Path) -> None:
    store = ResultStore(tmp_path, H)
    original = PredictionHasher()
    assert store.begin_unit("w0") is False
    with store.predictions() as write:
        for s in range(3):
            row = np.arange(4, dtype=np.int64) * (s + 1)
            proba = np.linspace(0.1, 0.9, 4, dtype=np.float32) * (s + 1) / 3
            pred = (proba > 0.5).astype(np.int8)
            write(key("w0", f"s{s}"), row_id=row, y_true=pred, proba=proba, pred=pred)
            original.update("cell", "w0", f"s{s}", row, pred, proba)
    store.end_unit()

    again = ResultStore(tmp_path, H, resume=True)
    assert again.begin_unit("w0") is True
    replay = PredictionHasher()
    for block in again.unit_blocks():
        replay.update(
            "cell",
            block.key["window_id"],
            block.key["slot_id"],
            block.row_id,
            block.pred,
            block.proba,
        )
    assert replay.hexdigest() == original.hexdigest()


def test_iter_blocks_splits_contiguous_runs_only() -> None:
    import pyarrow as pa

    table = pa.table(
        {
            "window_id": ["w", "w", "w", "w"],
            "slot_id": ["a", "a", "b", "a"],
            "row_id": pa.array([1, 2, 3, 4], pa.int64()),
            "pred": pa.array([0, 1, 0, 1], pa.int8()),
            "proba": pa.array([0.1, 0.9, 0.2, 0.8], pa.float32()),
        }
    )
    sizes = [len(b.row_id) for b in iter_blocks(table, ("window_id", "slot_id"))]
    assert sizes == [2, 1, 1]


def test_resume_refuses_a_finished_run_and_a_fresh_store_wipes_checkpoints(tmp_path: Path) -> None:
    done = ResultStore(tmp_path, H)
    fill_unit(done, "w0")
    done.finalize({"config_hash": H})
    with pytest.raises(FileExistsError):
        ResultStore(tmp_path, H, resume=True)

    other = ResultStore(tmp_path / "b", H)
    fill_unit(other, "w0")
    fresh = ResultStore(tmp_path / "b", H)  # not a resume: leftovers are replaced
    assert fresh.begin_unit("w0") is False


def test_a_failure_record_is_kept_when_a_run_is_resumed(tmp_path: Path) -> None:
    s = ResultStore(tmp_path, H)
    fill_unit(s, "w0")
    s.fail({"error": "boom"})
    r = ResultStore(tmp_path, H, resume=True)
    assert not (r.dir / "run_failed.json").exists()
    kept = sorted(p.name for p in r.dir.glob("run_failed*.json"))
    assert kept == ["run_failed.1.json"]


def test_a_unit_cannot_be_started_twice_in_one_session(tmp_path: Path) -> None:
    s = ResultStore(tmp_path, H)
    fill_unit(s, "w0")
    with pytest.raises(ValueError, match="already"):
        s.begin_unit("w0")


def test_begin_without_end_is_refused(tmp_path: Path) -> None:
    s = ResultStore(tmp_path, H)
    s.begin_unit("w0")
    with pytest.raises(ValueError, match="open"):
        s.begin_unit("w1")
