"""Export the architecture section of the documentation as one PDF.

    uvx --with playwright python scripts/export_architecture_pdf.py
    uvx --with playwright python scripts/export_architecture_pdf.py --out some.pdf --channel chrome

Builds the section as a single HTML page with Sphinx, opens it in an installed Edge or Chrome
through Playwright (nothing is downloaded: Playwright only drives the browser that is already
there), waits until Mermaid has drawn every diagram, and prints to A4. Run it with `uvx --with
playwright`: Playwright is a tool for this script, not a dependency of the project. The
diagrams are drawn by Mermaid, which the page loads from a CDN, so this needs network access.
The print layout is docs/_static/pdf.css (print.css imports the same rules for printing from a
browser). Exit code 0 on success, 2 when Playwright or the browser is missing, or a diagram
did not draw.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_DOC = "docs/architecture/index"
DRAW_TIMEOUT_MS = 60_000
MARGIN = {"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"}
ALL_DRAWN = "() => [...document.querySelectorAll('.mermaid')].every(m => m.querySelector('svg'))"


def build_single_page(workdir: Path) -> Path:
    """Sphinx single-page build of the architecture section; returns its index.html."""
    # through `uv run`, so the project's environment (with Sphinx) is used even under uvx
    cmd = [
        "uv", "run", "sphinx-build", "-q", "-c", "docs", "-b", "singlehtml",
        "-D", f"root_doc={ROOT_DOC}", ".", str(workdir),
    ]  # fmt: skip
    subprocess.run(cmd, cwd=ROOT, check=True)
    # a nested root_doc is written in a subfolder but links its assets from the output root
    page = workdir / "index.html"
    shutil.copyfile(workdir / ROOT_DOC.rsplit("/", 1)[0] / "index.html", page)
    return page


def print_pdf(page_file: Path, out: Path, channel: str) -> int:
    """Open the page, wait for every diagram, print. Returns the number of diagrams."""
    from playwright.sync_api import sync_playwright

    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=channel)
        try:
            page = browser.new_page(viewport={"width": 1100, "height": 900})
            page.goto(page_file.as_uri())
            n = page.locator(".mermaid").count()
            page.wait_for_function(ALL_DRAWN, timeout=DRAW_TIMEOUT_MS)
            broken = page.locator(".mermaid", has_text="Syntax error").count()
            if broken:
                raise RuntimeError(f"{broken} diagram(s) have a Mermaid syntax error")
            page.pdf(path=str(out), format="A4", print_background=True, margin=MARGIN)
        finally:
            browser.close()
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "architecture_report.pdf")
    ap.add_argument("--channel", default="msedge", help="msedge or chrome (an installed browser)")
    args = ap.parse_args(argv)
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("run with: uvx --with playwright python scripts/export_architecture_pdf.py",
              file=sys.stderr)  # fmt: skip
        return 2
    with tempfile.TemporaryDirectory(prefix="driftwatch-arch-") as tmp:
        page = build_single_page(Path(tmp))
        try:
            n = print_pdf(page, args.out, args.channel)
        except Exception as exc:  # a missing browser or a diagram that did not draw
            print(f"could not print the PDF: {exc}", file=sys.stderr)
            return 2
    size = args.out.stat().st_size
    print(f"wrote {args.out} ({size / 1024:.0f} KB, {n} diagrams)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
