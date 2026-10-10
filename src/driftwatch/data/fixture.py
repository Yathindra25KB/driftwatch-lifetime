"""Synthetic fixture with the LAMDA and BODMAS raw-file schemas, for tests and CI.

The values are random, but the column names, dtypes and file layout match the real data.
No real dataset content is used, and fixture numbers are never evidence. LAMDA keeps the
real feature names and dtypes, but its width is cut from 4,561 to 64 so the fixture stays
under 1 MB; the builder reads the width from the files.

Planted cases the tests rely on:
- LAMDA has no 2015 (a gap), an undersized month (2013-02), a feature vector repeated across
  months and years, one sha256 in both train and test, an `added` date outside its
  year_month, and one app missing from metadata.csv.
- BODMAS has old benign timestamps (2007, 2018) before the dense 2019 period, an empty ISO
  week, a feature vector repeated across weeks, and one malware row without a category.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

LAMDA_FEATURES = 64
BODMAS_FEATURES = 2381
FIXTURE_REVISION = "f1x7ure00000" + "0" * 28
LAMDA_MONTHS = {2013: (1, 2, 6), 2014: (3, 11), 2016: (1, 7)}
LAMDA_ROWS = {(2013, 2): 3}  # undersized month
LAMDA_DEFAULT_ROWS = 14
FAMILIES = ("dowgin", "airpush", "kuguo")


def _sha(rng: np.random.Generator) -> str:
    return rng.bytes(32).hex()


def _lamda_rows(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for year, months in LAMDA_MONTHS.items():
        for month in months:
            for _ in range(LAMDA_ROWS.get((year, month), LAMDA_DEFAULT_ROWS)):
                malware = rng.random() < 0.4
                start = datetime(year, month, 1, tzinfo=UTC)
                rows.append(
                    {
                        "hash": _sha(rng),
                        "label": int(malware),
                        "family": str(rng.choice(FAMILIES)) if malware else "benign",
                        "vt_count": float(rng.integers(4, 39)) if malware else 0.0,
                        "year_month": f"{year:04d}-{month:02d}",
                        "added": start + timedelta(seconds=int(rng.integers(0, 27 * 86400))),
                        "year": year,
                    }
                )
    df = pd.DataFrame(rows)
    feats = (rng.random((len(df), LAMDA_FEATURES)) < 0.12).astype(np.int8)
    feats[df.index[df.year_month == "2013-06"][0]] = feats[0]  # dup across months
    feats[df.index[df.year_month == "2014-03"][0]] = feats[0]  # dup across years
    feat_df = pd.DataFrame(feats, columns=[f"feat_{i}" for i in range(LAMDA_FEATURES)])
    return pd.concat([df, feat_df], axis=1)


def _write_lamda(root: Path, rng: np.random.Generator) -> None:
    snap = root / "raw" / "lamda" / FIXTURE_REVISION[:12]
    df = _lamda_rows(rng)
    df.loc[df.index[-1], "hash"] = df.loc[df.index[-2], "hash"]  # same app in train and test
    split = np.where(rng.random(len(df)) < 0.8, "train", "test")
    split[-2], split[-1] = "train", "test"
    columns = ["hash", "label", "family", "vt_count", "year_month"]
    columns += [f"feat_{i}" for i in range(LAMDA_FEATURES)]
    for year in LAMDA_MONTHS:
        for name in ("train", "test"):
            part = df[(df.year == year) & (split == name)][columns].reset_index(drop=True)
            path = snap / "Baseline" / str(year) / f"{year}_{name}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(pa.Table.from_pandas(part, preserve_index=False), path)
    mapping = pd.DataFrame(
        {
            "feature_name": [f"Synthetic_.token{i}" for i in range(LAMDA_FEATURES)],
            "mapped_name": [f"feat_{i}" for i in range(LAMDA_FEATURES)],
        }
    )
    mapping.to_csv(snap / "Baseline" / "feature_mapping.csv", index=False)
    meta = df.drop_duplicates("hash").iloc[:-1].copy()  # last app missing from metadata.csv
    shifted = meta.index[meta.year_month == "2016-07"][0]
    meta.loc[shifted, "added"] = datetime(2016, 6, 30, 23, 0, tzinfo=UTC)  # outside year_month
    out = pd.DataFrame(
        {
            "sha256": meta["hash"],
            "vt_detection": meta["vt_count"],
            "added": meta["added"].dt.strftime("%Y-%m-%d %H:%M:%S"),
            "label": meta["label"].astype(float),
            "year": meta["year"],
            "year_month": meta["year_month"],
            "family": meta["family"],
        }
    )
    out.to_csv(snap / "metadata.csv", index=False)
    (snap / "README.md").write_text("Synthetic LAMDA-schema fixture. Not real data.\n")
    source = {"dataset": "lamda", "revision": FIXTURE_REVISION, "fixture": True}
    (snap / "SOURCE.json").write_text(json.dumps(source, indent=2, sort_keys=True) + "\n")


def _bodmas_times(rng: np.random.Generator) -> list[datetime]:
    times = [datetime(2007, 1, 1, 8, 46, tzinfo=UTC), datetime(2018, 5, 3, 12, 0, tzinfo=UTC)]
    start = datetime(2019, 8, 26, tzinfo=UTC)  # Monday of ISO week 2019-W35
    for week in (0, 1, 3, 4, 5):  # week 2 (2019-W37) is left empty
        for _ in range(12 if week != 5 else 2):
            offset = timedelta(weeks=week, seconds=int(rng.integers(0, 7 * 86400)))
            times.append(start + offset)
    return sorted(times)


def _write_bodmas(root: Path, rng: np.random.Generator) -> None:
    raw = root / "raw" / "bodmas"
    raw.mkdir(parents=True, exist_ok=True)
    times = _bodmas_times(rng)
    n = len(times)
    y = (rng.random(n) < 0.45).astype(np.int32)
    y[:2] = 0  # the old timestamps are benign, as in the real file
    X = np.zeros((n, BODMAS_FEATURES), dtype=np.float32)
    mask = rng.random(X.shape) < 0.02
    X[mask] = rng.integers(1, 200, mask.sum()).astype(np.float32)
    X[n - 1] = X[5]  # dup across weeks
    shas = [_sha(rng) for _ in range(n)]
    families = [str(rng.choice(("sfone", "wacatac", "upatre"))) if v else "" for v in y]
    meta = pd.DataFrame(
        {"sha": shas, "timestamp": [t.isoformat(sep=" ") for t in times], "family": families}
    )
    meta.to_csv(raw / "bodmas_metadata.csv", index=False)
    malware = [s for s, v in zip(shas, y, strict=True) if v]
    cats = pd.DataFrame({"sha256": malware[1:], "category": "trojan"})  # first lacks a category
    cats.to_csv(raw / "bodmas_malware_category.csv", index=False)
    with zipfile.ZipFile(raw / "bodmas.npz", "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, arr in (("X.npy", X), ("y.npy", y)):
            buf = io.BytesIO()
            np.lib.format.write_array(buf, arr, allow_pickle=False)
            zf.writestr(name, buf.getvalue())
    source = {"dataset": "bodmas", "method": "fixture", "fixture": True}
    (raw / "SOURCE.json").write_text(json.dumps(source, indent=2, sort_keys=True) + "\n")


def write_fixture(root: Path, seed: int = 20261010) -> Path:
    """Write the synthetic raw files under ``root/raw/``; returns ``root``."""
    rng = np.random.default_rng(seed)
    _write_lamda(root, rng)
    _write_bodmas(root, rng)
    return root
