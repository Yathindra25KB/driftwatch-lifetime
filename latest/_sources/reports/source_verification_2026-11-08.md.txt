# Verification findings (access date 2026-11-08)

Method: WebFetch/WebSearch only. Repo not edited. No dataset or malware file touched. Crossref via WebFetch (the repo guard blocked curl to api.crossref.org, so I did not use curl; some Crossref calls returned HTTP 429 and were retried).
One Python helper (pypdf, installed in the scratchpad only) was used to read the BODMAS paper PDF and the arXiv 2303.04880 PDF; extracted text is in scratchpad (bodmas.txt, icc.txt).
Marker: [read] = I read the primary source; [snippet] = search-result summary only; unconfirmed = could not read.

## 1. BODMAS label provenance

Primary source READ: Yang, Ciptadi, Laziuk, Ahmadzadeh, Wang, "BODMAS: An Open Dataset for Learning based Temporal Analysis of PE Malware", 2021 IEEE Security and Privacy Workshops (SPW), pp. 78-84, DOI 10.1109/SPW53761.2021.00020 (Crossref-confirmed, matches the bib entry yang2021bodmas).
Full text read from https://gangw.cs.illinois.edu/DLS21_BODMAS.pdf (author-hosted, 7 pages) [read]. Other copies: https://par.nsf.gov/servlets/purl/10232928 and https://conferences.computer.org/sp/pdfs/spw/2021/893400a078.pdf (both unreachable from here: ECONNREFUSED / DNS fail).

Paper, Section III "Dataset Description" [read]:
- Malware source: "randomly sampled each month from a security company's internal malware database" (collected 29 Aug 2019 to 30 Sep 2020). Security company = Blue Hexagon (author affiliation).
- Benign source: "Benign samples are also selected from the security company's database" (collected 1 Jan 2007 to 30 Sep 2020), to "represent benign PE binary distribution in real world traffic".
- Label statement: "we provide the ground-truth label ("malware" or "benign"), curated malware family information, and the first-seen time of a sample based on VirusTotal reports [1]."
  Careful reading: "based on VirusTotal reports" attaches syntactically to the first-seen time. The paper does NOT state how the binary malware/benign ground-truth label was decided (no VirusTotal threshold, no AV-vote rule is given).
- Family labels: "The family label is obtained mostly by analyzing verdicts from multiple antivirus vendors with in-house scripts (similar as AVClass [26])."
  "The in-house scripts are constantly curated and updated by our threat team."
  "A small portion (about 1%) of malware were labeled via manual analysis of the binaries."
  Abstract/Intro: family labels "curated by security analysts", 581 families; 14 malware categories (Trojan 29,972; Worm 16,697; Backdoor 7,331; Downloader 1,031; Ransomware 821).
- So: families came from multi-AV-vendor verdict analysis with in-house scripts (AVClass-like, not AVClass itself), about 1% manual. VirusTotal is named as the source of first-seen time. Binary label provenance: unconfirmed (paper only says "ground-truth label").
- Ember comparison in paper: Ember "family tags are not curated ... incorrectly parsed from VirusTotal reports" (Sec. II).
- Licence in paper: none stated [read]. The only release statement: benign binaries not included "due to copyright considerations". The paper has no licence section.

Repo https://github.com/whyisyoung/BODMAS [read via WebFetch]: states 57,293 malware and 77,142 benign files, "disarmed malware only"; names a "BSD 2-Clause "Simplified" License" for the repository. Says nothing on how labels/families were obtained (no VirusTotal/AVClass mention). No separate dataset terms on that page.
Project page https://whyisyoung.github.io/BODMAS [read]: https://bodmas.github.io returns HTTP 404. The github.io page: y is "labels, 0 as benign, 1 as malicious"; "If the malware family is empty, then it's a benign sample"; family info "carefully curated" (no method); feature vectors and metadata "open to everyone" (Google Drive). No licence named for the dataset on that page. Binaries only on request: "Do not share the data with others, except your co-authors"; academics need institutional email plus university webpage; industry needs a justification letter. Benign binaries not released (copyright). Contact: a 2023 update names Pirouz Naghavi (Gang Wang cc'd); a search snippet says it was later redirected to Zhi Chen (unconfirmed, not seen on the page I read).
Third party: Hugging Face card https://huggingface.co/datasets/it4lia/BODMAS_cleaned/blob/main/README.md says "The original BODMAS data files are associated with the BSD-2 License" (a derivative card, not authoritative).
Implication for docs/data_cards/bodmas.md: licence = BSD-2 on the GitHub repo (verified); the paper and project page state no dataset licence; label provenance = family labels by multi-AV analysis with in-house AVClass-like scripts (about 1% manual), binary label basis not described (mark [verify]); the project-page note "labels were not described" in REFERENCES_TODO is now answerable from the paper Sec. III.

