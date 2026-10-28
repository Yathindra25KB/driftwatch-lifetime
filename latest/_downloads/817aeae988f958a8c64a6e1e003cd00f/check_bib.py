"""Check every bibliography entry against Crossref or arXiv by identifier.

    uv run python scripts/check_bib.py                         # paper/references.bib, live
    uv run python scripts/check_bib.py --cache .cache/bib      # keep responses between runs
    uv run python scripts/check_bib.py --cited report/*.md     # also check the keys the text cites

For each entry the script fetches the record named by its ``doi`` (Crossref) or ``eprint``
(arXiv) and compares title, year and authors with what the entry says. It exits non-zero when
any entry is unresolved or mismatched, and lists each problem. No entry is ever repaired or
invented by this script; a mismatch is for a person to read.

Rules (Phase 11):

- **Identifier.** An entry with neither ``doi`` nor ``eprint`` is unresolved.
- **Title.** Normalised (case, braces, LaTeX, punctuation, accents) and compared with a
  similarity ratio of at least 0.92 (a subtitle or a hyphen may differ between versions).
- **Authors.** The first author's surname must match, and so must the number of authors.
- **Year.** For Crossref the entry's year must equal the record's year. For arXiv it must not
  precede the first version and must not follow the latest version by more than one year: a
  paper published in a venue after its preprint carries the venue year (this is noted, not
  checked against the proceedings, which have no identifier here).
- **Cited keys.** With ``--cited``, every key-shaped token in the given files that is not in
  the bibliography is reported (keys look like ``pendlebury2019tesseract``).

Network access is one batched arXiv request and one Crossref request per DOI, with a pause
between hosts. Tests inject the fetch function and need no network.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "driftwatch-check-bib/0.1 (research software; bibliography check)"
TITLE_RATIO = 0.92
ATOM = {"a": "http://www.w3.org/2005/Atom"}
KEY_RE = re.compile(r"\b([a-z][a-z-]*\d{4}[a-z][a-z0-9]*)\b")

Fetch = Callable[[str], str]


# --- parsing ------------------------------------------------------------------------------------


@dataclass
class Entry:
    kind: str
    key: str
    fields: dict[str, str] = field(default_factory=dict)


def parse_bib(text: str) -> list[Entry]:
    """Entries of a BibTeX file: ``@kind{key, name = {value}, ...}``; values in braces or quotes."""
    entries: list[Entry] = []
    i = 0
    while True:
        m = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,").search(text, i)
        if not m:
            break
        kind, key = m.group(1).lower(), m.group(2)
        if kind in ("comment", "string", "preamble"):
            i = m.end()
            continue
        entry = Entry(kind, key)
        j = m.end()
        while j < len(text):
            while j < len(text) and text[j] in " \t\r\n,":
                j += 1
            if j >= len(text) or text[j] == "}":
                break
            name_m = re.compile(r"([A-Za-z][\w-]*)\s*=\s*").match(text, j)
            if not name_m:
                raise ValueError(f"entry {key}: cannot read a field near {text[j : j + 30]!r}")
            j = name_m.end()
            value, j = _read_value(text, j)
            entry.fields[name_m.group(1).lower()] = value.strip()
        entries.append(entry)
        i = j + 1
    return entries


def _read_value(text: str, j: int) -> tuple[str, int]:
    if text[j] == "{":
        depth, k = 1, j + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(text[k], 0)
            k += 1
        return text[j + 1 : k - 1], k
    if text[j] == '"':
        k = text.index('"', j + 1)
        return text[j + 1 : k], k + 1
    m = re.compile(r"[\w.-]+").match(text, j)
    if not m:
        raise ValueError(f"cannot read a value near {text[j : j + 30]!r}")
    return m.group(0), m.end()


# --- normalisation ------------------------------------------------------------------------------


def plain(s: str) -> str:
    """Lowercase ASCII words only: strips LaTeX commands, braces, accents and punctuation."""
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)
    s = s.replace("\\&", "and").replace("&", "and")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s.replace("-", " ")).lower()
    return " ".join(s.split())


def bib_authors(raw: str) -> list[str]:
    return [a.strip() for a in re.split(r"\s+and\s+", raw) if a.strip()]


def surname(name: str) -> str:
    name = name.strip()
    last = name.split(",", 1)[0] if "," in name else name.split()[-1]
    return plain(last).replace(" ", "")


# --- records ------------------------------------------------------------------------------------


@dataclass
class Record:
    title: str
    authors: list[str]  # surnames
    year: int
    year_last: int  # year of the latest version (arXiv); equal to year for Crossref
    source: str


def fetch_crossref(doi: str, fetch: Fetch) -> Record | None:
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
    try:
        body = json.loads(fetch(url))["message"]
    except (urllib.error.HTTPError, KeyError, json.JSONDecodeError):
        return None
    parts = (body.get("issued") or body.get("published") or {}).get("date-parts") or [[None]]
    year = parts[0][0]
    if not body.get("title") or year is None:
        return None
    authors = [plain(a.get("family", "")).replace(" ", "") for a in body.get("author", [])]
    return Record(body["title"][0], authors, int(year), int(year), "Crossref")


def fetch_arxiv(ids: list[str], fetch: Fetch) -> dict[str, Record]:
    joined = ",".join(ids)
    url = f"https://export.arxiv.org/api/query?max_results={len(ids)}&id_list={joined}"
    body = fetch(url)
    # the standard-library parser expands entities; an Atom feed never needs a DOCTYPE or an
    # entity, so a response that declares one is refused (no extra dependency, lock unchanged)
    if re.search(r"<!(DOCTYPE|ENTITY)", body, re.I):
        raise ET.ParseError("the response declares a DOCTYPE or an entity; refused")
    root = ET.fromstring(body)  # noqa: S314 - checked above
    out: dict[str, Record] = {}
    for e in root.findall("a:entry", ATOM):
        raw_id = (e.findtext("a:id", "", ATOM)).rsplit("/abs/", 1)[-1]
        arxiv_id = re.sub(r"v\d+$", "", raw_id)
        title = " ".join((e.findtext("a:title", "", ATOM)).split())
        if not title or title.lower() == "error":
            continue
        authors = [surname(a.findtext("a:name", "", ATOM)) for a in e.findall("a:author", ATOM)]
        published = int((e.findtext("a:published", "", ATOM))[:4])
        updated = int((e.findtext("a:updated", "", ATOM))[:4])
        out[arxiv_id] = Record(title, authors, published, updated, "arXiv")
    return out


# --- comparison ---------------------------------------------------------------------------------


@dataclass
class Result:
    key: str
    source: str
    status: str  # ok | mismatch | unresolved
    detail: str = ""


def compare(entry: Entry, rec: Record) -> Result:
    problems = []
    ratio = difflib.SequenceMatcher(
        None, plain(entry.fields.get("title", "")), plain(rec.title)
    ).ratio()
    if ratio < TITLE_RATIO:
        problems.append(f"title: bib '{entry.fields.get('title')}' against {rec.source} "
                        f"'{rec.title}' (similarity {ratio:.2f})")  # fmt: skip
    authors = bib_authors(entry.fields.get("author", ""))
    if not authors:
        problems.append("no author field")
    elif rec.authors:
        if surname(authors[0]) != rec.authors[0]:
            problems.append(f"first author: bib '{surname(authors[0])}' against "
                            f"{rec.source} '{rec.authors[0]}'")  # fmt: skip
        if len(authors) != len(rec.authors):
            problems.append(f"author count: bib {len(authors)} against {rec.source} "
                            f"{len(rec.authors)}")  # fmt: skip
    year = entry.fields.get("year", "")
    if not year.isdigit():
        problems.append("no year")
    elif rec.source == "Crossref" and int(year) != rec.year:
        problems.append(f"year: bib {year} against Crossref {rec.year}")
    elif rec.source == "arXiv" and not rec.year <= int(year) <= rec.year_last + 1:
        problems.append(f"year: bib {year} outside arXiv {rec.year} to {rec.year_last} (+1)")
    if problems:
        return Result(entry.key, rec.source, "mismatch", "; ".join(problems))
    return Result(entry.key, rec.source, "ok")


def check(entries: list[Entry], fetch: Fetch, pause: float = 0.0) -> list[Result]:
    results: dict[str, Result] = {}
    arxiv_ids = {e.key: e.fields["eprint"].strip() for e in entries if "eprint" in e.fields}
    arxiv: dict[str, Record] = {}
    if arxiv_ids:
        try:
            arxiv = fetch_arxiv(sorted(set(arxiv_ids.values())), fetch)
        except (urllib.error.URLError, ET.ParseError) as exc:
            for key in arxiv_ids:
                results[key] = Result(key, "arXiv", "unresolved", f"arXiv request failed: {exc}")
        time.sleep(pause)
    for e in entries:
        if e.key in results:
            continue
        doi = e.fields.get("doi", "").strip()
        if doi:
            try:
                rec = fetch_crossref(doi, fetch)
            except urllib.error.URLError as exc:
                results[e.key] = Result(e.key, "Crossref", "unresolved", f"request failed: {exc}")
                continue
            time.sleep(pause)
            results[e.key] = (
                compare(e, rec) if rec else Result(e.key, "Crossref", "unresolved", f"doi {doi}")
            )
        elif e.key in arxiv_ids:
            rec = arxiv.get(arxiv_ids[e.key])
            results[e.key] = (
                compare(e, rec)
                if rec
                else Result(e.key, "arXiv", "unresolved", f"eprint {arxiv_ids[e.key]}")
            )
        else:
            results[e.key] = Result(e.key, "-", "unresolved", "neither doi nor eprint")
    return [results[e.key] for e in entries]


def unknown_keys(entries: list[Entry], texts: dict[str, str]) -> dict[str, list[str]]:
    """Key-shaped tokens in the given texts that are not bibliography keys, by file."""
    known = {e.key for e in entries}
    out: dict[str, list[str]] = {}
    for name, text in texts.items():
        found = sorted({k for k in KEY_RE.findall(text) if k not in known})
        if found:
            out[name] = found
    return out


# --- command line -------------------------------------------------------------------------------


def make_fetch(cache: Path | None) -> Fetch:
    def fetch(url: str) -> str:
        path = None
        if cache is not None:
            cache.mkdir(parents=True, exist_ok=True)
            path = cache / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".txt")
            if path.exists():
                return path.read_text(encoding="utf-8")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https hosts
            body = resp.read().decode("utf-8")
        if path is not None:
            path.write_text(body, encoding="utf-8")
        return body

    return fetch


def main(argv: list[str] | None = None, fetch: Fetch | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--bib", type=Path, default=ROOT / "paper" / "references.bib")
    ap.add_argument("--cache", type=Path, default=None, help="directory for fetched responses")
    ap.add_argument("--cited", type=Path, nargs="*", default=[], help="files whose keys to check")
    ap.add_argument("--pause", type=float, default=1.0, help="seconds between hosts")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # accented author names must not crash a Windows console
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    entries = parse_bib(args.bib.read_text(encoding="utf-8"))
    results = check(entries, fetch or make_fetch(args.cache), args.pause)
    bad = [r for r in results if r.status != "ok"]
    for r in results:
        print(f"{r.status:10s} {r.key:30s} {r.source:9s} {r.detail}")
    missing = unknown_keys(entries, {p.name: p.read_text(encoding="utf-8") for p in args.cited})
    for name, keys in missing.items():
        print(f"unknown key in {name}: {', '.join(keys)}")
    ok, n_missing = len(results) - len(bad), sum(len(v) for v in missing.values())
    print(
        f"{ok} of {len(results)} entries resolved and matched; {len(bad)} problem(s); "
        f"{n_missing} unknown cited key(s)"
    )
    return 1 if bad or missing else 0


if __name__ == "__main__":
    sys.exit(main())
