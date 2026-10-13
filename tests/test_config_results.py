"""Run configs (strict YAML schema, config hash) and the result store."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml

from driftwatch.sim.config import (
    ConfigError,
    RunConfig,
    config_hash,
    lock_sha256,
    package_versions,
)
from driftwatch.sim.results import PredictionHasher, ResultStore

BASE = {
    "name": "t",
    "dataset": "bodmas",
    "slots": {"preset": "adr-0004", "min_malware": 50},
    "window": {"nT": 3, "nE": 6, "stride": 2},
    "ratio": {"target": 0.10, "sensitivity": 0.05},
    "seeds": [0, 1],
    "model": [{"name": "lr"}, {"name": "lgbm", "profile": "fast", "n_jobs": 2}],
    "policy": "never",
    "e0": {"variants": ["rolling", "single_run"], "random_split": True},
    "output": "results/e0",
}


def cfg(**changes) -> dict:
    d = json.loads(json.dumps(BASE))
    d.update(changes)
    return d


# --- schema ----------------------------------------------------------------------------------


def test_valid_config_round_trips() -> None:
    c = RunConfig.from_dict(cfg())
    assert (c.nT, c.nE, c.stride) == (3, 6, 2)
    assert c.seeds == (0, 1) and c.target_ratio == 0.10 and c.sensitivity_ratio == 0.05
    assert RunConfig.from_dict(c.to_dict()).to_dict() == c.to_dict()


def test_yaml_file_loads(tmp_path: Path) -> None:
    path = tmp_path / "c.yaml"
    path.write_text(yaml.safe_dump(cfg()), encoding="utf-8")
    assert RunConfig.from_file(path).name == "t"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"surprise": 1}, "unknown"),
        ({"policy": "periodic"}, "policy"),
        ({"delay": 2}, "selector"),
        ({"budget_pct": 1.0}, "selector"),
        ({"selector": "random"}, "delay"),
        ({"nonconf": "logit"}, "later phase"),
        ({"seeds": []}, "seeds"),
        ({"seeds": [0, 0]}, "seeds"),
        ({"seeds": 5}, "seeds"),
        ({"seeds": [0, "a"]}, "seeds"),
        ({"dataset": "ember"}, "dataset"),
        ({"model": []}, "model"),
        ({"model": [{"name": "mlp"}]}, "unknown model"),
        ({"model": [{"name": "lr", "bogus": 1}]}, "unknown hyperparameter"),
        ({"ratio": {"target": 1.5}}, "ratio"),
        ({"ratio": {"target": 0.1, "sensitivity": 0.1}}, "sensitivity"),
        ({"window": {"nT": 0, "nE": 6, "stride": 2}}, "window"),
        ({"window": {"nT": 3, "nE": 1, "stride": 1}}, "window"),  # AUT needs two slots
        ({"model": [{"name": "lr"}, {"name": "lr", "C": 2.0}]}, "distinct"),
        ({"window": {"nT": 3, "nE": 6}}, "window"),
        ({"slots": {"preset": "week", "min_malware": 50}}, "preset"),
        ({"e0": {"variants": ["rolling", "magic"]}}, "variant"),
    ],
)
def test_invalid_configs_raise(changes: dict, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        RunConfig.from_dict(cfg(**changes))


def test_sensitivity_variant_needs_a_sensitivity_ratio() -> None:
    d = cfg(ratio={"target": 0.1}, e0={"variants": ["sensitivity"], "random_split": False})
    with pytest.raises(ConfigError, match="sensitivity"):
        RunConfig.from_dict(d)


def test_explicit_null_for_later_phase_keys_is_accepted() -> None:
    d = cfg(delay=None, budget_pct=None, selector=None, nonconf=None, pool=None, monitors=None)
    RunConfig.from_dict(d)


# --- hash ------------------------------------------------------------------------------------


def test_config_hash_ignores_key_order_and_covers_code_lock_and_every_value() -> None:
    a = RunConfig.from_dict(cfg())
    reordered = dict(reversed(list(cfg().items())))
    b = RunConfig.from_dict(reordered)
    h = config_hash(a.to_dict(), "abc1234", "lock1")
    assert h == config_hash(b.to_dict(), "abc1234", "lock1")
    assert len(h) == 64
    assert h != config_hash(a.to_dict(), "abc1234-dirty", "lock1")  # code version
    assert h != config_hash(a.to_dict(), "abc1234", "lock2")  # lock file
    other = RunConfig.from_dict(cfg(seeds=[0, 2]))
    assert h != config_hash(other.to_dict(), "abc1234", "lock1")  # a config value
    tuned = cfg(model=[{"name": "lr", "C": 2.0}, {"name": "lgbm", "profile": "fast", "n_jobs": 2}])
    assert h != config_hash(RunConfig.from_dict(tuned).to_dict(), "abc1234", "lock1")


def test_lock_hash_is_line_ending_independent(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_bytes(b"a\r\nb\r\n")
    h_crlf = lock_sha256(tmp_path)
    (tmp_path / "uv.lock").write_bytes(b"a\nb\n")
    assert lock_sha256(tmp_path) == h_crlf


def test_package_versions_lists_the_libraries_that_decide_numbers() -> None:
    v = package_versions()
    for name in ("python", "numpy", "scipy", "scikit-learn", "lightgbm", "pyarrow", "pyyaml"):
        assert v[name] not in ("", "unknown"), name


# --- store -----------------------------------------------------------------------------------


def test_prediction_hasher_is_order_and_content_sensitive() -> None:
    def digest(rows: int, pred_flip: bool = False, swap: bool = False) -> str:
        h = PredictionHasher()
        keys = [("c1", "w0", "s0"), ("c1", "w0", "s1")]
        for key in reversed(keys) if swap else keys:
            row_id = np.arange(rows, dtype=np.int64)
            pred = np.zeros(rows, dtype=np.int8)
            if pred_flip:
                pred[0] = 1
            h.update(*key, row_id, pred, np.full(rows, 0.25, dtype=np.float32))
        return h.hexdigest()

    base = digest(5)
    assert base == digest(5)
    assert base != digest(5, pred_flip=True)
    assert base != digest(6)
    assert base != digest(5, swap=True)


def test_store_writes_tables_and_run_record(tmp_path: Path) -> None:
    store = ResultStore(tmp_path, "a" * 64)
    assert store.dir.name == "a" * 16
    with store.predictions() as write:
        write(
            {
                "variant": "rolling",
                "model": "lr",
                "ratio": 0.1,
                "seed": 0,
                "window_id": "w",
                "slot_id": "s",
            },
            row_id=np.array([3, 1], dtype=np.int64),
            y_true=np.array([1, 0], dtype=np.int8),
            proba=np.array([0.9, 0.2], dtype=np.float32),
            pred=np.array([1, 0], dtype=np.int8),
        )
    store.add_slot({"variant": "rolling", "slot_id": "s", "f1": 0.5})
    store.add_window({"variant": "rolling", "window_id": "w", "aut": 0.5})
    store.finalize({"config_hash": "a" * 64, "note": "x"})

    preds = pq.read_table(store.dir / "predictions.parquet").to_pandas()
    assert list(preds["row_id"]) == [3, 1] and list(preds["pred"]) == [1, 0]
    assert (preds["config_hash"] == "a" * 64).all()
    assert preds["proba"].dtype == np.float32
    slots = pd.read_parquet(store.dir / "slots.parquet")
    assert slots.loc[0, "config_hash"] == "a" * 64 and slots.loc[0, "f1"] == 0.5
    windows = pd.read_parquet(store.dir / "windows.parquet")
    assert windows.loc[0, "window_id"] == "w"
    record = json.loads((store.dir / "run.json").read_text(encoding="utf-8"))
    assert record["config_hash"] == "a" * 64 and record["status"] == "complete"


def test_overwrite_clears_an_earlier_failure_record(tmp_path: Path) -> None:
    failed = ResultStore(tmp_path, "c" * 64)
    failed.fail({"error": "boom"})
    assert (failed.dir / "run_failed.json").exists()
    again = ResultStore(tmp_path, "c" * 64, overwrite=True)
    assert not (again.dir / "run_failed.json").exists()
    again.finalize({"config_hash": "c" * 64})
    assert (again.dir / "run.json").exists() and not (again.dir / "run_failed.json").exists()


def test_store_refuses_to_overwrite_a_finished_run(tmp_path: Path) -> None:
    first = ResultStore(tmp_path, "b" * 64)
    first.finalize({"config_hash": "b" * 64})
    with pytest.raises(FileExistsError):
        ResultStore(tmp_path, "b" * 64)
    ResultStore(tmp_path, "b" * 64, overwrite=True)  # explicit, then it is clean again
    assert not (tmp_path / ("b" * 16) / "run.json").exists()