## 2. Two-stage / cluster bootstrap references

Crossref/IDEAS/Wiley-indexed data, all [read]:

| Ref | Verified record | Source |
|---|---|---|
| Davison and Hinkley (1997), Bootstrap Methods and their Application | Cambridge University Press, DOI 10.1017/CBO9780511802843, monograph, ISBNs 9780521573917 / 9780521574716 / 9780511802843. Section 3.8 is "Hierarchical data" (confirmed only via a snippet; see below). | https://api.crossref.org/works?query.bibliographic=Davison+Hinkley+Bootstrap+Methods+and+their+Application+1997+Cambridge |
| Field and Welsh (2007), Bootstrapping Clustered Data | J. Royal Statistical Society Series B 69(3), 369-390, DOI 10.1111/j.1467-9868.2007.00593.x | https://api.crossref.org/works/10.1111/j.1467-9868.2007.00593.x |
| Ren, Lai, Tong, Aminzadeh, Hou, Lai (2010), Nonparametric bootstrapping for hierarchical data | Journal of Applied Statistics 37(9), 1487-1498, DOI 10.1080/02664760903046102 (note the author order and the six names; Crossref query result) | Crossref query above; also https://ideas.repec.org/a/taf/japsta/v37y2010i9p1487-1498.html |

What each actually says (only what I could read):
- Field and Welsh 2007 (abstract only; full text not read): examines bootstrap for one-way clustered data; finds "the cluster bootstrap" consistent for variance estimates under both the transformation model and the random-effect model, and the residual bootstrap consistent under the transformation model; criteria based on the distribution of bootstrap observations "not very useful". The abstract does not mention a two-stage bootstrap or that resampling at both stages overstates the variance. Full-text PDF mirror (bemlar.ism.ac.jp) was unreachable. Support for the DriftWatch statement: UNCONFIRMED from what I could read.
- Ren et al. 2010 (abstract via EconPapers/IDEAS, full text paywalled): simple resampling that treats all observations as independent is inappropriate for hierarchical data; they "proved that the strategy of nonparametric bootstrapping on the highest level" is better than bootstrapping at lower levels, i.e. resample the highest-level units with replacement and lower-level units without replacement within each selected top unit. This is the closest read statement: it supports "resample whole blocks, do not also resample rows with replacement", but the abstract does not say "double counts / overstates variance" in those words.
- Davison and Hinkley sect. 3.8: a snippet from a scanned copy (Scribd; I did not open it because the fetch was denied as a pirated copy) describes Strategy 1 (sample groups with replacement, second stage without replacement = keep groups intact) and Strategy 2 (second stage with replacement). The "Strategy 2 variance is too large" claim was NOT confirmed by any source I could read. I recall that the book makes this point (p. 100-101 area) but that is from memory, so treat as [verify] against the book itself.
- Secondary source READ (arXiv 2303.04880, Rank Intraclass Correlation for Clustered Data, text extracted): "the two-stage bootstrap (Davison and Hinkley, 1997; Field and Welsh, 2007)"; says intra-cluster sampling "can cause positive bias" in estimating the intraclass correlation "because the same observation may be sampled twice". This is about ICC bias, not the variance of a mean; do not cite it for the DriftWatch statement.
- Recommendation: cite Davison and Hinkley (1997) sect. 3.8 for the two strategies and Ren et al. (2010) for "highest-level resampling is better than resampling at lower levels", and word the claim as "resampling windows only (rows kept intact) is the cluster bootstrap; additionally resampling rows within windows is the two-stage bootstrap, which Davison and Hinkley and Field and Welsh discuss" with the variance-inflation clause marked [verify] until the book page is read by the researcher.

