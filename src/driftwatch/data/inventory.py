"""`driftwatch data inventory`: measured facts that fix the slot design (Phase 2).

Everything here is computed from the caches and the manifest, never typed in by hand:
- row counts and class balance per base unit;
- timestamp type and granularity;
- feature count, density, disk size and build memory;
- missing values and family counts;
- per-slot occupancy with gate pass/fail for each candidate slot length;
- duplicate feature vectors seen in more than one slot.

Output: reports/data_inventory.md, reports/tables/data_*.csv and reports/figures/data_*.png.
The CSV files are the table view of every figure.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from driftwatch.data.cache import Layout, load_manifest
from driftwatch.data.slots import SLOT_LENGTHS, build_slots, unit_start

log = logging.getLogger(__name__)

GATE_M = (30, 50, 100)  # malware per slot after C3 subsampling to 10% (needs 9M benign)
# A date-only timestamp shared by at least this many rows is treated as a placeholder
# (BODMAS: 5,877 benign rows at 2020-01-01 00:00:00); reported, never dropped here.
PLACEHOLDER_TIE = 100
C3_RATIO = 0.10
BENIGN_COLOR, MALWARE_COLOR = "#2a78d6", "#eb6834"  # dataviz categorical slots 1-2, validated
INK, MUTED, SURFACE = "#1f1f1e", "#6b6a63", "#fcfcfb"
GATE_TEXT = (
    "A slot passes gate M when it holds at least M malware and 9M benign, so that C3 "
    f"subsampling to {C3_RATIO:.0%} malware keeps M malware. Gap slots hold no rows; "
    '"longest passing run" counts consecutive passing slots (gaps break a run).'
)
META_COLS = ["row_id", "sha256", "ts", "label", "family", "fv_hash"]


@dataclass
class DatasetFacts:
    name: str
    manifest: dict[str, Any]
    rows: pd.DataFrame  # one row per sample: unit, ts, label, family, sha256, fv_hash
    units: pd.DataFrame  # one row per base unit


def _load(layout: Layout, name: str) -> DatasetFacts:
    manifest = load_manifest(layout.manifest)["datasets"][name]
    cache = manifest["cache"]
    extra = ["added", "year_month", "src_split", "ts_source"]
    if name == "bodmas":
        extra = ["category", "ts_naive", "ts_date_only", "ts_tie_count"]
    cols = META_COLS + extra
    parts = []
    for unit in sorted(cache["units"], key=unit_start):
        t = pq.read_table(layout.unit_dir(name, unit) / "meta.parquet", columns=cols).to_pandas()
        t["unit"] = unit
        parts.append(t)
    rows = pd.concat(parts, ignore_index=True)
    rows["placeholder"] = (
        rows["ts_date_only"] & (rows["ts_tie_count"] >= PLACEHOLDER_TIE)
        if name == "bodmas"
        else False
    )
    placeholder_benign = rows[rows["placeholder"] & (rows["label"] == 0)].groupby("unit").size()
    n_feat = cache["n_features"]
    units = pd.DataFrame(
        [
            {
                "unit": u,
                "start": e["start"][:10],
                "n_rows": e["n_rows"],
                "n_malware": e["n_malware"],
                "n_benign": e["n_rows"] - e["n_malware"],
                "malware_share": round(e["n_malware"] / e["n_rows"], 4) if e["n_rows"] else 0,
                "density": round(e.get("nnz", e.get("nonzero", 0)) / (e["n_rows"] * n_feat), 6),
                "n_benign_placeholder_ts": int(placeholder_benign.get(u, 0)),
            }
            for u, e in sorted(cache["units"].items(), key=lambda kv: unit_start(kv[0]))
        ]
    )
    return DatasetFacts(name, manifest, rows, units)


# --- slots and gates -----------------------------------------------------------------------


def slot_table(facts: DatasetFacts, length: str) -> pd.DataFrame:
    by_unit = facts.units.set_index("unit")
    slots = build_slots(facts.name, length, list(by_unit.index))
    out = []
    for s in slots:
        n_mal = int(by_unit.loc[list(s.units), "n_malware"].sum()) if s.units else 0
        n_all = int(by_unit.loc[list(s.units), "n_rows"].sum()) if s.units else 0
        n_ben = n_all - n_mal
        n_ph = int(by_unit.loc[list(s.units), "n_benign_placeholder_ts"].sum()) if s.units else 0
        row = {
            "slot": s.slot_id,
            "index": s.index,
            "start": s.start.date().isoformat(),
            "end": s.end.date().isoformat(),
            "gap": s.is_gap,
            "partial": s.is_partial,  # some base units of the slot are empty
            "missing_units": " ".join(s.missing_units) if s.is_partial else "",
            "edge": s.index in (0, len(slots) - 1),
            "n_rows": n_all,
            "n_malware": n_mal,
            "n_benign": n_ben,
            "c3_malware_kept": min(n_mal, int(n_ben * C3_RATIO / (1 - C3_RATIO))),
        }
        for m in GATE_M:  # a partly empty slot fails: its window is not the stated one (C2)
            row[f"pass_M{m}"] = bool(n_mal >= m and n_ben >= 9 * m and not s.is_partial)
        if facts.name == "bodmas":
            row["n_benign_placeholder_ts"] = n_ph
            ok = n_mal >= 50 and n_ben - n_ph >= 450 and not s.is_partial
            row["pass_M50_without_placeholder_ts"] = bool(ok)
        out.append(row)
    return pd.DataFrame(out)


def longest_run(passing: Iterable[bool], table: pd.DataFrame) -> tuple[int, str, str]:
    best, cur, best_end = 0, 0, -1
    for i, ok in enumerate(passing):
        cur = cur + 1 if ok else 0
        if cur > best:
            best, best_end = cur, i
    if best == 0:
        return 0, "", ""
    return best, table["start"].iat[best_end - best + 1], table["end"].iat[best_end]


def gate_summary(facts: DatasetFacts, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    out = []
    for length, t in tables.items():
        filled = t[~t["gap"]]
        for m in GATE_M:
            run, start, end = longest_run(t[f"pass_M{m}"], t)
            out.append(
                {
                    "dataset": facts.name,
                    "slot_length": length,
                    "slots_in_span": len(t),
                    "gap_slots": int(t["gap"].sum()),
                    "non_empty_slots": len(filled),
                    "M": m,
                    "passing_slots": int(t[f"pass_M{m}"].sum()),
                    "longest_passing_run": run,
                    "run_start": start,
                    "run_end": end,
                }
            )
    return pd.DataFrame(out)


# --- duplicates ----------------------------------------------------------------------------


def duplicate_tables(facts: DatasetFacts, tables: dict[str, pd.DataFrame]):
    rows = facts.rows
    fv = rows["fv_hash"].to_numpy(dtype="S32")
    uniq, inv = np.unique(fv, return_inverse=True)
    labels = rows["label"].to_numpy()
    lab_min = np.full(len(uniq), 9, dtype=np.int8)
    lab_max = np.full(len(uniq), -1, dtype=np.int8)
    np.minimum.at(lab_min, inv, labels)
    np.maximum.at(lab_max, inv, labels)
    counts = np.bincount(inv)
    summary: dict[str, Any] = {
        "dataset": facts.name,
        "rows": len(rows),
        "distinct_vectors": len(uniq),
        "rows_sharing_a_vector": int((counts[inv] > 1).sum()),
        "vectors_with_both_labels": int((lab_min != lab_max).sum()),
        "rows_in_label_conflicting_vectors": int((lab_min != lab_max)[inv].sum()),
        "sha256_duplicate_rows": int(rows["sha256"].duplicated(keep=False).sum()),
        "sha256_in_several_units": facts.manifest["cache"]["cross_unit_sha256"],
    }
    per_slot = []
    for length, t in tables.items():
        unit_to_slot = {}
        for s in build_slots(facts.name, length, list(facts.units["unit"])):
            unit_to_slot.update({u: s.index for u in s.units})
        slot_of_row = rows["unit"].map(unit_to_slot).to_numpy()
        first = np.full(len(uniq), np.iinfo(np.int64).max)
        last = np.full(len(uniq), -1)
        np.minimum.at(first, inv, slot_of_row)
        np.maximum.at(last, inv, slot_of_row)
        seen_earlier = slot_of_row > first[inv]
        summary[f"vectors_in_several_slots_{length}"] = int((first != last).sum())
        summary[f"rows_seen_in_earlier_slot_{length}"] = int(seen_earlier.sum())
        df = pd.DataFrame({"slot_index": slot_of_row, "seen_earlier": seen_earlier})
        agg = df.groupby("slot_index")["seen_earlier"].agg(["sum", "size"]).reset_index()
        agg = agg.merge(t[["index", "slot", "start"]], left_on="slot_index", right_on="index")
        agg["share_seen_earlier"] = (agg["sum"] / agg["size"]).round(4)
        per_slot.append(
            agg.rename(columns={"sum": "rows_seen_earlier", "size": "n_rows"}).assign(
                dataset=facts.name, slot_length=length
            )[
                ["dataset", "slot_length", "slot", "start", "n_rows", "rows_seen_earlier"]
                + ["share_seen_earlier"]
            ]
        )
    return summary, pd.concat(per_slot, ignore_index=True)


# --- timestamps, families, missing values ---------------------------------------------------


def timestamp_facts(facts: DatasetFacts) -> dict[str, Any]:
    ts = pd.to_datetime(facts.rows["ts"], utc=True)
    out: dict[str, Any] = {
        "min": ts.min().isoformat(),
        "max": ts.max().isoformat(),
        "share_with_time_of_day": round(float((ts != ts.dt.normalize()).mean()), 4),
        "distinct_days": int(ts.dt.normalize().nunique()),
    }
    labels = facts.rows["label"]
    for lab, name in ((1, "malware"), (0, "benign")):
        sub = ts[labels == lab]
        if len(sub):
            out[f"{name}_min"] = sub.min().isoformat()
            out[f"{name}_max"] = sub.max().isoformat()
            out[f"{name}_p01"] = sub.quantile(0.01).isoformat()
            out[f"{name}_share_at_midnight"] = round(float((sub == sub.dt.normalize()).mean()), 4)
            mode = sub.value_counts().head(1)
            out[f"{name}_most_common_ts"] = f"{mode.index[0].isoformat()} x {int(mode.iloc[0])}"
    if facts.name == "lamda":
        added = pd.to_datetime(facts.rows["added"], utc=True)
        out["share_ts_equals_added"] = round(float((added == ts).mean()), 6)
        out["rows_without_added"] = int(added.isna().sum())
        out["rows_ts_from_month_start"] = int((facts.rows["ts_source"] != "added").sum())
    else:
        rows = facts.rows
        for lab, name in ((1, "malware"), (0, "benign")):
            sub = rows[rows["label"] == lab]
            out[f"{name}_placeholder_ts_rows"] = int(sub["placeholder"].sum())
            out[f"{name}_ts_without_offset"] = int(sub["ts_naive"].sum())
        out["placeholder_rule"] = f"date-only timestamp shared by >= {PLACEHOLDER_TIE} rows"
    return out


def family_table(facts: DatasetFacts, top: int = 20) -> tuple[pd.DataFrame, dict[str, int]]:
    mal = facts.rows[facts.rows["label"] == 1]
    fam = mal["family"].fillna("<missing>")
    singleton = fam.str.startswith("singleton:")  # AVClass2 label for an unclustered sample
    counts = Counter(fam[~singleton])
    table = pd.DataFrame(counts.most_common(top), columns=["family", "n_malware"])
    named = [f for f in counts if f != "<missing>"]
    info = {
        "named_families": len(named),
        "named_families_with_10_or_more": sum(1 for f in named if counts[f] >= 10),
        "malware_singleton_labels": int(singleton.sum()),
        "malware_without_family": counts.get("<missing>", 0),
        "malware_in_top_10_families": sum(c for _, c in counts.most_common(10)),
    }
    return table, info


def identifier_facts(facts: DatasetFacts) -> dict[str, Any]:
    sha = facts.rows["sha256"]
    bad = ~sha.str.fullmatch(r"[0-9a-f]{64}")
    prefixes = Counter(s.split("_")[0] for s in sha[bad])
    return {
        "ids_not_sha256": int(bad.sum()),
        "their_prefixes": dict(prefixes),
        "their_labels": dict(Counter(facts.rows.loc[bad, "label"].astype(int))),
    }


def year_table(facts: DatasetFacts) -> pd.DataFrame:
    ts = pd.to_datetime(facts.rows["ts"], utc=True)
    t = pd.crosstab(ts.dt.year, facts.rows["label"]).rename(columns={0: "benign", 1: "malware"})
    return t.reset_index().rename(columns={"ts": "year"})


def build_stats(facts: DatasetFacts) -> dict[str, Any]:
    cache = facts.manifest["cache"]
    if facts.name == "lamda":
        totals: Counter[str] = Counter()
        excluded: Counter[str] = Counter()
        for chunk in cache["chunks"].values():
            for k, v in chunk["stats"].items():
                if k == "excluded":
                    excluded.update(v)
                elif isinstance(v, int | float):
                    totals[k] += v
        stats = dict(totals)
        stats["excluded"] = dict(excluded)
        stats["metadata_csv_duplicate_sha256"] = cache.get("metadata_csv_duplicate_sha256")
        return stats
    return {k: v for k, v in cache["stats"].items() if k != "extra"}


# --- figures --------------------------------------------------------------------------------


def _axes_style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)


def plot_counts(base: pd.DataFrame, title: str, path: Path, width_days: float) -> None:
    """Stacked counts and malware share per base-unit slot; lines break at gap slots."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = pd.to_datetime(base["start"])
    share = (base["n_malware"] / base["n_rows"]).where(~base["gap"])
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(10, 5.2), sharex=True, gridspec_kw={"height_ratios": [3, 1.3]}
    )
    fig.patch.set_facecolor(SURFACE)
    kw = {"width": width_days, "align": "edge", "edgecolor": SURFACE, "linewidth": 0.8}
    ax1.bar(x, base["n_benign"], color=BENIGN_COLOR, label="benign", **kw)
    ax1.bar(
        x, base["n_malware"], bottom=base["n_benign"], color=MALWARE_COLOR, label="malware", **kw
    )
    ax1.set_ylabel("samples per slot", color=INK, fontsize=9)
    ax1.legend(frameon=False, fontsize=8, loc="upper right", labelcolor=INK)
    ax1.set_title(title, loc="left", color=INK, fontsize=11)
    ax2.plot(x, share, color=MALWARE_COLOR, linewidth=2, marker="o", markersize=3)
    ax2.axhline(C3_RATIO, color=MUTED, linewidth=1, linestyle="--")
    ax2.annotate("C3 target 10%", (x.iloc[0], C3_RATIO), color=MUTED, fontsize=7, va="bottom")
    ax2.set_ylabel("malware share", color=INK, fontsize=9)
    ax2.set_ylim(0, 1)
    for ax in (ax1, ax2):
        _axes_style(ax)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)


