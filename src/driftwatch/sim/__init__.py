"""Run harness and simulator: configuration, result store, runners, grids and reproduction.

The label queue (``queue.py``) is the only place a label delay lives; selectors, policies and
the pool see handles, never held-back labels. ``runner`` runs the E0 baseline and the
delay/budget simulation, ``runner_e3`` adds conformal selection and (with ``monitoring``)
monitor-triggered retraining for E4, the ``grid*`` modules run the pre-registered grids by
cell, and ``reproduce`` rebuilds Table 1.
"""
