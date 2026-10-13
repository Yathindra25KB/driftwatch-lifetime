"""Simulator keys in the run config (Phase 5): selector, delay, budget, pool, periodic policy.

E0 configs must keep parsing and hashing exactly as before; later-phase keys (nonconf,
monitors, monitor-triggered retraining) must still be refused.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from driftwatch.sim.config import ConfigError, RunConfig, config_hash

ROOT = Path(__file__).resolve().parents[1]

BASE = {
    "name": "t",
    "dataset": "bodmas",
    "slots": {"preset": "adr-0004", "min_malware": 50},
    "window": {"nT": 3, "nE": 6, "stride": 2},
    "ratio": {"target": 0.10, "sensitivity": 0.05},
    "seeds": [0, 1],
    "model": [{"name": "lr"}],
    "policy": "never",
    "e0": {"variants": ["rolling"], "random_split": False},
    "output": "results/e1",
}
SIM = {"selector": "random", "delay": 1, "budget_pct": 1.0}


def cfg(**changes) -> dict:
    d = json.loads(json.dumps(BASE))
    d.update(changes)
    return d


def test_an_e0_config_is_not_a_simulation_and_its_dict_has_no_new_keys() -> None:
    c = RunConfig.from_dict(cfg())
    assert not c.is_simulation
    d = c.to_dict()
    for key in ("selector", "delay", "budget_pct", "pool"):
        assert key not in d
    assert d["policy"] == "never" and "per_slot_random_split" not in d["e0"]


def test_committed_e0_configs_still_parse_and_round_trip() -> None:
    for name in ("e0_bodmas.yaml", "e0_lamda.yaml"):
        c = RunConfig.from_file(ROOT / "configs" / name)
        assert not c.is_simulation
        assert RunConfig.from_dict(c.to_dict()).to_dict() == c.to_dict()


def test_a_simulation_config_round_trips_with_defaults_filled_in() -> None:
    c = RunConfig.from_dict(cfg(policy={"name": "periodic", "period": 3}, **SIM))
    assert c.is_simulation and c.policy == "periodic" and c.policy_period == 3
    assert (c.selector, c.delay, c.budget_pct) == ("random", 1, 1.0)
    assert c.calibration_fraction == 0.20
    assert (c.pool_new_label_weight, c.pool_truncation) == (1.0, "none")
    d = c.to_dict()
    assert d["policy"] == {"name": "periodic", "period": 3}
    assert d["selector"] == {"name": "random", "calibration_fraction": 0.20}
    assert d["pool"] == {"new_label_weight": 1.0, "truncation": "none"}
    assert RunConfig.from_dict(d).to_dict() == d


def test_periodic_as_a_bare_string_uses_the_protocol_period() -> None:
    c = RunConfig.from_dict(cfg(policy="periodic", **SIM))
    assert c.policy_period == 3


def test_new_keys_change_the_hash_and_equal_configs_agree() -> None:
    a = RunConfig.from_dict(cfg(policy="periodic", **SIM))
    b = RunConfig.from_dict(cfg(policy="periodic", **{**SIM, "delay": 2}))
    c = RunConfig.from_dict(cfg(policy="periodic", **{**SIM, "budget_pct": 5.0}))
    h = [config_hash(x.to_dict(), "v", "l") for x in (a, b, c)]
    assert len(set(h)) == 3
    again = RunConfig.from_dict(a.to_dict())
    assert config_hash(again.to_dict(), "v", "l") == h[0]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"policy": "monitor", **SIM}, "Phase 9"),
        ({"policy": "sometimes", **SIM}, "policy"),
        ({"policy": "periodic"}, "periodic"),  # needs selector, delay and budget
        ({"selector": "random", "delay": 1}, "budget_pct"),
        ({"selector": "random", "budget_pct": 1.0}, "delay"),
        ({"delay": 1, "budget_pct": 1.0}, "selector"),
        ({**SIM, "delay": -1}, "delay"),
        ({**SIM, "delay": 1.5}, "delay"),
        ({**SIM, "delay": True}, "delay"),
        ({**SIM, "budget_pct": 0}, "budget_pct"),
        ({**SIM, "budget_pct": 101}, "budget_pct"),
        ({**SIM, "selector": "uncertainty"}, "Phase 8"),
        ({**SIM, "selector": "oracle"}, "selector"),
        ({**SIM, "selector": {"name": "random", "calibration_fraction": 1.5}}, "calibration"),
        ({**SIM, "pool": {"new_label_weight": 5.0, "truncation": "none"}}, "ADR-0007"),
        ({**SIM, "pool": {"new_label_weight": 1.0, "truncation": "last-3"}}, "ADR-0007"),
        ({**SIM, "pool": {"new_label_weight": 1.0, "surprise": 1}}, "pool"),
        ({**SIM, "nonconf": "logit"}, "later phase"),
        ({**SIM, "monitors": ["mmd"]}, "later phase"),
        ({"policy": {"name": "periodic", "period": 0}, **SIM}, "period"),
        ({"policy": {"name": "never", "period": 3}, **SIM}, "period"),
    ],
)
def test_invalid_simulation_configs_raise(changes: dict, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        RunConfig.from_dict(cfg(**changes))


def test_yaml_with_simulation_keys_loads(tmp_path: Path) -> None:
    path = tmp_path / "s.yaml"
    path.write_text(yaml.safe_dump(cfg(policy="periodic", **SIM)), encoding="utf-8")
    c = RunConfig.from_file(path)
    assert c.delay == 1 and c.policy == "periodic"


def test_per_slot_random_split_is_a_flag_of_the_baseline_block() -> None:
    c = RunConfig.from_dict(
        cfg(e0={"variants": ["rolling"], "random_split": True, "per_slot_random_split": True})
    )
    assert c.per_slot_random_split
    assert c.to_dict()["e0"]["per_slot_random_split"] is True
    with pytest.raises(ConfigError, match="per_slot_random_split"):
        RunConfig.from_dict(
            cfg(e0={"variants": ["rolling"], "random_split": False, "per_slot_random_split": 3})
        )