## 3. paper/REFERENCES_TODO.md open rows

| Row | Resolved data | Source URL | Status |
|---|---|---|---|
| Transcend (USENIX Security 2017) | Jordaney, Sharad, Dash, Wang, Papini, Nouretdinov, Cavallaro. "Transcend: Detecting Concept Drift in Malware Classification Models". 26th USENIX Security Symposium (2017), pp. 625-642. PDF https://www.usenix.org/system/files/conference/usenixsecurity17/sec17-jordaney.pdf | https://www.usenix.org/conference/usenixsecurity17/technical-sessions/presentation/jordaney | resolved (USENIX page read); no DOI exists on the page |
| CADE (USENIX Security 2021) | Yang, Guo, Hao, Ciptadi, Ahmadzadeh, Xing, Wang. "CADE: Detecting and Explaining Concept Drift Samples for Security Applications". 30th USENIX Security Symposium (2021), pp. 2327-2344. PDF https://www.usenix.org/system/files/sec21-yang-limin.pdf | https://www.usenix.org/conference/usenixsecurity21/presentation/yang-limin | resolved |
| Li et al. (NDSS 2025) | Adrian Shuai Li, Arun Iyengar, Ashish Kundu, Elisa Bertino, "Revisiting Concept Drift in Windows Malware Detection: Adaptation to Real Drifted Malware with Minimal Samples". Listed on the NDSS Symposium 2025 accepted-papers page (exact title match). The paper page shows no DOI or pages; PDF https://www.ndss-symposium.org/wp-content/uploads/2025-830-paper.pdf. The NDSS page does not itself state the year (filename suggests 2025). Whether this is the paper meant by plan Table G.1 is the researcher's call, not checkable from sources. | https://www.ndss-symposium.org/ndss-paper/revisiting-concept-drift-in-windows-malware-detection-adaptation-to-real-drifted-malware-with-minimal-samples/ and https://www.ndss-symposium.org/ndss2025/accepted-papers/ | venue confirmed; no DOI/pages (unconfirmed); keep arXiv 2407.13918 as the bib key target |
| TESSERACT USENIX Sec 2019 | Pendlebury, Pierazzi, Jordaney, Kinder, Cavallaro. 28th USENIX Security Symposium (2019), pp. 729-746. URL https://www.usenix.org/conference/usenixsecurity19/presentation/pendlebury ; final PDF https://www.usenix.org/system/files/sec19-pendlebury.pdf. arXiv 1807.07838 v4 (12 Sep 2019) comment: "corresponds to the one published at USENIX Security Symposium 2019" with fixed Eq. (4). | USENIX page; https://arxiv.org/abs/1807.07838 | resolved; add url and pages=729--746 |
| ActDroid journal version | Crossref: Muzaffar, Ragab Hassen, Zantout, Lones, "ActDroid: An active learning framework for android malware detection", Computers & Security vol. 160, article 104724, DOI 10.1016/j.cose.2025.104724, online 2025-10-23, print issue Jan 2026. Same title and authors as arXiv 2401.16982; arXiv page lists this DOI as "Related DOI". | https://api.crossref.org/works/10.1016/j.cose.2025.104724 ; https://arxiv.org/abs/2401.16982 | resolved (title and four authors match; contents not diffed, so "same work" rests on arXiv linking it) |
| LAMDA at ICLR 2026 | ICLR 2026 poster, Fri 24 Apr 2026; page lists the 7 authors; OpenReview forum https://openreview.net/forum?id=1FnCrZtBNQ (the OpenReview page itself showed a bot check, not read). The dataset's Hugging Face card gives BibTeX inproceedings key haque2026lamda, "14th International Conference on Learning Representations (ICLR)", year 2026. | https://iclr.cc/virtual/2026/poster/10011850 ; https://huggingface.co/datasets/PtaSack/LAMDA/blob/main/README.md | partly resolved: no page range or DOI exists in what I read; OpenReview entry unconfirmed |
| SEED | arXiv 2605.24903 v2 (23 Jun 2026): Amalapuram, Shresta, Chebiyam, Tamma, Channappayya. No Comments, no journal-ref, no venue. Title is stylised "SEED: Semi-supervised Continual MalwarE Detection for Tackling ConcEpt Drift on a BuDget". | https://arxiv.org/abs/2605.24903 | no final venue found |
| FIRCE | arXiv 2605.01962: Barrett, Li, Dorai, Rajaganapathy. Comments: "9 pages, 4 algorithms, 3 tables, 1 figure, accepted by IEEE SmartNets26". No journal-ref, no DOI beyond arXiv. | https://arxiv.org/abs/2605.01962 | venue per arXiv comment only; proceedings entry unconfirmed |
| Cerqueira et al. | arXiv 2606.07789 v1 (5 Jun 2026): Cerqueira, Gomes, Heyden, Pfahringer, Bifet. Comments: "Accepted in KDD'26". No proceedings/DOI found (search found none). | https://arxiv.org/abs/2606.07789 | KDD'26 per arXiv comment; proceedings entry unconfirmed |
| Minnei et al. | arXiv 2603.28396 v1 (30 Mar 2026). Comments: "Submitted to IEEE Transactions on Information Forensics and Security". Not accepted per the page; the bib has no venue note, so do not cite it as published. | https://arxiv.org/abs/2603.28396 | still preprint |
| EMA | arXiv 2605.13942 v1 (13 May 2026): Yu, Chen, Zhang, Liang, Qiao, Fan Lai. Comments: "SIGCOMM (2026)". A researchr listing and a search summary say SIGCOMM 2026, Denver, 17-21 Aug 2026 (second-hand). No DOI/pages found; dblp was blocked by bot protection. | https://arxiv.org/abs/2605.13942 ; https://researchr.org/publication/YuCZLQL26/authors | venue per arXiv comment; proceedings entry unconfirmed |
| DREAM | Published: He, Lei, Qin, Ren, Chen, "Combating Concept Drift with Explanatory Detection and Adaptation for Android Malware Classification", Proc. 2025 ACM SIGSAC CCS, pp. 978-992, DOI 10.1145/3719027.3744792, issued 2025-11-19. arXiv 2405.04095 v3 lists the same DOI. | https://api.crossref.org/works/10.1145/3719027.3744792 | resolved: final version with DOI and pages |
| TIF | Published: Zheng, Yang, Ngai, Jana, Cavallaro, "TIF: Learning Temporal Invariance in Android Malware Detectors", IEEE Transactions on Software Engineering vol. 52 no. 8, pp. 2463-2474, DOI 10.1109/TSE.2026.3698484, Aug 2026. | https://api.crossref.org/works/10.1109/TSE.2026.3698484 (also https://discovery.ucl.ac.uk/id/eprint/10228400 per search snippet) | resolved |
| Botacin and Gomes | Crossref: "Towards more realistic evaluations: The impact of label delays in malware detection pipelines", Computers & Security vol. 148, article 104122, DOI 10.1016/j.cose.2024.104122, Jan 2025. Matches the bib entry. Publisher page itself not retried (403 earlier); Crossref suffices for the bib. | https://api.crossref.org/works/10.1016/j.cose.2024.104122 | resolved via Crossref |
| BODMAS labelling | See section 1: families from multi-AV verdict analysis with in-house AVClass-like scripts (~1% manual); first-seen time from VirusTotal; binary label basis not described. | https://gangw.cs.illinois.edu/DLS21_BODMAS.pdf | resolved (with the binary-label gap noted) |
| AndroZoo citation | Allix, Bissyande, Klein, Le Traon, "AndroZoo: Collecting Millions of Android Apps for the Research Community", Proc. 13th International Conference on Mining Software Repositories (MSR 2016), pp. 468-471, DOI 10.1145/2901739.2903508 (Crossref-confirmed). That the AndroZoo site asks users to cite this paper comes from a search summary only: androzoo.uni.lu was unreachable (ECONNREFUSED). | https://api.crossref.org/works/10.1145/2901739.2903508 | bibliographic data confirmed; maintainers' request "unconfirmed" (site unreachable) |

