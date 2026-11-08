# Tier 3 go/no-go decision (Phase 10)

**Prepared:** 21 Oct 2026, by Claude Code (engineering lead), from `reports/G4.md`, `docs/PHASES.md` and the researcher's answers of the same day.

**The decision rule is the Phase 10 prompt's:** evaluate the go checklist first; if any item fails, switch to MODE B (polish) without discussion; stop if the checklist says no.

## Go checklist

| Item | Rule | Value (researcher, 21 Oct 2026) | Met |
|---|---|---|---|
| Gate G4 passed | G4 PASS, and `reports/G4.md` says Tier 2 is complete or honestly reported | PASS, decided on 21 Oct 2026 | Yes |
| Cumulative hours within plan | at or under plan (151 h at the end of week 19, plan Table 4.1) | "within plan"; no figure given | Yes |
| Recent average | at least 9 h per week over the last four weeks | "at least 9 h per week"; no figure given | Yes |
| Capstone deadline | not earlier than the end of week 24 (Sun 28 Mar 2027) | **early December 2026, by 10 Dec 2026** | **No** |

The hours rows rest on the researcher's statement. The exact figures were not given, so the weekly hours log in `docs/PHASES.md` has no entries for weeks 1 and 2.

## Decision

**MODE B (polish), scoped down.** One item fails (the deadline), so the prompt's rule gives MODE B with no discussion. The researcher chose the scoped-down form, about 4 to 6 hours of their time.

**E5 (cross-platform replication) and E6 (EMBER2024) are not run.** They become future work, and the report says so. As the Phase 10 prompt defines E5, it repeats the Tier 2 headline contrasts on whichever of LAMDA or BODMAS they have not yet been run on. E3 and E4 each ran on both, so on that definition there is no platform left to repeat them on, and a cross-platform comparison of their directions and magnitudes can be read from the existing tables. This is a reading for the researcher, not a finding; what E5 would still add is a comparison of platforms under a pre-registered rule for disagreement, which is future work.

## What the deadline changes beyond Phase 10

The capstone is due by 10 Dec 2026, about seven weeks after this decision. The researcher hands in the report and the code repository.

Moved to after the deadline:
- the 8-page paper and the venue checklist;
- the release pipeline (PyPI, Zenodo DOI, documentation site);
- the maintenance system (arXiv-audit skill, issue templates).

Kept before the deadline:
- the report, chapters 1 to 9;
- the licence and ethics audit;
- a clean-clone reproduction check;
- the README.

Every irreversible step (PyPI upload, DOI, making the repository public, tags) still needs the researcher's explicit go. The ledger (`docs/PHASES.md`) records the compression.

## MODE B scope (plan of 21 Oct 2026)

1. This decision file.
2. Test coverage of constraints, the label queue, the conformal layer and the monitors (`reports/coverage.md`).
3. Dead code and orphan scripts (nothing cited in `docs/CLAIMS.md` is deleted).
4. A test that every config in `configs/` parses and plans its cells.
5. A listing of results produced by superseded code (`docs/results_audit.md`; nothing deleted).
6. A CI timing check and the uv cache.
7. A README for a first-time reader.
