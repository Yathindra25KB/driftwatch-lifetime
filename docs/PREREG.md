# DriftWatch pre-registration

**Status: UNLOCKED** (draft written in Phase 1; finalised and tagged `prereg-v1` in Phase 6, before the first grid result)

## How the lock works

1. This file is a draft until the researcher approves its final diff in Phase 6. Then the annotated git tag `prereg-v1` is created on the commit that contains it. The tag date must come before the first E2 result.
2. While any `prereg-v*` tag exists, the PreToolUse guard (`.claude/hooks/guard.py`) blocks every Edit or Write that would make this file differ from its content at the highest `prereg-v*` tag. It also blocks shell commands that would write to this file, and any deletion or move of a `prereg-v*` tag.
3. After the lock, changes go only into addendum files, `docs/prereg/addendum-vN.md`: v2 in Phase 8 (RQ3), v3 in Phase 9 (RQ4), v4 in Phase 10 (RQ5 replication). Each addendum is locked in the same way once its tag `prereg-vN` exists.
4. Provenance is the tag, not this text: `git show prereg-v1:docs/PREREG.md` is the registered version.

Hypotheses are the build guide's (§5). The primary metrics, contrasts and decision rules come from the implementation plan, Appendix D. Values marked **TBD (owner)** are filled before the tag and never by looking at results.

## Research questions

| RQ | Hypothesis (a target to test, not a known result) | Primary metric and contrasts | Analysis and decision rule | Tag |
|---|---|---|---|---|
| RQ1 | A large gap between random-split F1 and time-aware AUT(F1), mostly from temporal leakage in the random split. | Gap = random-split F1 minus AUT(F1), same data, same C3 ratio, per model and dataset. | Report the gap with a 95% window-first bootstrap interval. Judge "large" against a band fixed in advance: **0.05** [estimate; confirm before tag]. | v1 |
| RQ2 | AUT falls roughly steadily with delay and rises with budget with diminishing returns. | A-AUT. Contrasts: d = 0 vs d = 3 at B = 1% and 5% (periodic); periodic at 5% vs never; the budget curve 0.5% to 5%. | Effect sizes (AUT lost per slot of delay, AUT gained per extra label) with intervals; Wilcoxon signed-rank on 10 seeds only as a supporting check; no single-cell claims. | v1 |
| RQ3 | The advantage of uncertainty or credibility selection over random selection shrinks as delay grows. | Difference in AUT from random selection at equal labels spent; selector-by-delay interaction; reserved-slice ablation. | Interaction estimate with interval; report it if no advantage exists at any delay. | v2 |
| RQ4 | Periodic retraining is a hard baseline; monitors may fail to beat it. | AUT at matched labels spent and at matched retrain count; alarm precision, alarm recall and detection delay. | Frozen thresholds; report all monitors; a negative result is a result. | v3 |
| RQ5 | Directions agree across platforms; magnitudes differ. | Sign agreement and ratio of effect sizes across LAMDA and BODMAS for the pre-registered contrasts. | Descriptive comparison with intervals; no pooled significance claim. | v1 (E2), v4 (E5) |

## Fixed before any run (to complete before `prereg-v1`)

| Item | Value | Owner |
|---|---|---|
| Seeds | 5 for the grid; 10 for headline contrasts (guide §10). Seed values: TBD | Phase 6 |
| A-AUT windows per dataset (nT, nE, stride) | TBD | ADR-0005 (Phase 3) |
| Malware ratio | 10% target; one sensitivity ratio: TBD | ADR-0005 (Phase 3) |
| Slot length, minimum-size gate, gap handling | TBD | ADR-0004 (Phase 2) |
| Decision threshold, scaling policy, A-AUT window formula | TBD (default fixed 0.5) | ADR-0006 (Phase 4) |
| Model hyperparameters (LR; LightGBM fast profile) | TBD; recorded here before E0 runs | Phase 4 |
| Training-pool design (new-label weight, windowing) | TBD | ADR-0007 (Phase 5) |
| Grid | delay {0,1,2,3}; budget {0.5,1,2,5}% of the evaluated slot; policies never and periodic(3); LR and LightGBM; both datasets | Phase 6 |
| Exclusion rules | TBD | Phase 6 |
| Failure rule | Failures are logged with their reason, never silently rerun; no cell is dropped, rerun or re-seeded because its result looks wrong. | fixed |
| Shrink order if a fit exceeds 60 s | delay 2, budget 0.5%, windows, seeds on non-headline cells (shrink the grid before the claim) | fixed |
