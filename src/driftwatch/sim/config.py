"""Run configuration: one strict YAML file per run, and the hash that identifies its results.

Keys follow plan Appendix C (``.claude/rules/configs.md``): dataset, slots, window
(nT, nE, stride), ratio, seeds, model, policy, selector, delay, budget_pct, nonconf, pool,
monitors, output. Phase 4 runs only the never-retrain baseline (E0), so ``policy`` must be
``never`` and the keys that belong to later phases must be absent or null: a config cannot
ask for something this code does not do. ``e0`` lists the variants to run.

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
POLICIES = ("never",)
LATER_PHASE_KEYS = ("selector", "delay", "budget_pct", "nonconf", "pool", "monitors")
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
                raise ConfigError(f"{key!r} belongs to a later phase and must be null in E0")
        if d.get("policy") not in POLICIES:
            raise ConfigError(f"policy must be one of {POLICIES}, got {d.get('policy')!r}")
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
        nE = _int(w["nE"], "window.nE", 1)
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

        e0 = d.get("e0") or {}
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
            policy=d["policy"],
            variants=variants,
            random_split=bool(e0.get("random_split", True)),
            output=str(d.get("output") or "results/e0"),
        )

    def to_dict(self) -> dict[str, Any]:
        """The canonical form: what is hashed, logged and re-parsed."""
        return {
            "name": self.name,
            "dataset": self.dataset,
            "slots": {"preset": self.preset, "min_malware": self.min_malware},
            "window": {"nT": self.nT, "nE": self.nE, "stride": self.stride},
            "ratio": {"target": self.target_ratio, "sensitivity": self.sensitivity_ratio},
            "seeds": list(self.seeds),
            "model": [dict(m) for m in self.models],
            "policy": self.policy,
            "e0": {"variants": list(self.variants), "random_split": self.random_split},
            "output": self.output,
        }


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
