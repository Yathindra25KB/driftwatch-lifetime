# DriftWatch protocol: single source of truth

Every protocol constant lives here and nowhere else. Code, configs, chapters and the paper refer to this file.

- **Source:** *DriftWatch Build Guide, revision 2* (6 Oct 2026), `docs/source/DriftWatch_Build_Guide_v2.pdf`. Sections 1–5 copy section 6 (pages 6–7) value for value, including the guide's own tags. Section 4 adds definitions from other guide sections and names each source section.
- **Changing a value** needs an ADR in `docs/DECISIONS/`. After `prereg-v1` it also needs a pre-registration addendum. Values still open are listed in section 5 together with the phase and ADR that will fix them.
- **Differences and ambiguities** between the guide, the implementation plan and the phase prompts are listed in section 6. None of them is resolved silently here.

## 1. Datasets (guide §6, p. 6)

| Dataset | Platform and period | Size | Licence | Use in this study |
|---|---|---|---|---|
| LAMDA (Hugging Face: IQSeC-Lab/LAMDA) | Android, 2013 to 2025 (no 2015) | 1,008,381 apps, about 37% malware, 1,380 families, Drebin-style features | MIT | Primary Android data. Use yearly or monthly slices of the sparse feature matrix. |
| BODMAS | Windows PE, Aug 2019 to Sep 2020 | 57,293 malware and 77,142 benign, 2,381-dimension EMBER-style features, 581 families | BSD-2-Clause | Primary PE data for Tier 1. Short time span, so slots are short. |
| EMBER2024 | Win32, Win64, .NET, APK, ELF and PDF; Sep 2023 to Dec 2024 | 3,238,315 files; train weeks 1 to 52, test weeks 53 to 64; 24.3 GB | Apache-2.0 | Tier 3 only: a Win32 subset by week, plus the challenge set for delay evidence. |
| AndroZoo | Android, all years | Over 23.9 million APKs; metadata useful for sampling | Academic key, no redistribution | Optional. Needs a faculty commitment. Avoid bulk APK processing. |

> Guide box, verbatim in substance: **[verify] before you design slots.** The audit could not confirm whether LAMDA carries month-level timestamps or what its feature dimension is, nor the exact file layout of EMBER2024 subsets. Week-1 task: inspect each dataset's timestamp granularity, feature count, sparsity and size on disk. The slot length (month, two weeks, week) follows from that, not the other way round.

## 2. Protocol: identical for every experiment (guide §6, pp. 6–7)

| Constant | Value (guide wording) | ID used in code and configs |
|---|---|---|
| Slots | Divide time into equal slots by first-seen date. | `slots` |
| Initial training window | Train on the first K slots, **K = 3 to 4**, then step through the rest one slot at a time. | `window.nT` (see D1) |
| C1 | Never train on the future. | `constraints.c1` |
| C2 | Evaluate each slot using only samples from that slot. | `constraints.c2` |
| C3 | Subsample malware to a fixed ratio: **start with 10%**, and run **one sensitivity check at another ratio**. | `ratio.target = 0.10`, `ratio.sensitivity` (see D4) |
| Label delay | A sample queried in slot t is usable for training from slot **t+1+d**. Test **d ∈ {0, 1, 2, 3} slots**. | `delay` |
| Budget | A fixed number of queries per slot, set as a percentage of the slot: **0.5%, 1%, 2%, 5%**. Report both the percentage and the absolute count. | `budget_pct`, `budget_n` (see D3) |
| Policies | **never** (train once), **periodic** (retrain **every 3 slots**) and **monitor-triggered** (retrain when the monitor alarms). Retraining uses only labels that have arrived. | `policy.name`, `policy.period = 3` |
| Selection | **random**, **uncertainty** (closest to 0.5), **credibility** (lowest conformal p-value). Reserve a random slice for calibration. | `selector.name`, `selector.calibration_fraction` (see D8) |
| Models | Logistic regression and LightGBM [verify the LightGBM install on your machine]. Add a small MLP only in Tier 3. | `model.name` |

## 3. Metrics (guide §6, p. 7)

| Metric | Definition | Why (guide) |
|---|---|---|
| AUT(F1) | Trapezoidal area over per-slot F1 of the malware class | Headline number, comparable with the literature |
| A-AUT | Mean and standard deviation of AUT over rolling windows | Matches current practice (Chow et al.) |
| FPR and FNR per slot | At a fixed decision threshold | F1 alone hides the benign-flagging cost analysts care about |
| Labels spent | Total queries used | Compare methods at equal analyst cost |
| Recovery time | Slots until F1 returns to **90%** of its pre-drop level after a drop event | Operational meaning of "works" |
| Monitor quality (Tier 2) | Alarm precision, alarm recall and detection delay against drop events defined from true labels (for example a fall of **at least 0.05 below the trailing 3-slot mean**). True labels are used only for scoring, never for the monitor. | Scores monitors the way arXiv 2606.07789 scores drift detectors |

