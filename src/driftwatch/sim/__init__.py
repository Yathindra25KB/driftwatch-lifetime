"""Run harness (Phase 4: config, result store, E0 runner) and simulator (Phase 5).

Phase 4 holds only the never-retrain baseline runner. The label queue, selectors and
policies arrive in Phase 5; the label queue is the only place a delay will live
(``sim/queue.py``).
"""
