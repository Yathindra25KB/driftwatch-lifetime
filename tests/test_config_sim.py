"""Simulator keys in the run config: selector, delay, budget, pool, policies, monitors.

E0 configs must keep parsing and hashing exactly as before; the Phase 9 keys (monitors, the
monitor and matched policies) are emitted only when set, so earlier hashes do not move.
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
        ({"policy": "monitor", **SIM}, "needs a trigger"),
        ({"policy": {"name": "monitor", "trigger": "ks"}, **SIM}, "nonconf"),
        ({"policy": {"name": "matched", "trigger": "ks"}, **SIM, "nonconf": {}}, "source"),
        ({"policy": {"name": "monitor", "trigger": "ks", "period": 3}, **SIM}, "takes only"),
        (
            {"policy": {"name": "monitor", "trigger": "ks"}, **SIM, "nonconf": {}},
            "trigger listed in monitors.names",
        ),
        (
            {
                "policy": {"name": "monitor", "trigger": "ks", "min_gap": 0},
                **SIM,
                "nonconf": {},
                "monitors": {"names": ["ks"]},
            },
            "min_gap",
        ),
        ({**SIM, "nonconf": {}, "monitors": {"names": ["adwin"]}}, "monitors.names"),
        ({**SIM, "nonconf": {}, "monitors": {"names": ["ks", "ks"]}}, "distinct"),
        ({**SIM, "nonconf": {}, "monitors": {"names": ["ks"], "every": 2}}, "takes only"),
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
        ({**SIM, "selector": "uncertainty"}, "needs a nonconf block"),
        ({**SIM, "selector": "oracle"}, "selector"),
        ({**SIM, "selector": {"name": "random", "calibration_fraction": 1.5}}, "calibration"),
        ({**SIM, "pool": {"new_label_weight": 5.0, "truncation": "none"}}, "ADR-0007"),
        ({**SIM, "pool": {"new_label_weight": 1.0, "truncation": "last-3"}}, "ADR-0007"),
        ({**SIM, "pool": {"new_label_weight": 1.0, "surprise": 1}}, "pool"),
        ({**SIM, "nonconf": "logit"}, "nonconf takes only"),
        ({**SIM, "nonconf": {"score": "logit"}}, "nonconf.score"),
        ({**SIM, "nonconf": {"holdout_fraction": 1.5}}, "holdout_fraction"),
        ({**SIM, "nonconf": {"min_per_class": 20, "buffer_size": 10}}, "buffer_size"),
        (
            {**SIM, "selector": {"name": "random", "calibration_fraction": 0.0}, "nonconf": {}},
            "exchangeability trap",
        ),
        (
            {**SIM, "nonconf": {"trap_selected_calibration": True}},
            "only applies with calibration_fraction 0",
        ),
        ({**SIM, "monitors": {"names": ["mmd"]}}, "need a simulation config with a nonconf"),
        ({**SIM, "monitors": ["mmd"]}, "monitors takes only"),
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


def test_per_slot_random_split_needs_the_random_split_comparator() -> None:
    with pytest.raises(ConfigError, match="per_slot_random_split"):
        RunConfig.from_dict(
            cfg(e0={"variants": ["rolling"], "random_split": False, "per_slot_random_split": True})
        )


@pytest.mark.parametrize(
    "name",
    sorted(p.name for p in (ROOT / "configs").glob("e1_*.yaml"))
    + sorted(p.name for p in (ROOT / "configs").glob("li_*.yaml")),
)
def test_committed_phase_5_configs_parse(name: str) -> None:
    c = RunConfig.from_file(ROOT / "configs" / name)
    assert RunConfig.from_dict(c.to_dict()).to_dict() == c.to_dict()
    if name.startswith("e1_"):
        assert c.per_slot_random_split and c.random_split and c.policy == "never"
    elif "_never" not in name:
        assert c.is_simulation and c.policy == "periodic" and c.delay == 0


# --- Phase 8: the conformal layer in the config -------------------------------------------------


def test_nonconf_block_parses_hashes_and_leaves_e2_hashes_alone() -> None:
    plain = RunConfig.from_dict(cfg(**SIM, policy="periodic"))
    assert "nonconf" not in plain.to_dict()  # emitted only when set: E0 to E2 hashes unchanged
    conf = RunConfig.from_dict(
        cfg(
            **{**SIM, "selector": {"name": "credibility", "calibration_fraction": 0.2}},
            policy="periodic",
            nonconf={},
        )
    )
    n = conf.to_dict()["nonconf"]
    assert n == {
        "score": "probability",
        "holdout_fraction": 0.2,
        "min_per_class": 20,
        "buffer_size": 1000,
        "calibration_in_pool": False,
        "trap_selected_calibration": False,
    }
    assert RunConfig.from_dict(conf.to_dict()).to_dict() == conf.to_dict()  # round trip


def test_the_zero_reserved_share_is_a_named_trap() -> None:
    conf = RunConfig.from_dict(
        cfg(
            **{**SIM, "selector": {"name": "credibility", "calibration_fraction": 0.0}},
            policy="periodic",
            nonconf={"trap_selected_calibration": True},
        )
    )
    assert conf.nonconf is not None and conf.nonconf["trap_selected_calibration"] is True


def test_monitor_and_matched_policies_round_trip_and_label_their_arm() -> None:
    mon = RunConfig.from_dict(
        cfg(
            **SIM,
            policy={"name": "monitor", "trigger": "mmd"},
            nonconf={},
            monitors={"names": ["mmd", "ks"]},
        )
    )
    assert mon.policy_min_gap == 2 and mon.policy_label == "monitor-mmd"
    d = mon.to_dict()
    assert d["policy"] == {"name": "monitor", "trigger": "mmd", "min_gap": 2}
    assert d["monitors"] == {"names": ["mmd", "ks"], "cache": None}
    assert RunConfig.from_dict(d).to_dict() == d
    matched = RunConfig.from_dict(
        cfg(**SIM, policy={"name": "matched", "trigger": "mmd", "source": "r/x"}, nonconf={})
    )
    assert matched.policy_label == "matched-mmd" and matched.policy_source == "r/x"
    assert RunConfig.from_dict(matched.to_dict()).to_dict() == matched.to_dict()
    h = {config_hash(c.to_dict(), "v", "l") for c in (mon, matched)}
    assert len(h) == 2


def test_monitors_key_is_emitted_only_when_set() -> None:
    conf = RunConfig.from_dict(cfg(**SIM, policy="periodic", nonconf={}))
    assert "monitors" not in conf.to_dict() and conf.policy_label == "periodic"
