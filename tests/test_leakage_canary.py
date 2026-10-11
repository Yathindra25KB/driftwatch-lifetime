"""The leakage canary (Build Guide section 8): shuffle timestamps, AUT must jump.

With true timestamps a drifting problem decays. With timestamps shuffled, training and
evaluation slots are exchangeable, so AUT moves toward what a random split would report. If
it does not, the slicer is not using time the way it claims, and the stop rule applies:
diagnose and fix the slicer before anything else.

The committed fixture has features that are independent of labels, so nothing on it can
decay and the canary cannot move there. The movement is therefore tested on seeded
synthetic timelines with planted drift (driftwatch.data.synthetic). The fixture caches only
prove the script runs end to end.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from driftwatch.data import constraints, slicer
from driftwatch.data.canary import (
    CanaryError,
    NearestCentroid,
    aut,
    f1_malware,
    run_canary,
    shuffle_timestamps,
)
from driftwatch.data.constraints import C1Violation, ConstraintViolation
from driftwatch.data.slicer import WindowSpec, _stack
from driftwatch.data.synthetic import drifting_timeline
from driftwatch.data.tables import FixedWidthScheme, TableSource

ROOT = Path(__file__).resolve().parents[1]
SPEC = WindowSpec(nT=3, nE=10, stride=1, target_ratio=0.10, min_malware=10, seed=0)


def source_for(table: pd.DataFrame, X: np.ndarray) -> TableSource:
    scheme = FixedWidthScheme(np.datetime64("2019-01-07", "ns"), np.timedelta64(14, "D"))
    return TableSource(table, scheme, x=X, name="synthetic")


# --- building blocks ------------------------------------------------------------------------


def test_aut_follows_the_guides_trapezoid_formula():
    # AUT(f, N) = 1/(N-1) * sum_{k=1..N-1} (f_k + f_{k+1}) / 2
    assert aut([1.0, 0.5, 0.5]) == pytest.approx(0.5 * ((1.0 + 0.5) / 2 + (0.5 + 0.5) / 2))
    assert aut([0.7, 0.7, 0.7, 0.7]) == pytest.approx(0.7)  # no decay at all
    with pytest.raises(CanaryError):
        aut([0.9])


def test_f1_is_the_malware_class_f1():
    y = np.array([1, 1, 1, 0, 0, 0])
    pred = np.array([1, 1, 0, 1, 0, 0])
    assert f1_malware(y, pred) == pytest.approx(2 * 2 / (2 * 2 + 1 + 1))
    assert f1_malware(np.zeros(4, int), np.zeros(4, int)) == 0.0


def test_trivial_model_separates_a_clean_problem_and_accepts_sparse_input():
    rng = np.random.default_rng(0)
    y = (rng.random(400) < 0.3).astype(np.int8)
    X = rng.normal(size=(400, 8)).astype(np.float32)
    X[y == 1, :3] += 3.0
    dense = NearestCentroid().fit(X, y)
    assert f1_malware(y, dense.predict(X)) > 0.9
    sparse = NearestCentroid().fit(sp.csr_matrix(X), y)
    assert np.array_equal(dense.predict(X), sparse.predict(sp.csr_matrix(X)))


def test_shuffling_permutes_timestamps_and_keeps_every_other_column():
    table, _ = drifting_timeline(n_slots=6, rows_per_slot=50, seed=1)
    shuffled = shuffle_timestamps(table, seed=2)
    assert sorted(shuffled["ts"].tolist()) == sorted(table["ts"].tolist())
    assert not shuffled["ts"].equals(table["ts"])
    assert shuffled["label"].equals(table["label"]) and shuffled["row_id"].equals(table["row_id"])
    assert shuffle_timestamps(table, seed=2)["ts"].equals(shuffled["ts"])  # seeded


# --- the canary -----------------------------------------------------------------------------


def test_shuffled_timestamps_move_aut_toward_the_random_split_score():
    table, X = drifting_timeline(n_slots=16, rows_per_slot=300, drift=1.0, seed=7)
    result = run_canary(source_for(table, X), SPEC, seed=0)
    assert result.aut_true < result.f1_random - 0.15, "the planted drift should hurt the true AUT"
    assert result.aut_shuffled > result.aut_true + 0.15, "shuffled AUT must be clearly above"
    assert abs(result.aut_shuffled - result.f1_random) < abs(result.aut_true - result.f1_random)
    assert result.closure is not None and result.closure >= 0.5
    assert result.verdict == "PASS" and result.leakage_warning is False


def test_canary_is_seeded():
    table, X = drifting_timeline(n_slots=16, rows_per_slot=300, seed=7)
    a = run_canary(source_for(table, X), SPEC, seed=3)
    b = run_canary(source_for(table, X), SPEC, seed=3)
    assert a.as_record() == b.as_record()


def test_without_drift_the_canary_has_nothing_to_move():
    """Negative control: a canary that always 'passes' proves nothing."""
    table, X = drifting_timeline(n_slots=16, rows_per_slot=300, drift=0.0, seed=7)
    result = run_canary(source_for(table, X), SPEC, seed=0)
    assert result.verdict == "NO_GAP"
    assert abs(result.aut_shuffled - result.aut_true) < 0.1


def _leak_everything(monkeypatch: pytest.MonkeyPatch, n_future: int | None = None) -> None:
    """Make the slicer train on the window's first ``n_future`` evaluation slots (all if None)."""
    original = slicer._train_rows

    def leaky(source, planned, plan):
        rows = list(original(source, planned, plan))
        future = [source.load_slot(ref.slot_id) for ref in plan.eval[:n_future]]
        last = rows[-1]
        parts = [last, *future]
        rows[-1] = slicer.SlotRows(
            ref=last.ref,
            y=np.concatenate([p.y for p in parts]),
            ts=np.concatenate([p.ts for p in parts]),
            row_id=np.concatenate([p.row_id for p in parts]),
            X=_stack([p.X for p in parts]),
            fv_hash=None,
        )
        return tuple(rows)

    monkeypatch.setattr(slicer, "_train_rows", leaky)