Other bib notes spotted while checking:
- Bib entry haque2025lamda note says "Presented at ICLR 2026 (poster page iclr.cc/virtual/2026/poster/10011850)": consistent with the ICLR page.
- ADD to TODO closure: DREAM and TIF are no longer "if published": both are published (above); EMA, FIRCE, Cerqueira remain "accepted per arXiv comment"; Minnei is only "submitted".

## 4. Venue shortlist for docs/submission_checklist.md (today 2026-11-08)

All dates as stated on the official page; AoE = Anywhere on Earth. "Page limit" = what the page states.

| Venue | Current-cycle deadline | Page limit / format | Review | Source |
|---|---|---|---|---|
| DIMVA 2027 (Enschede, NL, 30 Jun - 2 Jul 2027) | Cycle 1: abstract 03 Dec 2026, paper "10 December 2026 (firm)", notification 28 Jan 2027. Cycle 2: abstract 11 Feb 2027, paper "18 February 2027 (firm)", notification 08 Apr 2027. Camera-ready 27 May 2027. Rejected Cycle 1 papers cannot go to Cycle 2. | "limited to 25 pages total": 18 main, 5 bibliography, 2 appendix. Springer LNCS template, no margin/font changes. | double-blind | http://www.dimva.org/dimva2027/ (home https://www.dimva.org/ confirms dates and place) |
| IEEE EuroS&P 2027 (Madrid, 5-9 Jul 2027) | Registration 25 Nov 2026, "Submissions deadline: 02 December 2026 (Wednesday)" AoE; early reject 28 Jan 2027; rebuttals 24 Feb - 01 Mar; notification 18 Mar 2027; camera-ready (tentative) 15 Apr 2027 | "13 pages of body text", unlimited references and appendices. LaTeX, A4, the IEEE conference template supplied on the site; other IEEE templates not allowed. | not read on the page (I did not extract the review policy) | https://eurosp2027.ieee-security.org/cfp.html |
| ARES 2027 (Venice, 24-27 Aug 2027) | unconfirmed: the site says "Call for Papers for ARES 2027 will be available soon." Prior year for planning only: ARES 2026 full-paper deadline 9 Mar 2026 (no extension), abstract 2 Mar 2026. | unconfirmed for 2027. ARES 2026: full paper max 22 pages including references, Springer LNCS, short 11, SoK 22, workshop 18 | unconfirmed | https://www.ares-conference.eu/ ; prior year https://www.ieee-security.org/Calendar/cfps/cfp-ARES2026.html |
| ACSAC 2027 | unconfirmed: the site shows only ACSAC 2026 (7-11 Dec 2026, Los Angeles). 2026 cycle (past): paper deadline "May 26 (23:59 AoE)" firm, notification Sep 8, camera-ready Oct 22. Use only as a pattern, not as a 2027 date. | ACSAC 2026: "no more than 11 double-column pages" plus up to 5 appendix pages, full PDF at most 16 pages; IEEEtran conference,compsoc, US letter | double-blind, two rounds (2026) | https://www.acsac.org/ ; https://www.acsac.org/2026/submissions/papers/ |
| AISec 2027 (ACM workshop at CCS) | unconfirmed: the site shows AISec 2026 only (19th, The Hague, 15 Nov 2026; deadline "July 24th, 2026 (firm)", passed). | AISec 2026: "at most 10 pages ... double-column ACM format" plus up to 2 pages of references/appendices; anonymised | double-blind (anonymised) | https://aisec.cc/ |
| IEEE SaTML 2027 (Reykjavik, 3-6 May 2027) | Past: abstract 22 Sep 2026, paper "Tue, Sep 29, 2026", artifacts 2 Oct 2026; early reject 4 Nov; notification 16 Dec 2026. The 2027 cycle is closed. 2028 cycle unconfirmed. Scope note: topics are trustworthy ML; papers that only use a dataset without engaging trustworthiness "may be desk rejected". | up to 12 pages body for research and SoK papers; references and appendices unlimited; two-column IEEEtran (conference), 10pt; anonymised | double-blind | https://satml.org/ ; https://satml.org/call-for-papers/ |
| RAID 2027 | unconfirmed: raid-symposium.org was unreachable (ECONNREFUSED) and a search found no RAID 2027 CFP. A search snippet says RAID 2026 was in Lancaster, UK, 10-14 Oct 2026 (second-hand). | unconfirmed | unconfirmed | none read |
| Computers & Security (Elsevier journal) | no deadline (journal); not confirmed from the official guide: ScienceDirect guide for authors returned HTTP 403. | unconfirmed. Note: the journal already published Botacin and Gomes (vol 148, 104122) and ActDroid (vol 160, 104724), so it is a close-topic venue. | unconfirmed | https://www.sciencedirect.com/journal/computers-and-security/publish/guide-for-authors (403) |
| IEEE S&P 2027 (main symposium, not requested) | A third-party aggregator (getpaperpilot.com) lists abstract 2026-11-10 and paper 2026-11-17; not confirmed on the official site, so unconfirmed. | unconfirmed | unconfirmed | https://www.getpaperpilot.com/deadlines/s-p-2027.html (third party) |