## 4. Supporting definitions from other guide sections

These are not in section 6, but section 6 depends on them. Each row names its source section.

| Item | Value | Source |
|---|---|---|
| C1 Temporal training consistency | Every training sample is older than every test sample. Split by first-seen date, never randomly. | §3, p. 3 |
| C2 Temporal window consistency | In each test slot, malware and goodware come from the same time window. Evaluate slot by slot with both classes from that slot. | §3, p. 3 |
| C3 Realistic ratio | The test set reflects the in-the-wild malware share; TESSERACT used 10% malware for Android. Subsample malware to a stated ratio; report a sensitivity check. | §3, p. 3 |
| AUT formula | `AUT(f, N) = 1/(N-1) * sum_{k=1..N-1} (f_k + f_{k+1}) / 2`; 1.0 means no decay at all. | §3, p. 4 |
| A-AUT | (mean AUT, std of AUT) over rolling train/test windows; must be used to compare detectors (Chow et al., arXiv 2506.23814). | §3, p. 4 |
| Label delay d | A sample queried in slot t gets its true label only in time to be used for training from slot t+1+d; d = 0 means the next slot. | §3, p. 4 |
| Analyst budget B | A fixed number (or percentage) of samples per slot an analyst can label. | §3, p. 4 |
| Mondrian p-value | `p_c(x) = (1 + #{calibration samples i with label c and s_i >= s_c(x)}) / (n_c + 1)` | §5, p. 6 |
| Credibility | `credibility(x) = p_{predicted class}(x)`; low credibility means x looks unlike what the model knows. | §5, p. 6 |
| Nonconformity score | A research variable, e.g. 1 minus the model probability, or distance to a class centroid in feature space. | §5, p. 6 |
| Calibration slice | A small random slice of each slot's budget reserved for calibration (20% in the sandbox); its size is itself a question for one ablation. | §5, p. 6 |
| Seeds | 5 seeds for the whole grid; 10 seeds for the headline comparisons (a two-sided Wilcoxon on 5 paired seeds cannot go below p = 0.0625). | §10, p. 10 |
| Uncertainty reporting | Effect sizes with bootstrap confidence intervals over slots and seeds; Wilcoxon only as a supporting check; A-AUT as mean and std plus per-slot curves. | §10, p. 10 |
| Fit-time rule | If a fit takes more than 60 seconds, shrink the grid before you shrink the claim. | §9, p. 9 (E2) |
| Leakage warning | Treat any AUT above 0.9 on a hard split as a possible leakage warning. | §9, p. 9 |
| Leakage canary | Shuffle timestamps and confirm AUT jumps toward the random-split number. | §8, p. 9 |
| Reproducibility | One config file per run; log config hash, package versions and seeds with every result row; store raw per-slot predictions; pin a lock file; one-command reproduction of Table 1 on BODMAS. | §8, p. 9 |
| Monitors | KS on top features, MMD on embeddings, domain-classifier AUC, KS of p-values; one alarm interface. | §8, p. 8 |
| Stop rules | Week 4 (time-aware baseline), week 8 (simulator end to end), week 14 (Tier 1 + core chapters), hour check (under 5 h/week for four weeks in a row). | §1, p. 2 |

## 5. Open values (fixed later by ADR, never by looking at results)

| Value | Fixed in | Record |
|---|---|---|
| Slot length per dataset, minimum-size gate, gap handling | Phase 2 | ADR-0004-slot-definition |
| nT, nE, stride per dataset; size-gate numbers; ratio policy incl. the sensitivity ratio | Phase 3 | ADR-0005-windows-and-size-gate |
| Decision threshold (default fixed 0.5 per Phase 4 prompt), scaling policy, A-AUT window formula | Phase 4 | ADR-0006-metrics-threshold-scaling |
| Training-pool composition, new-label weight, budget base | Phase 5 | ADR-0007-pool-composition-and-budget |
| Model hyperparameters, seeds, windows, exclusion rules | before E0 / Phase 6 | docs/PREREG.md, tag prereg-v1 |

## 6. Differences and ambiguities (listed, not resolved)

