# Roadmap

What may come after 0.1.0. Research items come from chapter 9 section 9.5 of the report. Each needs its own pre-registration (an addendum and a `prereg-vN` tag) **before** any run, because a change chosen after seeing results is no longer a test. Nothing here is promised. Order and timing are the researcher's.

## Releases

| Version | Content | Precondition |
|---|---|---|
| 0.1.x | Fixes only: documentation, packaging, dependency refreshes that leave every stored number unchanged | quarterly dependency refresh (docs/MAINTENANCE.md) |
| 0.2.0 | The 8-page workshop paper (`paper/main.tex`), built from `docs/CLAIMS.md` only, and the researcher's rewrite of the report | after the capstone hand-in (10 Dec 2026) |
| 0.3.0 | Any of the research items below that is registered and run | its addendum and tag |

## Research items (chapter 9 section 9.5)

- **Tier 3:** E5, a cross-platform comparison, with the rule for disagreement written in advance; E6, EMBER2024 (`reports/G5-tier3-decision.md`).
- **Drift monitors at other settings:** a larger sample per slot, a stricter significance level, or another reference rule, reported with the alarm rate [E-63].
- **A longer BODMAS evaluation window**, so that the delay axis has more than one refit (needs an ADR).
- **Label noise and measured delay:** noise injected at a stated rate, and an observed delay distribution if one can be obtained.
- **A trap arm whose released labels also train the model** [E-45].
- **Controls for class prior:** a random baseline matched to the malware share, and a threshold-free score (PR-AUC) from stored predictions [E-66, E-47].
- **A registered lifetime measure:** threshold and start slot fixed in advance, per-window curves, an interval [E-68].
- **A label-using monitor:** a Transcend-style credibility monitor with label-conditional p-values.
- **A public deposit of the stored predictions** (hashed already [E-69]), so that every table can be rebuilt without the original disk.
- **A stratified within-slot random-split comparator** (ADR-0008) [E-18].

## Engineering

- Re-evaluate Zensical for the docs site when it leaves alpha and ships native versioning (ADR-0011).
- Rename the import package only if a user reports the clash with the unrelated `driftwatch` PyPI package (ADR-0003).
- Accept a contributed dataset loader only with a data card, a licence that permits the use, and a manifest with hashes (`CONTRIBUTING.md`).
