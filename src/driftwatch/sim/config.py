"""Run configuration: one strict YAML file per run, and the hash that identifies its results.

Keys follow plan Appendix C (``.claude/rules/configs.md``): dataset, slots, window
(nT, nE, stride), ratio, seeds, model, policy, selector, delay, budget_pct, nonconf, pool,
monitors, output. A config either describes the Phase 4 baseline (``selector``, ``delay`` and
``budget_pct`` null, ``policy: never``) or a simulation (Phase 5: all three set; ``policy``
never or periodic). ``nonconf`` and ``monitors`` belong to later phases and must be null, as
must monitor-triggered retraining: a config cannot ask for something this code does not do.
``e0`` lists the window variants to run (the key keeps its Phase 4 name so that E0 hashes stay
valid) and, in a simulation, the same variants apply.

E0 configs hash exactly as they did in Phase 4: ``to_dict`` emits the simulation keys only
when they are set.

The config hash covers every config value, the code version (git commit, ``-dirty`` when
the tree has uncommitted changes) and the lock file, so a changed config, change of code or
change of package pins gives a different hash.
"""

from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any

import yaml

from driftwatch.models import make_model

DATASETS = ("lamda", "bodmas")
PRESETS = ("adr-0004",)
VARIANTS = ("rolling", "rolling_chow", "sensitivity", "single_run")
POLICIES = ("never", "periodic")
SELECTORS = ("random",)
LATER_PHASE_KEYS = ("nonconf", "monitors")
SIM_KEYS = ("selector", "delay", "budget_pct", "pool")
DEFAULT_PERIOD = 3  # PROTOCOL.md: retrain every 3 slots
DEFAULT_CALIBRATION = 0.20  # PROTOCOL.md D8
TOP_KEYS = {
    "name",
    "dataset",
    "slots",
    "window",
    "ratio",
    "seeds",
    "model",
    "policy",
    "e0",
    "output",
    *SIM_KEYS,
    *LATER_PHASE_KEYS,
}
PACKAGES = (
    "numpy",
    "scipy",
    "pandas",
    "pyarrow",
    "scikit-learn",
    "lightgbm",
    "pyyaml",
    "psutil",
    "driftwatch-lifetime",
)


class ConfigError(ValueError):
    """The run config is not valid for this phase."""


