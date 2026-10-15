# ADR-0008: RQ1 primary comparator and the E2 grid design

**Status:** PROPOSED. The researcher chose the RQ1 comparator, the local sequential compute plan and the BODMAS geometry on 2026-10-15 (Phase 6 planning session). The remaining rules were proposed by Claude Code and take effect when this ADR is accepted together with the PREREG diff.
**Date:** 2026-10-15
**Deciders:** Yathindra (researcher, approves); Claude Code (engineering lead, proposes)
**Phase:** 6

## Context
- **Open decision A (reports/G2.md).** The same fitted comparator model scored two ways gives different RQ1 gaps on LAMDA: E0's window-level pooled comparator 0.152 (LR) and 0.137 (LightGBM); E1's per-slot matched comparator 0.029 and 0.040 (CLAIMS E-19). BODMAS: 0.028 and -0.000 against 0.035 and 0.006. The registered band is 0.05. Both numbers were seen before this ADR.
- **Open decision B (memory).** Two concurrent BODMAS runs crossed the 1.5 GiB cap; the E1 BODMAS run peaked at 98.2% of it (CLAIMS E-20).
- **BODMAS geometry.** nE = 6 with a 3-slot retrain period gives one useful refit per window (ADR-0007 consequences).
- **Review findings (second leakage pass, Phase 6).** No temporal leak. Feature-vector repeats between arrived labels and later slots were invisible to the initial-window-only count, and the grid driver needed run-identity hardening.

## Decision
1. **RQ1 primary comparator: the per-slot matched random-split series (E1).** It matches "same data, same C3 ratio" slot by slot. The E0 window-level gap stays in the table as the secondary reading. The choice was made after both numbers were seen and the reason is definitional, not the verdict: the per-slot series scores only evaluation-slot rows with C3 applied per slot, as the time-aware series does. Consequence: on LAMDA the registered 0.05 band is not reached by the E1 point estimates; the PREREG row reports that as it is. The sentence "mostly from temporal leakage" is not made (the comparator reaches a lower malware ratio on LAMDA, CLAIMS E-18). A stratified within-slot comparator was not built (new comparator, rerun, delays the tag); it is listed as future work.
2. **E2 grid design.** 27 runs per dataset (16 grid cells, 6 headline extra-seed cells, 4 Chow-stride cells, never once with seeds 0 to 9 and both window variants). Contrasts, units, interval method, decision rules and exclusion rules are in PREREG. Seeds 0 to 4 for the grid, 5 to 9 added for headline cells.
3. **Compute.** One run at a time on the laptop, about 10 to 11 hours of machine time in cost-balanced chunks of about one hour, resumable; Kaggle or Colab only by the same CLI and the same commit (docs/GRID.md), not used unless the researcher decides so later. The cap is not changed.
4. **BODMAS geometry kept** (ADR-0005). The delay axis there is a delay in one refit; this is a pre-registered limit, not a defect to repair after seeing results.
5. **Pool repeats.** Slot rows carry `n_seen_in_pool` next to `n_seen_in_initial_train`; the hashes stay inside the slot and the count is taken from the metric side. Repeats are reported, not removed.
6. **Grid run identity.** One code version per grid (read once, pinned, refused if HEAD moves); smoke events never complete a real cell; an adopted directory must be a finished run of that cell; the hashed output path is cell-relative; never must cover every seed and variant of every contrast.

## Consequences
- RQ1 will probably read as "gap below the band" on both datasets under the primary comparator; that is a result. The E0 reading stays visible so a reader can see the definition dependence.
- Delay contrasts on BODMAS are weak by construction and are reported with that label.
- The grid is not byte-comparable across machines: a Kaggle chunk records its platform and any numeric drift is reported, not corrected.
- Carried and not fixed (listed, not hidden): resume does not verify a source content digest for synthetic sources (real runs are safe, the cache manifest hash is in the window id); skipped slots are logged through the logger only, not in `run.json`; threads sharing one cached source are untested on real data (the grid runs sequentially); `fit_seed` of a cached LR initial model shows the first caller's seed.
- Phase 8 and Phase 9 constraints from the review: calibration rows must be tagged and kept out of the pool; monitors must not receive true-label F1 before release.

## Evidence and references
- reports/G2.md (open decisions A and B), CLAIMS E-17 to E-20, ADR-0005, ADR-0006, ADR-0007, PREREG (prereg-v1).
- Second leakage-review pass (Phase 6 start): findings and fixes in commits a82d49c and 0c8a1a0; tests `tests/test_grid.py`, `tests/test_pool_seen.py`.
