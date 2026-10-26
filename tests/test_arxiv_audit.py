"""scripts/arxiv_audit.py: query, Atom parsing, topic filter and report (no network)."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


aa = load_script("arxiv_audit")


def entry(arxiv_id: str, title: str, abstract: str, published: str) -> str:
    return f"""<entry>
  <id>http://arxiv.org/abs/{arxiv_id}</id>
  <published>{published}T12:00:00Z</published>
  <title>{title}</title>
  <summary>{abstract}</summary>
  <author><name>A. Author</name></author>
  <category term="cs.CR"/>
</entry>"""


def feed(*entries: str) -> bytes:
    return (
        '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
        + "".join(entries)
        + "</feed>"
    ).encode()


FEED = feed(
    entry(
        "2611.00001v1", "Delayed labels in\n  Android malware", "Label delay matters.", "2026-11-02"
    ),
    entry(
        "2611.00002v1",
        "Conformal drift for images",
        "Concept drift and active learning.",
        "2026-11-01",
    ),
    entry("2611.00003v1", "Diffusion models", "Nothing related.", "2026-10-30"),
    entry("2609.00004v1", "Old malware drift", "Concept drift in malware.", "2026-09-01"),
)


def test_query_names_both_categories_and_topic_phrases() -> None:
    q = urllib.parse.unquote_plus(aa.query_url(0))
    assert "cat:cs.CR OR cat:cs.LG" in q
    assert 'abs:"label delay"' in q and 'abs:"conformal"' in q
    assert "sortBy=submittedDate" in aa.query_url(0)


def test_parse_normalises_whitespace_and_ids() -> None:
    papers = aa.parse(FEED)
    assert papers[0]["id"] == "2611.00001v1"
    assert papers[0]["title"] == "Delayed labels in Android malware"
    assert papers[0]["published"] == "2026-11-02"


def test_classify_needs_domain_or_two_topics() -> None:
    p = aa.parse(FEED)
    assert aa.classify(p[0]) == ["label delay"]  # one topic plus malware
    assert set(aa.classify(p[1])) == {"analyst budget", "conformal / drift monitoring"}
    assert aa.classify(p[2]) == []


def test_collect_stops_at_the_since_date(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(aa.time, "sleep", lambda s: None)

    def fetch(url: str) -> bytes:
        calls.append(url)
        return FEED

    found = aa.collect(dt.date(2026, 10, 1), fetch)
    assert [p["id"] for p in found] == ["2611.00001v1", "2611.00002v1"]
    assert len(calls) == 1  # the page reaches back past the since date


def test_main_writes_report_json_and_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(aa, "fetch_url", lambda url: FEED)
    monkeypatch.setattr(aa.time, "sleep", lambda s: None)
    assert aa.main(["--since", "2026-10-01", "--out", str(tmp_path)]) == 0
    reports = list(tmp_path.glob("*.md"))
    assert len(reports) == 1
    text = reports[0].read_text("utf-8")
    assert "2 candidates" in text and "https://arxiv.org/abs/2611.00001v1" in text
    assert (tmp_path / "state.json").exists()
