# The project working

Captures of the real system, taken from real runs on 27 Oct 2026 on a Windows 11 laptop. Each caption says what was run. The terminal captures show the program's own output, with colours removed and my local scratch paths shortened; nothing here is a mock-up. They were taken at code commit `d183423`; the documentation-only commits after it do not change the code.

Fixture numbers (anything from `driftwatch smoke`) test the code path only and are never evidence. Results are in the [claims ledger](../CLAIMS.md).

## 1. Install and run from nothing

```{figure} img/term-smoke.png
:alt: Terminal: a fresh virtual environment, the wheel installed, driftwatch --version printing 0.1.0, driftwatch smoke ending in MATCH with exit code 0
:width: 100%

The wheel built from the repository, installed into a fresh virtual environment and run from an empty folder that is not a checkout. `driftwatch smoke` regenerates the synthetic fixture, builds the cache, slices windows under the C1 to C3 checks (the log lines show the malware share being brought to the target ratio), fits both detectors, and compares the result with the golden table shipped inside the wheel: `MATCH`, exit code `0`. This is the acceptance test of the release workflow, run on Linux and Windows before anything is uploaded.
```

## 2. The documentation site

```{figure} img/docs-architecture.png
:alt: The architecture overview page of the documentation site
:width: 100%

The built documentation site (Sphinx with MyST and the Furo theme), architecture overview page. The left column lists the pages; the build is strict, so a broken link or an unknown reference fails it.
```

```{figure} img/docs-simulator.png
:alt: The simulator page showing the rendered sealed-boundary diagram
:width: 100%

The simulator page with the sealed-boundary diagram (Figure 4), drawn from the Mermaid source in the page. Every diagram on the site is checked to draw without error before the PDF export.
```

```{figure} img/term-docs.png
:alt: Terminal: sphinx-build strict build succeeded with exit code 0, then the link check with exit code 0
:width: 100%

The strict build (`-W --keep-going`: every warning is an error) and then the external link check, both exit code `0`.
```

## 3. The checks that guard the work

```{figure} img/term-pytest.png
:alt: Terminal: the fast test suite passing
:width: 100%

The fast test suite (the slow suites run in continuous integration and before a release).
```

```{figure} img/term-guardrails.png
:alt: Terminal: the guardrail demonstration reports 45 of 45 scenarios passed
:width: 100%

The guardrail demonstration: each guard scenario (a blocked force push, a blocked edit of a locked file, a download from an unlisted host, and so on) is run against a throw-away repository, never the real one, and must be blocked or allowed as designed. The latency lines show what the hooks cost per call.
```

```{figure} img/term-claims.png
:alt: Terminal: the claims audit passes
:width: 100%

The claims audit: every paragraph of the README, the report chapters and the architecture pages that contains a number must cite a row of the claims ledger, every cited row must name a file and a commit, and "first" may not be used as a contribution claim.
```

```{figure} img/term-release.png
:alt: Terminal: release checks pass for the wheel and source archive
:width: 100%

The release checks: version, tag, changelog and citation file agree; the built wheel and source archive hold no dataset, result or secret and stay small; `twine check --strict` accepts both files; the Zenodo metadata is well formed.
```

## 4. Not captured yet

Captures of the public GitHub Actions runs, the TestPyPI and PyPI project pages and the Zenodo record cannot exist before the repository is public and the release is published. They are added to this page after the release, with their dates ([RELEASING](../RELEASING.md), step "After the release").
