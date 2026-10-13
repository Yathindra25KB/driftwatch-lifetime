"""The spy test: held-back labels are reachable only through the queue and the metric door.

``EvalSlot`` carries ``y``, ``ts`` and ``row_id``. Here those three are replaced by spies that
record the module of every caller and raise on any operation they do not expect. A stream is
then driven through the real selector, policy, pool and queue; every recorded read must come
from ``driftwatch.sim.queue`` (the release door and the scoring door), and selectors, policies
and the pool must not read at all (hard rules 3 and 4; ADR-0004 addendum 1).
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import numpy as np
import pytest
from simstream import N_EVAL, Spy, eval_slots, train_window

from driftwatch.data.slicer import OpaqueSlot
from driftwatch.sim.policies import Periodic
from driftwatch.sim.pool import TrainingPool
from driftwatch.sim.queue import LabelQueue, SealedSlot
from driftwatch.sim.selectors import RandomSelector, selector_rng

SIM = Path(__file__).resolve().parents[1] / "src" / "driftwatch" / "sim"


def spied_slots(log):
    out = []
    for slot in eval_slots():
        out.append(
            dataclasses.replace(
                slot,
                y=Spy(slot.y, "y", log),
                ts=Spy(slot.ts, "ts", log),
                row_id=Spy(slot.row_id, "row_id", log),
            )
        )
    return out


def drive(log, *, delay: int = 1, budget: int = 5):
    """The runner's loop in miniature, with a read-counter around every non-label component."""
    slots = [SealedSlot(s) for s in spied_slots(log)]
    queue = LabelQueue(delay=delay, n_slots=N_EVAL)
    pool = TrainingPool(train_window())
    policy, selector = Periodic(period=3), RandomSelector()
    quiet_reads = []
    for s, slot in enumerate(slots):
        released = queue.release(s)
        pool.add(released)
        before = len(log)
        retrain = policy.should_retrain(s)
        public = slot.public()
        selection = selector.select(public, budget, selector_rng(0, public.slot_id))
        quiet_reads.append(len(log) - before)
        if retrain:
            pool.mark_fitted()
        pred = np.zeros(slot.n, dtype=np.int8)
        slot.score(pred)
        queue.query(s, slot, selection)
    return queue, pool, quiet_reads


def test_every_label_read_comes_from_the_queue_module_and_selectors_policies_read_nothing() -> None:
    log: list[tuple[str, str, str]] = []
    queue, pool, quiet_reads = drive(log)
    assert queue.n_queued > 0 and pool.n_arrived > 0  # the stream really moved labels
    assert log, "the spy saw no reads at all; the test is not exercising the queue"
    assert {caller for caller, _, _ in log} == {"driftwatch.sim.queue"}
    assert quiet_reads == [0] * N_EVAL  # policy + selector never touched y, ts or row_id


def test_label_reads_during_scoring_are_for_metrics_only() -> None:
    log: list[tuple[str, str, str]] = []
    slot = SealedSlot(spied_slots(log)[0])
    slot.score(np.zeros(slot.n, dtype=np.int8))
    assert {caller for caller, _, _ in log} == {"driftwatch.sim.queue"}
    assert {field for _, field, _ in log} == {"y", "row_id"}


def test_the_public_view_exposes_features_and_handles_only() -> None:
    slot = SealedSlot(eval_slots()[0])
    pub = slot.public()
    assert isinstance(pub, OpaqueSlot)
    assert {f.name for f in dataclasses.fields(pub)} == {"dataset", "slot_id", "X", "handle"}
    assert not hasattr(pub, "_slot") and not hasattr(pub, "y")


def test_a_hostile_consumer_has_nothing_to_reach() -> None:
    log: list[tuple[str, str, str]] = []
    pub = SealedSlot(spied_slots(log)[0]).public()
    for name in ("y", "ts", "row_id", "slot", "_slot", "perm", "ref", "c3"):
        assert not hasattr(pub, name)
    assert not log


# --- static boundary: who may import what ------------------------------------------------------


def toplevel_imports(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    """(module, names) for imports that run at import time (not under TYPE_CHECKING)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            found.append((node.module or "", tuple(a.name for a in node.names)))
        elif isinstance(node, ast.Import):
            found.extend((a.name, ()) for a in node.names)
    return found


FORBIDDEN_NAMES = {"EvalSlot", "Window", "SealedSlot", "LabelQueue", "Released"}
FORBIDDEN_MODULES = {
    "driftwatch.sim.queue",
    "driftwatch.sim.runner",
    "driftwatch.metrics",
    "driftwatch.metrics.slot",
    "driftwatch.data.constraints",
}


@pytest.mark.parametrize("module", ["selectors.py", "policies.py"])
def test_selectors_and_policies_cannot_import_the_label_holders(module: str) -> None:
    for mod, names in toplevel_imports(SIM / module):
        assert mod not in FORBIDDEN_MODULES, f"{module} imports {mod}"
        assert not FORBIDDEN_NAMES & set(names), f"{module} imports {sorted(names)}"
        if mod == "driftwatch.data.slicer":
            assert set(names) <= {"OpaqueSlot"}, f"{module} imports {names} from the slicer"


def test_the_pool_imports_only_the_initial_window_type() -> None:
    for mod, names in toplevel_imports(SIM / "pool.py"):
        assert mod not in FORBIDDEN_MODULES
        assert not FORBIDDEN_NAMES & set(names)
        if mod == "driftwatch.data.slicer":
            assert set(names) <= {"TrainWindow", "_stack"}


def test_only_the_queue_module_reads_slot_labels() -> None:
    """No other sim module touches ``.y[`` or ``.row_id[`` on a slot-like object."""
    for path in SIM.glob("*.py"):
        if path.name in {"queue.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "_slot.y" not in text and "slot.y[" not in text, path.name
