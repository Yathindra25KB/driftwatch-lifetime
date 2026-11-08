# References: status of the open items

`paper/references.bib` holds 36 entries. Each was built from the arXiv or Crossref record named by its identifier and is re-resolved by `scripts/check_bib.py`. Never add an entry by hand from memory: fetch the record, then run the script.

The items below were re-checked on 8 Nov 2026 against primary sources (evidence and URLs: `reports/source_verification_2026-11-08.md`, CLAIMS L-34, L-35). Two things remain open and need a person.

## Resolved on 8 Nov 2026

| Item | Result |
|---|---|
| Transcend (USENIX Security 2017, pp. 625 to 642) and CADE (USENIX Security 2021, pp. 2327 to 2344) | Confirmed on the USENIX pages. They have no DOI or arXiv record, so they stay out of `references.bib` and are cited by their USENIX pages [L-12, L-13] |
| TESSERACT, USENIX Security 2019 | pp. 729 to 746; final PDF at usenix.org; arXiv v4 states that it corresponds to the published version. The bib keeps the arXiv identifier |
| ActDroid journal version | Computers & Security vol. 160, article 104724, DOI 10.1016/j.cose.2025.104724 (Crossref); title and four authors match the arXiv record, which lists the DOI as related. The bib cites the arXiv record |
| DREAM | Published: ACM CCS 2025, pp. 978 to 992, DOI 10.1145/3719027.3744792 |
| TIF | Published: IEEE Transactions on Software Engineering vol. 52 no. 8, pp. 2463 to 2474, DOI 10.1109/TSE.2026.3698484 |
| Botacin and Gomes | Computers & Security vol. 148, article 104122, DOI 10.1016/j.cose.2024.104122 (Crossref) |
| BODMAS labelling | Read in the paper, Section III: families from multi-vendor antivirus verdicts with in-house scripts (about 1% manual), first-seen time from VirusTotal reports; how the binary label was decided is not stated [CLAIMS D-18] |
| AndroZoo | Allix et al., MSR 2016, DOI 10.1145/2901739.2903508 (Crossref). AndroZoo is not used by this study |

## Still open

| Item | What is missing |
|---|---|
| Two-stage (cluster) bootstrap | Davison and Hinkley (1997) and Ren et al. (2010) are in the bibliography [L-34]; the book's section 3.8 was not read, so the statement that resampling both stages widens the interval stays unconfirmed |
| "Li et al. (NDSS 2025)" | Venue confirmed [L-33]. Plan Table G.1 lists "Li et al. (NDSS 2025)" among papers not re-read, with no title or arXiv number (read in the plan PDF on 8 Nov 2026), so `li2024revisiting` (the NDSS 2025 paper by Li et al. on concept drift in Windows malware detection) is an identification by author, venue and topic; only the researcher can confirm that it is the one intended |
| SEED, Minnei et al. and LAMDA | Re-checked on 8 Nov 2026 (CLAIMS L-39). SEED (arXiv 2605.24903 v2, 23 Jun 2026) and Minnei et al. (arXiv 2603.28396 v1, 30 Mar 2026, "submitted" to IEEE TIFS) have no final version that could be found and stay cited as preprints. LAMDA is an ICLR 2026 poster (24 Apr 2026) with no page range or DOI on the conference page and an OpenReview page that could not be read |
| (resolved 8 Nov 2026) FIRCE, Cerqueira et al., EMA | Now cited from their proceedings records with DOIs, which `check_bib.py` resolved against Crossref: FIRCE, SmartNets 2026, pp. 1 to 9; Cerqueira et al., KDD '26, pp. 8671 to 8682; EMA, ACM SIGCOMM 2026, pp. 1617 to 1629. The ACM and IEEE pages themselves returned 403 or could not be reached, so the data comes from Crossref and the conference programme pages [L-39] |

Note on AUT (resolved in ADR-0006 and CLAIMS M-02): TESSERACT arXiv v4 says the published Eq. (4) had an extra 1/N normalisation factor; the guide's 1/(N-1) form equals the numpy trapezoid and is pinned by `tests/test_aut.py`.
