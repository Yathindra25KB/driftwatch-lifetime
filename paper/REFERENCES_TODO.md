# References still open

`paper/references.bib` holds 34 entries. Each was built from the arXiv or Crossref record named by its identifier and is re-resolved by `scripts/check_bib.py` (22 Oct 2026: 34 of 34 resolved and matched). Never add an entry by hand from memory: fetch the record, then run the script.

Resolved on 22 Oct 2026 (CLAIMS L-nn rows hold the evidence): EMBER and EMBER2024; the extended TESSERACT paper; the Gama survey; Ceschin et al.; ADAPT; LFreeDA; MADCAT; TIF; DREAM; Aurora; McNdroid; Kalny et al.; EMA; the two adversarial surveys; Shafer and Vovk; the three language-model papers. The pages of Chen et al. (USENIX Security 2023, 1127 to 1144), Transcend (2017, 625 to 642) and CADE (2021, 2327 to 2344) come from the USENIX pages [L-11, L-12, L-13]. Li et al. is NDSS 2025 [L-33].

Open:

| Item | What is missing | Where it came from |
|---|---|---|
| Transcend (USENIX Security 2017) and CADE (USENIX Security 2021) | No DOI or arXiv record, so they are not in `references.bib` and `check_bib.py` cannot resolve them. They are cited in chapter 5 by their USENIX pages [L-12, L-13] | USENIX proceedings |
| "Li et al. (NDSS 2025)" | The researcher confirms that `li2024revisiting` is the paper meant by plan Table G.1 | `docs/related_work_addendum.md` |
| TESSERACT, USENIX Security 2019 | Proceedings pages or URL (the bib uses arXiv 1807.07838; v4 matches the USENIX version) | arXiv comment |
| ActDroid journal version | arXiv lists related DOI 10.1016/j.cose.2025.104724; confirm it is the same work before citing the journal version | arXiv page |
| LAMDA at ICLR 2026 | Formal proceedings entry (only the poster page was found; its title and authors match the arXiv record) | iclr.cc |
| SEED, FIRCE, Cerqueira et al., Minnei et al., EMA, DREAM, TIF | Final venue versions, if published (the arXiv comments name KDD 2026, SIGCOMM 2026, ACM CCS 2025 and IEEE TSE for some) | arXiv pages |
| Botacin and Gomes | The publisher page returned HTTP 403; the abstract was read on the NSF Public Access Repository [L-18] | par.nsf.gov |
| BODMAS labelling | How its labels were produced (the project page does not say) [D-17] | docs/data_cards/bodmas.md |
| AndroZoo | Citation the AndroZoo maintainers request (only if AndroZoo is ever used; currently excluded) | Build guide section 6 |

Note on AUT (resolved in ADR-0006 and CLAIMS M-02): TESSERACT arXiv v4 says the published Eq. (4) had an extra 1/N normalisation factor; the guide's 1/(N-1) form equals the numpy trapezoid and is pinned by `tests/test_aut.py`.