Practical read of the above (facts only): with a paper ready in this window, the two venues with confirmed open deadlines are EuroS&P 2027 (2 Dec 2026) and DIMVA 2027 (10 Dec 2026 or 18 Feb 2027). All other shortlist items are unconfirmed or already closed for the 2026-27 cycle.

## 5. LAMDA timestamp, platform threat figures, plan and guide (second check, 8 Nov 2026)

Pages were read through a summarising fetch tool, so wording is not verbatim and quotes should be checked before they are cited. The plan and guide PDFs (course documents, not in this repository) were read after extracting their text with PyMuPDF: the plan's Table G.1 note lists "Li et al. (NDSS 2025)" among papers "not re-read" with no title or arXiv number, and the guide's section 7 gives the sanity band (CLAIMS L-38).

### Notes of the page-reading agent

# verify2: LAMDA timestamp and threat-landscape figures (accessed 2026-11-08)

Note: pages were read through a fetch tool that summarises the page, so quotes are as returned by that tool; re-check before citing verbatim.

## 1. LAMDA timestamp column

### What the sources say
- HF dataset card (https://huggingface.co/datasets/IQSeC-Lab/LAMDA, raw README read too):
  - Column table lists `year_month` = "Timestamp in YYYY-MM format."
  - Other columns: hash (SHA256 index), label, family (AVClass2), vt_count, feat_0..feat_4560.
  - "Labeled malware if `vt_detection ≥ 4`"; "The dataset was created using ~1M APKs from AndroZoo".
  - Card gives NO derivation of year_month. No mention of added, dex_date, vt_scan_date, first seen, submission date.
- arXiv 2505.18551v1 (https://arxiv.org/html/2505.18551v1):
  - Sec 3, "Label Assignment and Collection Strategy": metadata "including APK hashes, VirusTotal (VT) results, and submission dates."
    (Ambiguous: not tied to the year_month column.)
  - "we collect APKs and assign binary labels using the vt_detection field."
  - Sec 3, Vectorization: "the first five columns represent metadata fields: hash, label, family, vt_count, and year_month."
  - Appendix L.2: "Metadata columns include: hash, label, family, vt_count, year_month".
  - Intro: 2015 excluded "due to the unavailability of hashes in the AndroZoo repository".
  - Appendix J.2: Domain-IL experience = "samples collected during a specific year." (year grouping)
  - The terms dex_date, vt_scan_date, "first seen", "added", timestamp: not found in the text I read (about first 100k chars plus chars 100k onward; read via summariser, not exhaustive).
- GitHub README (https://github.com/IQSeC-Lab/LAMDA; raw README.md read):
  - "YYYY = four digit of the year when the APK was added to AndroZoo repository" (describes the yearly npz file naming).
  - Step 1: "Download the latest dataset from AndroZoo: latest_with-added-date.csv.gz"
  - Metadata: "metadata containing binary label, family label, number of virus total flagged, year month and hash".
  - Monthly: "you might need to split yearly npz files into monthly npz file, if you want it."
  - Repo contains metadata.csv.gz, code/, scripts named AndroZoo-extractor.py, LAMDA_get_train_test.py, vectorization_npz_creation.py, download_dataset_and_convert_to_npz.py.
  - README does not say which timestamp yields the month.
- I could not open the code files: raw/blob URLs for code/AndroZoo-extractor.py returned 404 (path guess probably wrong). So the month derivation in code is UNCONFIRMED.
- AndroZoo's own page (androzoo.uni.lu, /lists) failed to load in the tool; AndroZoo column definitions are UNCONFIRMED by me.

### Verdict on CLAIMS D-03 ("added column = AndroZoo collection date")
- Partly supported at the YEAR level: README says the year in file names is when the APK "was added to AndroZoo", and the pipeline downloads AndroZoo's `latest_with-added-date.csv.gz` (so an "added"-type date exists in the source CSV).
- NOT confirmed for the month: no source I read says year_month is derived from the "added" column (or from dex_date / vt_scan_date). The HF card calls it only "Timestamp in YYYY-MM format".
- The paper's phrase "submission dates" could mean VT submission/scan date or AndroZoo added date; it is not resolved.
- Nothing I read contradicts D-03. Suggested wording: "year_month is LAMDA's timestamp; the README ties the yearly grouping to the date the APK was added to AndroZoo; the month derivation is not documented in the card or paper [verify in code/ or by asking the authors]."
- Also noted: the HF card names the column `year_month`; the repo data card says metadata.csv has `added`. The HF card and paper list `year_month`, not `added`, as the metadata column; check that the local file column name matches.

## 2. Threat-landscape figures

### (a) Android
- Kaspersky / Securelist, "Mobile threat report 2025" (https://securelist.com/mobile-threat-report-2025/119076, dated 04 Mar 2026):
  - "815,735 new unique installation packages were observed in 2025."
  - Page says the figure dropped "by nearly one-third" vs the previous year (no exact 2024 count in the text; it is in a chart image).
  - (A search snippet adds 255,090 new mobile banking-Trojan packages in 2025; I did not see it on the page I read: unconfirmed.)
  - These are "malicious and potentially unwanted" Android installation packages seen by Kaspersky; not a census.
- AV-TEST, "AV-TEST Security Report 2019/2020" news page (https://av-test.org/en/news/facts-analyses-on-the-threat-scenario-the-av-test-security-report-2019-2020/, dated 26 Aug 2020 per page):
  - Android new malware samples "in 2019 reaching the lowest level in three years with 3,170,140."
- AV-TEST 2022 Android figure: 1,073,866 new Android samples. I only saw this as a quotation of an AV-TEST post in a web-search result summary (originating from Neowin). Neowin returned HTTP 403 to me, so DIRECT READ UNCONFIRMED. The linuxsecurity.com article (https://linuxsecurity.com/news/security-trends/new-data-shows-constant-rise-of-new-malware-on-windows-linux-macos-and-android, 15 Jan 2023) confirms only rounded Windows/macOS/Linux figures, not Android.
- AV-TEST statistics page (https://www.av-test.org/en/statistics/malware/): yearly and per-platform values are in chart images (hosted on av-atlas.org), not in page text. Text says AV-TEST "registers over 450,000 new malicious programs (malware)" each day. No platform numbers readable as text.

### (b) Windows PE / Windows
- AV-TEST 2019/2020 news page (same URL as above): "over 78 percent of malware codes newly-developed by cybercriminals targeted Windows systems" (2019). The tool also reported a 2019 all-platform total of 114,312,703 new samples; I take that from the summariser, so re-check on the page before use. (The ~89 million Windows implied figure is my arithmetic, not a source number.)
- AV-TEST 2022: linuxsecurity.com (15 Jan 2023) says AV-TEST "had received almost 70 million new malware samples on Windows"; "only 12,000 new samples" for macOS; "2 million" for Linux. The precise 2022 Windows figure 69,504,686 was seen only via a search-result quotation of AV-TEST's post (Neowin), not read directly: unconfirmed.
  - Caution: that article says Windows is "over 60 times" Linux, which does not match its own 70M/2M (about 35x).
- Kaspersky Security Bulletin: attempted Kaspersky press-release page returned no per-day or per-platform malware-file figure. UNCONFIRMED for Kaspersky Windows/PE figures.
- Secondary only (not read on the page; do not cite without checking): a search summary cited Atlas VPN using AV-TEST data: 59.58 million new Windows samples in Q1-Q3 2022, 95.6% of new malware. Not verified.

### Gaps
- No AV-TEST annual figures for 2023-2025 found in text form.
- No AndroZoo growth figure retrieved (AndroZoo site failed to load).
- No Google Play Protect figure searched/verified.
- The AV-TEST dashboards (portal.av-atlas.org/malware) are charts; read them in a browser if exact per-year numbers are needed.

