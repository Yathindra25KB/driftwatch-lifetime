"""scripts/check_bib.py: parsing, comparison and failure rules (recorded responses only)."""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cb = load_script("check_bib")

BIB = r"""
% a comment
@inproceedings{alpha2019tesseract,
  title = {{TESSERACT}: Eliminating Bias \& Drift},
  author = {Pendlebury, Feargus and Pierazzi, Fabio},
  booktitle = {USENIX},
  year = {2019},
  eprint = {1807.07838},
  archiveprefix = {arXiv}
}
@article{beta2025delays,
  title = "Label delays in {M}alware pipelines",
  author = {Botacin, Marcus and Gomes, Heitor},
  year = 2025,
  doi = {10.1016/j.cose.2024.104122}
}
@misc{gamma2024none,
  title = {No identifier here},
  author = {Nobody, N.},
  year = {2024}
}
"""


def atom(*entries: tuple[str, str, list[str], str, str]) -> str:
    body = ""
    for arxiv_id, title, authors, published, updated in entries:
        names = "".join(f"<author><name>{a}</name></author>" for a in authors)
        body += (
            f"<entry><id>http://arxiv.org/abs/{arxiv_id}v4</id><title>{escape(title)}</title>"
            f"<published>{published}</published><updated>{updated}</updated>{names}</entry>"
        )
    return f'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">{body}</feed>'


def crossref(title: str, family: list[str], year: int) -> str:
    msg = {
        "title": [title],
        "author": [{"family": f} for f in family],
        "issued": {"date-parts": [[year]]},
    }
    return json.dumps({"message": msg})


GOOD_ARXIV = atom(
    ("1807.07838", "TESSERACT: Eliminating Bias & Drift", ["Feargus Pendlebury", "Fabio Pierazzi"],
     "2018-07-20T00:00:00Z", "2019-06-01T00:00:00Z")
)  # fmt: skip
GOOD_CROSSREF = crossref("Label delays in Malware pipelines", ["Botacin", "Gomes"], 2025)


def fetcher(arxiv: str = GOOD_ARXIV, cross: str = GOOD_CROSSREF):
    calls: list[str] = []

    def fetch(url: str) -> str:
        calls.append(url)
        return arxiv if "arxiv.org" in url else cross

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


def results(fetch, bib: str = BIB):
    return {r.key: r for r in cb.check(cb.parse_bib(bib), fetch)}


def test_the_parser_reads_braced_quoted_and_bare_values_and_skips_comments() -> None:
    entries = cb.parse_bib(BIB)
    assert [e.key for e in entries] == ["alpha2019tesseract", "beta2025delays", "gamma2024none"]
    assert entries[0].fields["title"] == r"{TESSERACT}: Eliminating Bias \& Drift"
    assert entries[1].fields["title"] == "Label delays in {M}alware pipelines"
    assert entries[1].fields["year"] == "2025"


def test_a_matching_entry_is_ok_and_one_without_an_identifier_is_unresolved() -> None:
    res = results(fetcher())
    assert res["alpha2019tesseract"].status == "ok"
    assert res["beta2025delays"].status == "ok"
    assert res["gamma2024none"].status == "unresolved"
    assert "neither doi nor eprint" in res["gamma2024none"].detail


def test_arxiv_ids_go_in_one_request() -> None:
    f = fetcher()
    results(f)
    assert sum("arxiv.org" in u for u in f.calls) == 1


@pytest.mark.parametrize(
    ("arxiv", "needle"),
    [
        (atom(("1807.07838", "A totally different title about graphs", ["Feargus Pendlebury",
              "Fabio Pierazzi"], "2018-07-20T00:00:00Z", "2019-06-01T00:00:00Z")), "title"),
        (atom(("1807.07838", "TESSERACT: Eliminating Bias & Drift", ["Someone Else",
              "Fabio Pierazzi"], "2018-07-20T00:00:00Z", "2019-06-01T00:00:00Z")), "first author"),
        (atom(("1807.07838", "TESSERACT: Eliminating Bias & Drift", ["Feargus Pendlebury"],
              "2018-07-20T00:00:00Z", "2019-06-01T00:00:00Z")), "author count"),
        (atom(("1807.07838", "TESSERACT: Eliminating Bias & Drift", ["Feargus Pendlebury",
              "Fabio Pierazzi"], "2021-07-20T00:00:00Z", "2021-08-01T00:00:00Z")), "year"),
    ],
)  # fmt: skip
def test_an_arxiv_mismatch_is_reported_with_its_reason(arxiv: str, needle: str) -> None:
    r = results(fetcher(arxiv=arxiv))["alpha2019tesseract"]
    assert r.status == "mismatch" and needle in r.detail


def test_a_venue_year_after_the_preprint_is_allowed_but_not_before_it() -> None:
    later = atom(("1807.07838", "TESSERACT: Eliminating Bias & Drift",
                  ["Feargus Pendlebury", "Fabio Pierazzi"], "2017-07-20T00:00:00Z",
                  "2018-06-01T00:00:00Z"))  # fmt: skip
    assert results(fetcher(arxiv=later))["alpha2019tesseract"].status == "ok"  # 2019 <= 2018 + 1


def test_crossref_year_must_match_exactly_and_a_missing_doi_is_unresolved() -> None:
    wrong = crossref("Label delays in Malware pipelines", ["Botacin", "Gomes"], 2024)
    assert results(fetcher(cross=wrong))["beta2025delays"].status == "mismatch"

    def not_found(url: str) -> str:
        if "crossref" in url:
            raise urllib.error.HTTPError(url, 404, "not found", None, None)  # type: ignore[arg-type]
        return GOOD_ARXIV

    assert results(not_found)["beta2025delays"].status == "unresolved"


def test_an_arxiv_response_that_declares_an_entity_is_refused() -> None:
    evil = '<?xml version="1.0"?><!DOCTYPE feed [<!ENTITY x "y">]><feed/>'
    res = results(fetcher(arxiv=evil))
    assert res["alpha2019tesseract"].status == "unresolved"
    assert "refused" in res["alpha2019tesseract"].detail


def test_title_normalisation_ignores_latex_case_and_punctuation() -> None:
    assert cb.plain(r"{TESSERACT}: Eliminating \& {Bias}") == cb.plain(
        "tesseract eliminating and bias"
    )
    assert cb.surname("Pierazzi, Fabio") == cb.surname("Fabio Pierazzi") == "pierazzi"
    assert cb.surname("Gómez, J.") == "gomez"


def test_unknown_cited_keys_are_found() -> None:
    entries = cb.parse_bib(BIB)
    text = {"ch.md": "see (alpha2019tesseract; zeta2030missing) and 2019 results"}
    assert cb.unknown_keys(entries, text) == {"ch.md": ["zeta2030missing"]}


def test_main_exits_nonzero_on_any_problem_and_zero_when_all_match(tmp_path: Path, capsys) -> None:
    good = tmp_path / "good.bib"
    good.write_text(BIB.split("@misc")[0], encoding="utf-8")
    assert cb.main(["--bib", str(good), "--pause", "0"], fetch=fetcher()) == 0
    bad = tmp_path / "bad.bib"
    bad.write_text(BIB, encoding="utf-8")
    assert cb.main(["--bib", str(bad), "--pause", "0"], fetch=fetcher()) == 1
    assert "neither doi nor eprint" in capsys.readouterr().out
    cited = tmp_path / "ch.md"
    cited.write_text("uses nonexistent2020key", encoding="utf-8")
    assert cb.main(["--bib", str(good), "--cited", str(cited), "--pause", "0"],
                   fetch=fetcher()) == 1  # fmt: skip