def _silence_checks(monkeypatch) -> None:
    monkeypatch.setattr(constraints, "check_c1", lambda train_ts, eval_ts: None)
    monkeypatch.setattr(constraints, "check_c2", lambda ts, y, start, end: None)


def test_the_slicers_own_checks_stop_a_leak_before_the_canary_runs(monkeypatch):
    _leak_everything(monkeypatch)
    table, X = drifting_timeline(n_slots=16, rows_per_slot=300, drift=1.0, seed=7)
    with pytest.raises(ConstraintViolation):  # C2 on the training slots fires first
        run_canary(source_for(table, X), SPEC, seed=0)


def test_c1_alone_also_stops_a_leak_when_the_training_window_check_is_silenced(monkeypatch):
    _leak_everything(monkeypatch)
    monkeypatch.setattr(constraints, "check_c2", lambda ts, y, start, end: None)
    table, X = drifting_timeline(n_slots=16, rows_per_slot=300, drift=1.0, seed=7)
    with pytest.raises(C1Violation):
        run_canary(source_for(table, X), SPEC, seed=0)


def test_the_canary_still_flags_a_leak_when_the_checks_have_been_disabled(monkeypatch):
    """Last line of defence: leak the future AND silence C1 and C2, and AUT gives it away."""
    _leak_everything(monkeypatch)
    _silence_checks(monkeypatch)
    table, X = drifting_timeline(n_slots=16, rows_per_slot=300, drift=1.0, seed=7)
    result = run_canary(source_for(table, X), SPEC, seed=0)
    assert result.verdict == "NO_GAP"  # true-time AUT is already at the random-split level
    assert result.aut_true > 0.9 and result.leakage_warning is True


def test_canary_sensitivity_to_partial_leaks_is_pinned_not_assumed(monkeypatch):
    """Review finding 2: the canary only sees leaks big enough to close the gap.

    Leaking 3 of 10 evaluation slots closes it (NO_GAP, which the script exits non-zero
    on); leaking 1 raises AUT but leaves the gap open, so only C1/C2 and the oracle tests
    catch that. The test records the limit so nobody reads PASS as "no leak at all".
    """
    table, X = drifting_timeline(n_slots=16, rows_per_slot=300, drift=1.0, seed=7)
    clean = run_canary(source_for(table, X), SPEC, seed=0)
    with monkeypatch.context() as mp:
        _silence_checks(mp)
        _leak_everything(mp, n_future=1)
        small = run_canary(source_for(table, X), SPEC, seed=0)
    assert small.aut_true > clean.aut_true + 0.02, "a leak must raise the true-time AUT"
    assert small.verdict == "PASS"  # the limit: undetected by the canary alone
    with monkeypatch.context() as mp:
        _silence_checks(mp)
        _leak_everything(mp, n_future=3)
        large = run_canary(source_for(table, X), SPEC, seed=0)
    assert large.verdict == "NO_GAP" and large.leakage_warning is True


