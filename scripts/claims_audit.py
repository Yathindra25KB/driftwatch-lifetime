"""Claims audit: every number in the README and the chapters must trace to docs/CLAIMS.md.

    uv run python scripts/claims_audit.py                 # README and chapters 1 to 8
    uv run python scripts/claims_audit.py --write reports/claims_audit.md

Rules (CLAUDE.md hard rules 8 and 9, .claude/rules/writing.md):

1. A paragraph or table that contains a number must cite at least one claim id of the form
   ``E-13``, ``P-08``, ``S-02`` (letters, hyphen, two or three digits), and every cited id must
   exist in docs/CLAIMS.md. A paragraph marked ``[verify]`` or ``[researcher: verify]`` is
   reported as pending instead of failing: it names itself as unverified.
2. Every row of docs/CLAIMS.md that is cited must name a source file and a commit.
3. "first" is never a contribution claim: phrases such as "the first to" or "first ever" fail.

Ignored as numbers: years, dates written "15 Oct 2026", item numbers at the start of a line,
heading lines, code blocks and inline code, identifiers with letters attached (RQ1, C3, ch07).
Exit code 0 when nothing fails.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = (
    "README.md",
    "report/ch01_introduction.md",
    "report/ch02_landscape.md",
    "report/ch03_analysis.md",
    "report/ch04_latest_techniques.md",
    "report/ch05_related_work.md",
    "report/ch06_method.md",
    "report/ch07_experiments.md",
    "report/ch08_discussion.md",
)
ID_RE = re.compile(r"\b([A-Z]{1,2}-\d{2,3})\b")
NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*%?(?![\w])")
DATE_RE = re.compile(
    r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?(?:\s+\d{4})?\b"
)
YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
VERIFY_RE = re.compile(r"\[(?:researcher:\s*)?verify[^\]]*\]", re.IGNORECASE)
FIRST_RE = re.compile(
    r"\b(?:the|a)\s+first\s+(?:to|study|work|paper|system|framework|open|attempt|benchmark)\b"
    r"|\bfirst[- ]ever\b|\bwe\s+are\s+the\s+first\b|\bfirst\s+to\b",
    re.IGNORECASE,
)


@dataclass
class Paragraph:
    file: str
    line: int
    text: str


@dataclass
class Report:
    files: list[str] = field(default_factory=list)
    n_paragraphs_with_numbers: int = 0
    covered: int = 0
    pending: list[Paragraph] = field(default_factory=list)  # marked [verify]
    uncovered: list[Paragraph] = field(default_factory=list)
    unresolved: list[tuple[Paragraph, str]] = field(default_factory=list)
    incomplete_rows: list[str] = field(default_factory=list)  # cited rows lacking file or commit
    first_claims: list[Paragraph] = field(default_factory=list)
    cited: set[str] = field(default_factory=set)

    @property
    def ok(self) -> bool:
        return not (self.uncovered or self.unresolved or self.incomplete_rows or self.first_claims)


def parse_claims(text: str) -> dict[str, dict[str, str]]:
    """Claim id -> {source, commit, tag} from the ledger table."""
    rows: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not ID_RE.fullmatch(cells[0]):
            continue
        rows[cells[0]] = {
            "statement": cells[1],
            "source": cells[3],
            "commit": cells[4],
            "tag": cells[5],
        }
    return rows


def paragraphs(path: Path, rel: str) -> list[Paragraph]:
    """Blocks of prose or table, with code fences and headings removed."""
    out: list[Paragraph] = []
    block: list[str] = []
    start = 1
    in_code = False

    def flush() -> None:
        nonlocal block
        if block:
            out.append(Paragraph(rel, start, chr(10).join(block)))
        block = []

    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip()
        if line.lstrip().startswith("```"):
            flush()
            in_code = not in_code
            continue
        if in_code:
            continue
        if not line.strip():
            flush()
            continue
        if line.lstrip().startswith("#"):  # headings carry section numbers, not claims
            flush()
            continue
        if not block:
            start = n
        block.append(line)
    flush()
    return out


def numbers(text: str) -> list[str]:
    """Numeric tokens that would need a claim."""
    t = re.sub(r"`[^`]*`", " ", text)  # inline code
    t = re.sub(r"\]\([^)]*\)", "]", t)  # link targets
    t = DATE_RE.sub(" ", t)
    t = re.sub(r"\[[A-Z]{1,2}-\d{2,3}\]", " ", t)  # the claim tags themselves
    t = ID_RE.sub(" ", t)
    t = re.sub(r"(?m)^\s*(?:[-*]\s+)?\d+[.)]\s", " ", t)  # list item numbers
    t = re.sub(r"\|\s*\d+\s*(?=\|)", "|", t)  # a table cell that is only a chapter or row number
    t = re.sub(r"\b[Ss]ections?\s+\d+(?:\.\d+)*", " ", t)  # references to sections
    t = re.sub(r"\b[Cc]hapters?\s+\d+(?:\s*(?:to|and|-)\s*\d+)?", " ", t)
    t = re.sub(r"\b(?:Table|Figure|Eq\.?|Appendix|Tier|Phase|Gate|Week|Step)\s+\d+", " ", t)
    found = []
    for tok in NUMBER_RE.findall(t):
        bare = tok.rstrip("%")
        if YEAR_RE.match(bare) and not tok.endswith("%"):
            continue
        if bare in {"0", "1"}:  # zero and one as words of counting ("one run", "0")
            continue
        found.append(tok)
    return found


def audit(files: list[Path], claims_path: Path, root: Path = ROOT) -> Report:
    claims = parse_claims(claims_path.read_text(encoding="utf-8"))
    rep = Report()
    for path in files:
        if not path.exists():
            continue
        rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        rep.files.append(rel)
        for p in paragraphs(path, rel):
            if FIRST_RE.search(p.text):
                rep.first_claims.append(p)
            ids = set(ID_RE.findall(p.text))
            rep.cited |= ids
            bad = sorted(i for i in ids if i not in claims)
            for i in bad:
                rep.unresolved.append((p, i))
            if not numbers(p.text):
                continue
            rep.n_paragraphs_with_numbers += 1
            good = ids & set(claims)
            if good:
                rep.covered += 1
            elif VERIFY_RE.search(p.text):
                rep.pending.append(p)
            else:
                rep.uncovered.append(p)
    for cid in sorted(rep.cited):
        row = claims.get(cid)
        if row is None:
            continue
        if not row["source"].strip() or not row["commit"].strip():
            rep.incomplete_rows.append(cid)
    return rep


NOT_SHOWN = (
    "That the gap between random-split F1 and time-aware AUT is *caused* by temporal leakage: "
    "the per-slot comparator reaches a lower malware ratio than the time-aware series on LAMDA, "
    "and the E0 and per-slot comparators disagree about the 0.05 band on LAMDA (P-14, E-19).",
    "A delay curve on BODMAS: with nE = 6 and retraining every third slot there is one useful "
    "refit per window, and periodic equals never at a delay of three by construction (P-12).",
    "Independent replication on LAMDA: its 16 rolling windows are about four independent "
    "12-month blocks, and logistic regression is deterministic given its pool, so seeds are "
    "draws of the C3 subsample and of the selection, not replicates of the model (P-12).",
    "That more labels do not help when a flat result appears at the smallest budget: retraining "
    "changed 0.2% to 2.1% of decisions in the earlier diagnostic (P-13).",
    "Anything about conformal selection, drift monitors, other platforms or EMBER2024: those "
    "experiments (E3 to E6) have not been run in Tier 1.",
    "Anything about evasion or adversarial examples: the study describes decay, not defeat "
    "(docs/ETHICS.md).",
    "Results on another machine: every cell was run on one laptop; numeric drift elsewhere is "
    "reported, not corrected (docs/GRID.md).",
)


def render(rep: Report) -> str:
    def where(p: Paragraph) -> str:
        flat = " ".join(p.text.split())
        return f"{p.file}:{p.line}: {flat[:140]}{'...' if len(flat) > 140 else ''}"

    lines = ["# Claims audit", ""]
    lines += [
        f"Files audited: {', '.join(rep.files) or 'none'}.",
        f"Paragraphs and tables with numbers: {rep.n_paragraphs_with_numbers}; "
        f"with a resolving claim id: {rep.covered}; marked [verify]: {len(rep.pending)}; "
        f"uncovered: {len(rep.uncovered)}.",
        f"Claim ids cited: {len(rep.cited)}. Unresolved ids: {len(rep.unresolved)}. "
        f"Cited rows lacking a source file or commit: {len(rep.incomplete_rows)}. "
        f"'first' used as a contribution claim: {len(rep.first_claims)}.",
        f"**Result: {'PASS' if rep.ok else 'FAIL'}**",
        "",
    ]
    for title, items in (
        (
            "Uncovered paragraphs (a number with no resolving claim id)",
            [where(p) for p in rep.uncovered],
        ),
        ("Unresolved claim ids", [f"{where(p)} -> {i}" for p, i in rep.unresolved]),
        ("Cited rows without source file or commit", rep.incomplete_rows),
        ("'first' as a contribution claim", [where(p) for p in rep.first_claims]),
        (
            "Pending (marked [verify]; to be checked by the researcher)",
            [where(p) for p in rep.pending],
        ),
    ):
        lines.append(f"## {title}")
        lines += [f"- {i}" for i in items] or ["- none"]
        lines.append("")
    lines.append("## What the results do not show")
    lines += [f"- {s}" for s in NOT_SHOWN]
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("files", nargs="*", type=Path, help="default: README and chapters")
    ap.add_argument("--claims", type=Path, default=ROOT / "docs" / "CLAIMS.md")
    ap.add_argument("--write", type=Path, help="write the Markdown report here")
    args = ap.parse_args(argv)
    files = args.files or [ROOT / f for f in DEFAULT_FILES]
    rep = audit([f if f.is_absolute() else ROOT / f for f in files], args.claims)
    text = render(rep)
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8", newline="\n")
    print(text if not args.write else text.split("\n## ")[0])
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