def plot_duplicates(base: pd.DataFrame, per_slot: pd.DataFrame, title: str, path: Path) -> None:
    """Share of each base-unit slot whose feature vector appeared in an earlier slot."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = base[["slot", "start", "gap"]].merge(
        per_slot[["slot", "share_seen_earlier"]], on="slot", how="left"
    )
    fig, ax = plt.subplots(figsize=(10, 2.8))
    fig.patch.set_facecolor(SURFACE)
    ax.plot(pd.to_datetime(d["start"]), d["share_seen_earlier"], color=INK, linewidth=2)
    ax.set_ylim(0, 1)
    ax.set_ylabel("share of slot", color=INK, fontsize=9)
    ax.set_title(title, loc="left", color=INK, fontsize=10)
    _axes_style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor=SURFACE)
    plt.close(fig)


# --- report ---------------------------------------------------------------------------------


def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def _kv(d: dict[str, Any]) -> str:
    return _md(pd.DataFrame({"item": list(d), "value": [str(v) for v in d.values()]}))


def _gb(n: int | float | None) -> str:
    return "n/a" if n is None else f"{n / 1024**3:.2f} GB"


def _mb(n: int | float) -> str:
    return f"{n / 1024**2:.1f} MB"


def dataset_section(facts: DatasetFacts, out: Path) -> tuple[str, dict[str, Any]]:
    name = facts.name
    tables = {length: slot_table(facts, length) for length in SLOT_LENGTHS[name]}
    for length, t in tables.items():
        t.to_csv(
            out / "tables" / f"data_{name}_slots_{length}.csv", index=False, lineterminator="\n"
        )
    facts.units.to_csv(out / "tables" / f"data_{name}_units.csv", index=False, lineterminator="\n")
    gates = gate_summary(facts, tables)
    dup_summary, dup_per_slot = duplicate_tables(facts, tables)
    dup_per_slot.to_csv(
        out / "tables" / f"data_{name}_duplicates_per_slot.csv", index=False, lineterminator="\n"
    )
    families, fam_info = family_table(facts)
    families.to_csv(
        out / "tables" / f"data_{name}_families_top20.csv", index=False, lineterminator="\n"
    )
    ts = timestamp_facts(facts)
    ids = identifier_facts(facts)
    years = year_table(facts)
    years.to_csv(out / "tables" / f"data_{name}_years.csv", index=False, lineterminator="\n")
    stats = build_stats(facts)
    cache, source = facts.manifest["cache"], facts.manifest["source"]
    build = facts.manifest["builds"][-1]
    mem = build["memory"]
    n, f = int(cache["n_rows"]), int(cache["n_features"])
    nnz = sum(u.get("nnz", u.get("nonzero", 0)) for u in cache["units"].values())
    base_len = SLOT_LENGTHS[name][0]
    base = tables[base_len]
    if name == "bodmas":  # plot the dense period; earlier rows are counted in the year table
        base = base[base["start"] >= base.loc[base["n_malware"] > 0, "start"].min()]
    plot_counts(
        base,
        f"{name.upper()}: samples per {cache['base_unit']} (benign and malware)",
        out / "figures" / f"data_{name}_counts.png",
        27 if name == "lamda" else 6,
    )
    dup_base = dup_per_slot[dup_per_slot["slot_length"] == base_len]
    dup_fig = ""
    if dup_summary[f"rows_seen_in_earlier_slot_{base_len}"] > 0.001 * n:
        plot_duplicates(
            base,
            dup_base,
            f"{name.upper()}: share of each {cache['base_unit']} whose feature vector "
            "already appeared in an earlier slot",
            out / "figures" / f"data_{name}_duplicates.png",
        )
        dup_fig = f"![{name} duplicates](figures/data_{name}_duplicates.png)\n\n"
    overview = {
        "source": source.get("repo_id") or source.get("url"),
        "version": source.get("revision") or source.get("file_ids"),
        "rows": n,
        "malware": int(cache["n_malware"]),
        "benign": n - int(cache["n_malware"]),
        "malware share": f"{cache['n_malware'] / n:.4f}",
        "features": f,
        "feature dtype": cache["feature_dtype"],
        "density (non-zero share)": f"{nnz / (n * f):.5f}",
        "base unit": cache["base_unit"],
        "populated base units": len(cache["units"]),
        "timestamp used": cache["timestamp"],
        "raw size on disk": _mb(build["raw_bytes"]),
        "cache size on disk": _mb(build["cache_bytes"]),
        "build peak memory": f"{_gb(mem['peak_bytes'])} (cap {_gb(mem['cap_bytes'])})",
        "build wall-clock": f"{mem['wall_s']:.1f} s",
        "build code version": build["code_version"],
    }
    slot_links = ", ".join(f"[{k}](tables/data_{name}_slots_{k}.csv)" for k in tables)
    gate_cols = ["slot_length", "slots_in_span", "gap_slots", "non_empty_slots", "M"]
    gate_cols += ["passing_slots", "longest_passing_run", "run_start", "run_end"]
    text = f"""## {name.upper()}

