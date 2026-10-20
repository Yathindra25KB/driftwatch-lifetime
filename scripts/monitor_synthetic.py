"""Synthetic acceptance checks of the four monitors (code behaviour; never evidence).

    uv run python scripts/monitor_synthetic.py

For each monitor, on seeded synthetic streams (``data.synthetic.change_point_stream``):

- **change point**: an abrupt covariate shift at evaluation slot 4 of 8; reports the first
  alarm at or after the shift (detection delay) and alarms before it, over 5 stream seeds;
- **no drift**: 8 streams of 100 evaluation slots from one distribution, each with its own
  reference draw; reports the pooled alarm rate against the nominal alpha (0.01) and the
  highest rate of a single reference draw (a fixed reference makes alarms within a stream
  dependent, so the rate given one reference can sit above or below alpha).

The monitor is driven as the runner drives it: start on the initial window, reference = the
time-ordered hold-out (features only), calibration rows = the hold-out (features only), one
update per slot. Writes ``reports/tables/e4_synthetic_checks.csv``. Synthetic numbers are
never evidence (CLAUDE.md rule 8); they show the monitors behave as specified.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from driftwatch.data.synthetic import change_point_stream  # noqa: E402
from driftwatch.monitors import MONITORS, SlotView, make_monitor  # noqa: E402
from driftwatch.monitors.base import (  # noqa: E402
    ALPHA,
    INITIAL_REF,
    MonitorState,
    reference_sample,
)

N_TRAIN = 3
QUIET_STREAMS, QUIET_SLOTS = 8, 100  # 8 reference draws x 100 no-drift slots


def alarms(name: str, stream, seed: int = 0) -> list[bool]:
    X = np.vstack([x for x, _ in stream[:N_TRAIN]])
    y = np.concatenate([t for _, t in stream[:N_TRAIN]])
    cut = int(0.8 * len(y))
    model = LogisticRegression(max_iter=1000).fit(X[:cut], y[:cut])
    mon = make_monitor(name)
    st = MonitorState(seed=seed, window_key="synthetic")
    st.reset_reference(reference_sample(X[cut:], seed, "synthetic", INITIAL_REF), INITIAL_REF)
    mon.start(st, X[:cut], y[:cut], X[cut:])
    cal_p = model.predict_proba(X[cut:])[:, 1]
    out = []
    for s, (Xs, _) in enumerate(stream[N_TRAIN:]):
        view = SlotView(s, f"slot{s}", Xs, proba=model.predict_proba(Xs)[:, 1],
                        ref_proba=model.predict_proba(st.ref_X)[:, 1], cal_X=X[cut:],
                        cal_proba=cal_p)  # fmt: skip
        out.append(mon.update(view, st).fired)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "tables")
    args = ap.parse_args(argv)
    rows = []
    change, n_eval = 4, 8
    for name in MONITORS:
        delays, early = [], 0
        for seed in range(5):
            stream = change_point_stream(n_slots=N_TRAIN + n_eval, change_at=N_TRAIN + change,
                                         rows_per_slot=700, shift=1.0, seed=100 + seed)  # fmt: skip
            a = alarms(name, stream, seed)
            early += sum(a[:change])
            after = [s for s in range(change, n_eval) if a[s]]
            delays.append(after[0] - change if after else None)
        per_ref = [  # one reference draw per stream; the rate is conditional on it
            sum(alarms(name, change_point_stream(n_slots=N_TRAIN + QUIET_SLOTS, change_at=None,
                                                 rows_per_slot=700, seed=200 + sd), sd))
            for sd in range(QUIET_STREAMS)
        ]  # fmt: skip
        detected = [d for d in delays if d is not None]
        rows.append(
            {
                "monitor": name, "alpha": ALPHA,
                "change_streams": len(delays), "change_detected": len(detected),
                "change_delay_max": max(detected) if detected else None,
                "change_delay_mean": float(np.mean(detected)) if detected else None,
                "alarms_before_change": early, "slots_before_change": change * len(delays),
                "no_drift_streams": QUIET_STREAMS, "no_drift_slots": QUIET_STREAMS * QUIET_SLOTS,
                "no_drift_alarms": int(sum(per_ref)),
                "no_drift_rate": sum(per_ref) / (QUIET_STREAMS * QUIET_SLOTS),
                "no_drift_rate_max_per_reference": max(per_ref) / QUIET_SLOTS,
            }
        )  # fmt: skip
    df = pd.DataFrame(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out / "e4_synthetic_checks.csv", index=False, float_format="%.4f",
              lineterminator="\n")  # fmt: skip
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
