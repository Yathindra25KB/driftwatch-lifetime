"""The training pool: initial window plus every label that has arrived (ADR-0007).

Design (fixed by the researcher before any grid run, not chosen by AUT):

- **Composition:** the initial training window's raw rows, then released labels in arrival
  order. Arrived rows are C3-subsampled evaluation rows (about the target malware ratio); the
  initial rows are raw. ADR-0007 states that mix.
- **Weight:** every row counts once. There is no new-label weight to tune.
- **Truncation:** none. Nothing is dropped as the window advances; a label that would arrive
  after the window ends never reaches the pool (it is ignored by the queue).

The pool never holds a slot or a handle, only rows that were already released.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from driftwatch.data.slicer import TrainWindow, _stack

if TYPE_CHECKING:
    from driftwatch.sim.queue import Released


class TrainingPool:
    def __init__(self, initial: TrainWindow) -> None:
        self._initial_X = initial.X
        self._initial_y = initial.y
        self._initial_ts = initial.ts
        self._initial_row_id = initial.row_id
        self._parts_X: list[Any] = []
        self._parts_y: list[np.ndarray] = []
        self._parts_ts: list[np.ndarray] = []
        self._parts_row_id: list[np.ndarray] = []
        self._parts_queried_in: list[np.ndarray] = []
        self._n_new = 0
        self._cache: tuple[Any, np.ndarray] | None = None

    @property
    def n_initial(self) -> int:
        return len(self._initial_y)

    @property
    def n_arrived(self) -> int:
        return sum(len(y) for y in self._parts_y)

    @property
    def n(self) -> int:
        return self.n_initial + self.n_arrived

    @property
    def n_new_since_fit(self) -> int:
        return self._n_new

    def add(self, released: Released) -> None:
        """Append the rows that arrived at one slot (an empty release changes nothing)."""
        if len(released) == 0:
            return
        self._parts_X.append(released.X)
        self._parts_y.append(released.y)
        self._parts_ts.append(released.ts)
        self._parts_row_id.append(released.row_id)
        self._parts_queried_in.append(released.queried_in)
        self._n_new += len(released)
        self._cache = None

    def mark_fitted(self) -> None:
        self._n_new = 0

    def _materialise(self) -> tuple[Any, np.ndarray]:
        if self._cache is None:
            X = _stack([self._initial_X, *self._parts_X])
            y = np.concatenate([self._initial_y, *self._parts_y])
            self._cache = (X, y)
        return self._cache

    @property
    def X(self) -> Any:
        return self._materialise()[0]

    @property
    def y(self) -> np.ndarray:
        return self._materialise()[1]

    @property
    def ts(self) -> np.ndarray:
        return np.concatenate([self._initial_ts, *self._parts_ts])

    @property
    def arrived_row_id(self) -> np.ndarray:
        if not self._parts_row_id:
            return np.empty(0, dtype=np.int64)
        return np.concatenate(self._parts_row_id)

    @property
    def arrived_queried_in(self) -> np.ndarray:
        if not self._parts_queried_in:
            return np.empty(0, dtype=np.int64)
        return np.concatenate(self._parts_queried_in)

    @property
    def row_id(self) -> np.ndarray:
        """Initial and arrived row ids (for the seen-before mask, which only metrics use)."""
        return np.concatenate([self._initial_row_id, self.arrived_row_id])