| ID | Where | What does not line up | Owner |
|---|---|---|---|
| D1 | Guide §6 vs plan §3 item 5 | §6 trains once on the first K = 3–4 slots and then steps through the rest. A-AUT needs rolling train/test windows. The plan turns each rolling window into an independent simulation (nT = K, nE, stride). | Phase 3 ADR |
| D2 | Guide §6 vs §2 | §6 measures delay in **slots** (d ∈ {0,1,2,3}). §2 promises "how much AUT(F1) you lose per **month** of label delay", and §3 motivates 1–3 months from the EMBER2024 challenge set. If BODMAS slots are weeks, a slot is not a month. | Phase 2 ADR, Phase 6 reporting |
| D3 | Guide §6 vs Phase 5 prompt | Budget is a "percentage of the slot" (§6) or "of the evaluated slot" (Phase 5). Not stated: whether the base is counted before or after C3 malware subsampling. | Phase 5 ADR |
| D4 | Guide §6 | "One sensitivity check at another ratio": the second ratio is not given. | Phase 3 ADR |
| D5 | Guide §6 vs Phase 4 prompt | §6 says only "a fixed decision threshold". The value 0.5 and the rule that a tuned threshold may use only the final training slot come from the Phase 4 prompt. | Phase 4 ADR |
| D6 | Guide §6 | Recovery time refers to "a drop event", but a drop event is defined only under monitor quality, and only "for example" (0.05 below the trailing 3-slot mean). The Phase 9 prompt makes that definition firm for monitor scoring. Whether recovery time uses the same definition is unstated. | Phase 4 ADR |
| D7 | Guide §6 | "Retrain every 3 slots": the anchor (window start vs first evaluation slot) is unstated. | Phase 5 |
| D8 | Guide §5, §6 vs plan §3 item 6 | The 20% calibration slice is a sandbox value. The plan sets it as default 20% and ablates {0, 10, 20, 40}% [estimate]. | Phase 8 addendum |
| D9 | Guide §6 box vs plan §3 item 7 | The guide marks LAMDA's timestamp granularity and feature dimension [verify]. The plan reports year_month, 4,561 int8 features, no 2015 and a provided 80/20 split to ignore [verified by the plan]. | Phase 2 re-measures |
| D10 | Guide §6 vs plan §3 item 11 | BODMAS "Aug 2019 to Sep 2020" is described as about 13 months, but can be up to 14. | Phase 2 re-measures |
| D11 | Phase 1 prompt vs guide §8, plan App. C, Phases 7 and 12 | The prompt lists `cli` among the empty packages. The guide's map has no `cli`; plan App. C and later prompts name `src/driftwatch/cli.py`. Implemented as the module `cli.py` (a `cli/` package would collide with later paths). | Phase 1 (recorded in PHASES.md) |
| D12 | Guide §8 vs Phase 1 prompt | The guide shows `driftwatch/` at the repo root. The prompt requires src layout (`src/driftwatch/`). Implemented as src layout. | Phase 1 |
| D13 | Guide §6 | Slots are cut by "first-seen date", but the datasets may carry other timestamp types (compile time, collection time; Chow et al. bias factor). | Phase 2 data cards |
| D14 | Plan §4.3, Phase 2 prompt vs Phase 1 prompt rev 1.2 | The plan assumes a 16 GB laptop and a 6 GB peak cap. The machine has 8 GB (7.2 GB usable); rev 1.2 overrides. Each affected place is listed in docs/PHASES.md. | Phase 2 cap proposal |
| D15 | Guide §8 vs plan App. C, phase prompts | Config names: `configs/tier1_bodmas.yaml` (guide) vs `configs/e0_*.yaml` … `e5_*.yaml` (plan, prompts). The prompts' names are used. | Phase 4 onward |
| D16 | Guide §6 vs Phase 10 prompt | The guide allows a small MLP in Tier 3; the Phase 10 prompt has no MLP (E5/E6 only). | Phase 10 |
| D17 | Guide §3 AUT formula vs TESSERACT arXiv v4 | The arXiv v4 comment (arxiv.org/abs/1807.07838, accessed 2026-10-10) says the published Eq. (4) had an extra 1/N normalisation factor. The guide's `1/(N-1)` form should be checked against v4. | Phase 4 ADR-0006 |

## 7. Phase 2 measurements against open differences (no value changed here)

| ID | Measured (10 Oct 2026) | Evidence |
|---|---|---|
| D2 | Delay units: LAMDA slot = 1 month; BODMAS proposed slot = 14 days | ADR-0004 (PROPOSED) |
| D9 | LAMDA: 4,561 int8 features (counts 0-17); `year_month` derives from AndroZoo `added` (second resolution); no 2015 rows, and the empty run is 2014-09..2016-01; the provided 80/20 split is pooled | reports/data_inventory.md, CLAIMS D-02..D-04 |
| D10 | BODMAS malware spans 2019-08-29..2020-09-30 (58 ISO weeks); benign timestamps reach back to 2007 | CLAIMS D-08 |
| D13 | LAMDA time = AndroZoo collection date (`added`); BODMAS time = "first appeared" (malware) but benign dates are mostly date-only or placeholders | docs/data_cards/, reports/data_inventory_notes.md Q1-Q2 |
| D14 | Peak-memory cap 1.5 GB approved by the researcher; LAMDA build peak 0.85 GB, BODMAS 0.55 GB | CLAIMS D-06, D-09 |
