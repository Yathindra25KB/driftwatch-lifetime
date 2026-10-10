# References still to verify

Phase 1 put into `paper/references.bib` only entries whose identifiers were fetched and checked on 2026-10-10. Everything below is [verify]: do not cite it until its identifier is confirmed, and never invent an entry.

| Item | What is missing | Where it came from |
|---|---|---|
| EMBER2024 dataset paper (Tier 3 only) | Paper identifier (arXiv or DOI) and author list | Build guide §6 (Hugging Face `joyce8/EMBER2024`) |
| TESSERACT, USENIX Security 2019 | Proceedings pages or URL (bib currently uses arXiv 1807.07838) | arXiv comment |
| Transcendent, IEEE S&P 2022 | DOI and pages; the authors publish an errata corrige | arXiv comment |
| Chen, Ding, Wagner, USENIX Security 2023 | Proceedings pages or URL | arXiv comment |
| ActDroid journal version | arXiv lists related DOI 10.1016/j.cose.2025.104724; confirm it is the same work before citing the journal version | arXiv page |
| LAMDA at ICLR 2026 | Formal proceedings entry (only the poster page and slides were found) | Web search, iclr.cc |
| SEED, FIRCE, Cerqueira et al., Minnei et al. | Final venue versions, if published | arXiv pages |
| AndroZoo | Citation the AndroZoo maintainers request (only if AndroZoo is ever used; currently excluded) | Build guide §6 |

Note for Phase 4 (AUT): TESSERACT arXiv v4 says the published Eq. (4) had an extra 1/N normalisation factor. Check the AUT formula in docs/PROTOCOL.md against v4 when writing ADR-0006.