![{name} counts](figures/data_{name}_counts.png)

Table view: [units](tables/data_{name}_units.csv); slots: {slot_links}.

### Overview
{_kv(overview)}

### Timestamps
{_kv(ts)}

Rows per year and class ([csv](tables/data_{name}_years.csv)):

{_md(years)}

### Identifiers
{_kv(ids)}

### Slot occupancy and minimum-size gate
{GATE_TEXT}

{_md(gates[gate_cols])}

### Duplicates
{dup_fig}{_kv(dup_summary)}

Per-slot table: [duplicates per slot](tables/data_{name}_duplicates_per_slot.csv).

### Families (malware)
{_kv(fam_info)}

Top 20: [families](tables/data_{name}_families_top20.csv).

### Missing values and consistency checks (from the build)
{_kv(stats)}
"""
    key = {
        "overview": overview,
        "timestamps": ts,
        "identifiers": ids,
        "years": years,
        "gates": gates,
        "duplicates": dup_summary,
        "families": fam_info,
        "stats": stats,
        "dup_per_slot": dup_per_slot,
    }
    return text, key


def write_inventory(layout: Layout, datasets: Iterable[str], out: Path) -> Path:
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(layout.manifest)
    sections = []
    for name in datasets:
        if name not in manifest["datasets"]:
            log.warning("%s not built; skipped", name)
            continue
        log.info("inventory %s", name)
        text, _ = dataset_section(_load(layout, name), out)
        sections.append(text)
    header = (
        "# Data inventory (Phase 2)\n\n"
        "Generated by `uv run driftwatch data inventory` from `data/manifest.json` "
        f"(content hash `{manifest.get('content_hash', '')}`) and the per-unit caches. "
        "Do not edit by hand: regenerate. Interpretation, decisions and open questions are in "
        "[data_inventory_notes.md](data_inventory_notes.md) and ADR-0004.\n"
    )
    path = out / "data_inventory.md"
    path.write_bytes((header + "\n" + "\n".join(sections)).encode("utf-8"))
    log.info("wrote %s", path)
    return path
