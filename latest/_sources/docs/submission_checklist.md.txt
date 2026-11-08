# Submission checklist

This is a checklist for submitting the paper. A first full draft exists: `paper/main.tex` (IEEE conference template, A4, 7 pages including references; build with `tectonic paper/main.tex`) and `paper/main.pdf`. It is written from `docs/CLAIMS.md` only, and every number carries its claim id in small type; the claim ids are for the reader of the draft and should be removed or turned into footnotes at submission. Neither the draft nor the report has been read line by line by a person. Venue facts below were read on the venues' own pages on 8 Nov 2026 (`reports/source_verification_2026-11-08.md`). Deadlines move: read the call again before relying on a date. "Unconfirmed" means the official page could not be read or has not published a call for the 2027 cycle.

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

## Decision (8 Nov 2026): venue and AI wording

**Target: DIMVA 2027, cycle 2 (paper deadline 18 Feb 2027, firm; Springer LNCS; 18 pages main text, 25 in all; double-blind).** Reasons: its scope is malware and intrusion detection; the researcher's rewrite and a second person's reading need more than the 3.5 weeks before EuroS&P's 2 Dec 2026 deadline (which falls in the capstone hand-in week); and 18 pages fit the full study. A rejected cycle-1 paper cannot go to cycle 2, so submitting in cycle 2 only is deliberate. **Not EuroS&P 2027**: the call (read 8 Nov 2026) requires the official `eurosp2027` template (not other IEEE templates), anonymous artifact hosting (GitHub is excluded), a discussion of potential harms, and the disclosure of AI-generated content in the acknowledgments, naming the system and the sections concerned. A later venue (ARES 2027, when its call appears) is the fallback.

**AI wording.** The researcher decided on 8 Nov 2026 that the paper draft carries no AI-disclosure paragraph, and it carries none. That is a decision about the draft, not a finding that no venue requires one: EuroS&P's call requires it, and a venue's or a publisher's policy must be read and followed before any submission. The repository itself (README, report chapter 0, CLAUDE.md, commit trailers) records the use of Claude Code and was not changed.

**Build.** `paper/main.tex` is the IEEE-format draft. `paper/main-anon.tex` builds the anonymous variant (no author block, repository address withheld). DIMVA needs the Springer LNCS class: porting is a class change, the bibliography style and the claim ids removed; it has not been done.

## Before any submission

- [ ] The researcher rewrites and defends the text. Every chapter says it is a draft written with Claude Code.
- [ ] The venue's and the publisher's policy on AI-assisted writing and code is read and followed. The paper draft has no disclosure paragraph by the researcher's decision (see above); the venue may require one.
- [ ] Every number comes from `docs/CLAIMS.md` (`uv run python scripts/claims_audit.py` says PASS).
- [ ] `uv run python scripts/check_bib.py` resolves every entry; entries cited as "accepted" or "submitted" are updated if a final version exists (`paper/REFERENCES_TODO.md`).
- [ ] The registered and unregistered parts are labelled as in chapter 7 (RQ1 was registered after E0 and E1 were read; the lifetime reading is exploratory).
- [ ] The limits in chapter 8 (section 8.3 and the open items in section 8.7) appear in the paper, not only in the repository.
- [ ] The artifact statement points at the release tag, the Zenodo DOI (when it exists), `driftwatch smoke` and `driftwatch reproduce table1`.
- [ ] Double-blind venues: the repository name, the author line in `CITATION.cff` and the commit identity are visible, so decide how the venue wants the artifact link anonymised.
- [ ] Ethics: no malware, no evasion tooling, feature files only (`docs/ETHICS.md`); say so in the paper.
