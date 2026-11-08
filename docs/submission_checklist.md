# Submission checklist

This is a checklist for turning the report into a paper. **No paper exists yet.** `paper/main.tex` is not written; the roadmap puts it after the capstone hand-in (`docs/ROADMAP.md`, release 0.2.0). Venue facts below were read on the venues' own pages on 8 Nov 2026 (`reports/source_verification_2026-11-08.md`). Deadlines move: read the call again before relying on a date. "Unconfirmed" means the official page could not be read or has not published a call for the 2027 cycle.

## Venues

| Venue | Deadline (as stated) | Format and length (as stated) | Source |
|---|---|---|---|
| IEEE EuroS&P 2027 (Madrid, 5 to 9 Jul 2027) | Registration 25 Nov 2026; submission 2 Dec 2026 (AoE) | 13 pages of body text; references and appendices extra; IEEE conference template | eurosp2027.ieee-security.org/cfp.html |
| DIMVA 2027 (Enschede, 30 Jun to 2 Jul 2027) | Cycle 1: paper 10 Dec 2026 (firm); cycle 2: paper 18 Feb 2027 (firm) | 25 pages in all (18 main, 5 bibliography, 2 appendix); Springer LNCS; double-blind | dimva.org/dimva2027/ |
| IEEE SaTML 2027 | Closed (paper deadline was 29 Sep 2026) | 12 pages body; IEEEtran; double-blind. The call says that papers that only use a dataset without engaging trustworthiness may be desk rejected | satml.org/call-for-papers/ |
| ARES 2027 (Venice, 24 to 27 Aug 2027) | Unconfirmed: the site says the call "will be available soon" (the 2026 edition's full-paper deadline was 9 Mar 2026) | Unconfirmed for 2027 (2026: 22 pages including references, Springer LNCS) | ares-conference.eu |
| ACSAC, AISec, RAID (2027 editions) | Unconfirmed: no 2027 call found | Unconfirmed (ACSAC 2026: 11 pages plus appendix; AISec 2026: 10 pages plus 2) | acsac.org, aisec.cc |
| Computers & Security (journal) | None (journal) | Unconfirmed: the author guide could not be read. The journal has published two closely related papers (Botacin and Gomes; ActDroid) | sciencedirect.com |

The capstone deadline is about 10 Dec 2026 [verify] (researcher, 21 Oct 2026, exact date to confirm; docs/PHASES.md), and the report plus the repository are the hand-in. A paper for the first two rows would have to be written, rewritten by the researcher and checked within days, so the checklist treats them as options for the researcher, not as a plan.

## Before any submission

- [ ] The researcher rewrites and defends the text. Every chapter says it is a draft written with Claude Code.
- [ ] The venue's policy on AI-assisted writing is read and the disclosure paragraph in `report/ch00_front_matter.md` is changed to match it. The wording of any policy is not known to this project.
- [ ] Every number comes from `docs/CLAIMS.md` (`uv run python scripts/claims_audit.py` says PASS).
- [ ] `uv run python scripts/check_bib.py` resolves every entry; entries cited as "accepted" or "submitted" are updated if a final version exists (`paper/REFERENCES_TODO.md`).
- [ ] The registered and unregistered parts are labelled as in chapter 7 (RQ1 was registered after E0 and E1 were read; the lifetime reading is exploratory).
- [ ] The limits in chapter 8 (section 8.3 and the open items in section 8.7) appear in the paper, not only in the repository.
- [ ] The artifact statement points at the release tag, the Zenodo DOI (when it exists), `driftwatch smoke` and `driftwatch reproduce table1`.
- [ ] Double-blind venues: the repository name, the author line in `CITATION.cff` and the commit identity are visible, so decide how the venue wants the artifact link anonymised.
- [ ] Ethics: no malware, no evasion tooling, feature files only (`docs/ETHICS.md`); say so in the paper.