def _int(value: Any, what: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ConfigError(f"{what} must be an integer >= {minimum}, got {value!r}")
    return value


def _policy(raw: Any) -> tuple[str, int | None]:
    """(name, period): ``policy`` is a name or ``{name, period}``; period only for periodic."""
    if isinstance(raw, dict):
        if set(raw) - {"name", "period"}:
            raise ConfigError(f"policy takes only name and period, got {sorted(raw)}")
        name, period = raw.get("name"), raw.get("period")
    else:
        name, period = raw, None
    if name == "monitor":
        raise ConfigError("monitor-triggered retraining is implemented in Phase 9")
    if name not in POLICIES:
        raise ConfigError(f"policy must be one of {POLICIES}, got {name!r}")
    if name == "never":
        if period is not None:
            raise ConfigError("policy never takes no period")
        return name, None
    if period is None:
        return name, DEFAULT_PERIOD
    return name, _int(period, "policy.period", 1)


def _simulation(d: dict[str, Any]) -> dict[str, Any] | None:
    """Simulation fields, or ``None`` for a baseline config. All of them or none."""
    selector, delay, budget = d.get("selector"), d.get("delay"), d.get("budget_pct")
    present = {k: d.get(k) is not None for k in ("selector", "delay", "budget_pct")}
    if not any(present.values()):
        if d.get("pool") is not None:
            raise ConfigError("pool needs selector, delay and budget_pct (a simulation config)")
        return None
    missing = [k for k, ok in present.items() if not ok]
    if missing:
        raise ConfigError(f"a simulation config needs selector, delay and budget_pct; no {missing}")

    if isinstance(selector, dict):
        if set(selector) - {"name", "calibration_fraction"}:
            raise ConfigError(f"selector takes only name and calibration_fraction: {selector}")
        name, calibration = selector.get("name"), selector.get("calibration_fraction")
    else:
        name, calibration = selector, None
    if name in ("uncertainty", "credibility"):
        raise ConfigError(f"selector {name!r} needs the conformal layer (Phase 8)")
    if name not in SELECTORS:
        raise ConfigError(f"selector must be one of {SELECTORS}, got {name!r}")
    if calibration is None:
        calibration = DEFAULT_CALIBRATION
    if isinstance(calibration, bool) or not isinstance(calibration, int | float):
        raise ConfigError(f"calibration_fraction must be a number, got {calibration!r}")
    if not 0.0 <= float(calibration) <= 1.0:
        raise ConfigError(f"calibration_fraction must lie in [0, 1], got {calibration!r}")

    delay = _int(delay, "delay", 0)
    if isinstance(budget, bool) or not isinstance(budget, int | float) or not 0 < budget <= 100:
        raise ConfigError(f"budget_pct must be a percentage in (0, 100], got {budget!r}")

    pool = d.get("pool") or {}
    if set(pool) - {"new_label_weight", "truncation"}:
        raise ConfigError(f"pool takes only new_label_weight and truncation, got {sorted(pool)}")
    weight, truncation = pool.get("new_label_weight", 1.0), pool.get("truncation", "none")
    if isinstance(weight, bool) or weight != 1.0:
        raise ConfigError(
            f"pool.new_label_weight is fixed at 1 by ADR-0007 (no free parameter), got {weight!r}"
        )
    if truncation != "none":
        raise ConfigError(f"pool.truncation is fixed at none by ADR-0007, got {truncation!r}")
    return {
        "selector": name,
        "calibration_fraction": float(calibration),
        "delay": delay,
        "budget_pct": float(budget),
        "pool_new_label_weight": 1.0,
        "pool_truncation": "none",
    }


@dataclass(frozen=True)
class RunConfig:
    name: str
    dataset: str
    preset: str
    min_malware: int
    nT: int
    nE: int
    stride: int
    target_ratio: float
    sensitivity_ratio: float | None
    seeds: tuple[int, ...]
    models: tuple[dict[str, Any], ...]
    policy: str
    variants: tuple[str, ...]
    random_split: bool
    output: str
    per_slot_random_split: bool = False
    policy_period: int | None = None
    selector: str | None = None
    calibration_fraction: float | None = None
    delay: int | None = None
    budget_pct: float | None = None
    pool_new_label_weight: float | None = None
    pool_truncation: str | None = None

    @property
    def is_simulation(self) -> bool:
        return self.selector is not None

    # -- parsing -----------------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: Path | str) -> RunConfig:
        text = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ConfigError(f"{path}: the config must be a mapping")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunConfig:
        unknown = sorted(set(d) - TOP_KEYS)
        if unknown:
            raise ConfigError(f"unknown key(s) in config: {unknown}; allowed {sorted(TOP_KEYS)}")
        for key in LATER_PHASE_KEYS:
            if d.get(key) is not None:
                raise ConfigError(f"{key!r} belongs to a later phase and must be null")
        policy, period = _policy(d.get("policy"))
        sim = _simulation(d)
        if policy == "periodic" and sim is None:
            raise ConfigError(
                "policy periodic needs selector, delay and budget_pct (a simulation config)"
            )
        if d.get("dataset") not in DATASETS:
            raise ConfigError(f"dataset must be one of {DATASETS}, got {d.get('dataset')!r}")

        slots = d.get("slots") or {}
        if slots.get("preset") not in PRESETS:
            raise ConfigError(f"slots.preset must be one of {PRESETS}, got {slots.get('preset')!r}")
        min_malware = _int(slots.get("min_malware"), "slots.min_malware", 1)

        w = d.get("window") or {}
        if set(w) != {"nT", "nE", "stride"}:
            raise ConfigError("window needs exactly nT, nE and stride")
        nT = _int(w["nT"], "window.nT", 1)
        nE = _int(w["nE"], "window.nE", 2)  # AUT needs at least two evaluation slots
        stride = _int(w["stride"], "window.stride", 1)

        r = d.get("ratio") or {}
        target = r.get("target")
        if not isinstance(target, float | int) or not 0.0 < float(target) < 1.0:
            raise ConfigError(f"ratio.target must lie strictly between 0 and 1, got {target!r}")
        sens = r.get("sensitivity")
        if sens is not None and (
            not isinstance(sens, float | int) or not 0.0 < float(sens) < 1.0 or sens == target
        ):
            raise ConfigError(f"ratio.sensitivity must differ from the target, got {sens!r}")

        seeds = d.get("seeds")
        if not isinstance(seeds, list) or not seeds:
            raise ConfigError("seeds must be an explicit non-empty list of integers")
        if any(isinstance(s, bool) or not isinstance(s, int) or s < 0 for s in seeds):
            raise ConfigError(f"seeds must be non-negative integers, got {seeds!r}")
        if len(set(seeds)) != len(seeds):
            raise ConfigError(f"seeds must be distinct, got {seeds!r}")

        models = d.get("model")
        if not isinstance(models, list) or not models:
            raise ConfigError("model must be a non-empty list of {name: ..., hyperparameters}")
        for spec in models:
            try:
                make_model(spec, seed=0)
            except (ValueError, TypeError) as exc:
                raise ConfigError(str(exc)) from exc
        names = [m["name"] for m in models]
        if len(set(names)) != len(names):
            raise ConfigError(f"model names must be distinct (they key every result row): {names}")

        e0 = d.get("e0") or {}
        per_slot = e0.get("per_slot_random_split", False)
        if not isinstance(per_slot, bool):
            raise ConfigError(f"e0.per_slot_random_split must be true or false, got {per_slot!r}")
        if per_slot and not bool(e0.get("random_split", True)):
            raise ConfigError("per_slot_random_split needs e0.random_split (the same draw)")
        variants = tuple(e0.get("variants") or ("rolling",))
        for v in variants:
            if v not in VARIANTS:
                raise ConfigError(f"unknown variant {v!r}; choose from {VARIANTS}")
        if "sensitivity" in variants and sens is None:
            raise ConfigError("the sensitivity variant needs ratio.sensitivity")
        if len(set(variants)) != len(variants):
            raise ConfigError("variants must be distinct")

        return cls(
            name=str(d.get("name") or "run"),
            dataset=d["dataset"],
            preset=slots["preset"],
            min_malware=min_malware,
            nT=nT,
            nE=nE,
            stride=stride,
            target_ratio=float(target),
            sensitivity_ratio=None if sens is None else float(sens),
            seeds=tuple(int(s) for s in seeds),
            models=tuple(dict(m) for m in models),
            policy=policy,
            variants=variants,
            random_split=bool(e0.get("random_split", True)),
            output=str(d.get("output") or "results/e0"),
            per_slot_random_split=per_slot,
            policy_period=period,
            **(sim or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """The canonical form: what is hashed, logged and re-parsed."""
        e0: dict[str, Any] = {"variants": list(self.variants), "random_split": self.random_split}
        if self.per_slot_random_split:
            e0["per_slot_random_split"] = True
        out: dict[str, Any] = {
            "name": self.name,
            "dataset": self.dataset,
            "slots": {"preset": self.preset, "min_malware": self.min_malware},
            "window": {"nT": self.nT, "nE": self.nE, "stride": self.stride},
            "ratio": {"target": self.target_ratio, "sensitivity": self.sensitivity_ratio},
            "seeds": list(self.seeds),
            "model": [dict(m) for m in self.models],
            "policy": self.policy,
            "e0": e0,
            "output": self.output,
        }
        if self.policy == "periodic":
            out["policy"] = {"name": "periodic", "period": self.policy_period}
        if self.is_simulation:
            out["selector"] = {
                "name": self.selector,
                "calibration_fraction": self.calibration_fraction,
            }
            out["delay"] = self.delay
            out["budget_pct"] = self.budget_pct
            out["pool"] = {
                "new_label_weight": self.pool_new_label_weight,
                "truncation": self.pool_truncation,
            }
        return out


# --- hashes and environment ---------------------------------------------------------------


def lock_sha256(repo_root: Path | str) -> str:
    """SHA-256 of ``uv.lock`` with line endings normalised (Windows and Linux agree)."""
    raw = (Path(repo_root) / "uv.lock").read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def config_hash(config: dict[str, Any], code_version: str, lock_hash: str) -> str:
    """Hash of the config values, the code version and the lock file."""
    body = {"config": config, "code_version": code_version, "lock_sha256": lock_hash}
    text = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def package_versions() -> dict[str, str]:
    out = {"python": platform.python_version()}
    for name in PACKAGES:
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = "unknown"
    return out