def test_a_canary_with_no_window_is_an_error_not_a_pass():
    table, X = drifting_timeline(n_slots=3, rows_per_slot=300, seed=7)
    with pytest.raises(CanaryError):
        run_canary(source_for(table, X), SPEC, seed=0)


# --- the script -----------------------------------------------------------------------------


def _write_drifting_bodmas_raw(
    raw_root: Path, *, n_weeks: int = 10, per_week: int = 120, drift: float = 1.0
) -> None:
    """Raw BODMAS-format files (same layout as the real download) with planted drift."""
    table, X = drifting_timeline(
        n_slots=n_weeks,
        rows_per_slot=per_week,
        malware_share=0.25,
        n_features=2381,
        width_days=7,
        start="2019-08-26",
        drift=drift,
        seed=11,
    )
    raw = raw_root / "raw" / "bodmas"
    raw.mkdir(parents=True)
    rng = np.random.default_rng(3)
    sha = [rng.bytes(32).hex() for _ in range(len(table))]
    y = table["label"].to_numpy()
    stamps = [t.tz_localize("UTC").isoformat(sep=" ") for t in table["ts"]]
    family = ["wacatac" if v else "" for v in y]
    pd.DataFrame({"sha": sha, "timestamp": stamps, "family": family}).to_csv(
        raw / "bodmas_metadata.csv", index=False, lineterminator="\n"
    )
    malware = [s for s, v in zip(sha, y, strict=True) if v]
    pd.DataFrame({"sha256": malware, "category": "trojan"}).to_csv(
        raw / "bodmas_malware_category.csv", index=False, lineterminator="\n"
    )
    with zipfile.ZipFile(raw / "bodmas.npz", "w") as zf:
        for name, arr in (("X.npy", X), ("y.npy", y.astype(np.int32))):
            buf = io.BytesIO()
            np.lib.format.write_array(buf, arr, allow_pickle=False)
            zf.writestr(name, buf.getvalue())
    (raw / "SOURCE.json").write_text('{"dataset": "bodmas", "fixture": true}\n', encoding="utf-8")


def _canary_cmd(root: Path, out: Path, *, nT: int, nE: int, min_malware: int) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "scripts" / "leakage_canary.py"),
        "bodmas",
        "--root",
        str(root),
        "--length",
        "1w",
        "--ratio",
        "0.10",
        "--min-malware",
        str(min_malware),
        "--nT",
        str(nT),
        "--nE",
        str(nE),
        "--out",
        str(out),
    ]


def test_canary_script_passes_end_to_end_on_a_built_cache_with_planted_drift(tmp_path):
    """raw files -> `data build` caches -> presets -> slicer -> canary script, unmocked."""
    from driftwatch.data.build import build_dataset
    from driftwatch.data.cache import Layout

    _write_drifting_bodmas_raw(tmp_path)
    build_dataset("bodmas", Layout(tmp_path), raw_layout=Layout(tmp_path), batch_size=256)
    out = tmp_path / "canary.json"
    proc = subprocess.run(
        _canary_cmd(tmp_path, out, nT=2, nE=6, min_malware=5),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["verdict"] == "PASS", record
    assert record["aut_shuffled"] > record["aut_true"] + 0.15
    assert {"aut_true", "aut_shuffled", "f1_random", "spec", "dataset", "memory"} <= set(record)
    assert record["dataset"] == "bodmas" and record["spec"]["nT"] == 2
    assert record["source"]["kind"] == "cache" and record["source"]["x_format"] == "dense-npy"


def test_canary_script_reports_when_the_caches_hold_no_window(built_data, tmp_path):
    """The committed fixture has no run of three usable weeks: exit 2, no fake verdict."""
    out = tmp_path / "canary.json"
    proc = subprocess.run(
        _canary_cmd(built_data, out, nT=1, nE=2, min_malware=2),
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "no window" in proc.stderr and not out.exists()
