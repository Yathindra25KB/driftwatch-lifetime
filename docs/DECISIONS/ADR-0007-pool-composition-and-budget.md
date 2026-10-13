# ADR-0007: Training-pool composition, new-label weight, budget base, retrain anchor and the simulator's queue rules

**Status:** PROPOSED. The two pool choices (new-label weight 1, no truncation) were made by the researcher on 2026-10-11, before any simulator run existed. The remaining rules (budget base, retrain anchor, calibration slice, after-window labels, memory and parallelism) are proposed by Claude Code and take effect when the researcher accepts this ADR. Nothing below was chosen by looking at AUT. Formal acceptance (PROPOSED to ACCEPTED) is the researcher's.
**Date:** 2026-10-13
**Deciders:** Yathindra (researcher, approves); Claude Code (engineering lead, proposes)
**Phase:** 5

This ADR closes the open value "training-pool composition, new-label weight, budget base" in PROTOCOL section 5 and settles D3 and D7. It must be accepted before any grid run (hard rule 7 spirit: the design is fixed before results exist). The label-influence check below counts changed predictions only; it computes no AUT and no F1.

## Context
- **What the simulator does (chapter 6).** Per evaluation slot: release the labels that arrive now, retrain if the policy says so and new labels exist, score the slot on its label-free public view, select rows to query, queue them. A label queried in slot `t` is usable from slot `t + 1 + d`.
- **Rule 3 and the sealed store.** The delay lives only in `src/driftwatch/sim/queue.py`; true labels leave the sealed slot by the queue and by the metric door only (`tests/test_queue_delay.py`, `tests/test_sim_sealed.py`).
- **D3 (budget base).** The guide says "a percentage of the slot" and the Phase 5 prompt "of the evaluated slot". It does not say whether the base is counted before or after C3 malware subsampling.
- **D7 (retrain anchor).** "Retrain every 3 slots" does not say counted from where.
- **Training prevalence (ADR-0006).** The initial window is raw (8% to 73% malware on LAMDA, 35% to 55% on BODMAS across windows, CLAIMS E-08), while evaluation slots are C3-subsampled to at most 10% malware. Rows that arrive through the queue are C3-subsampled evaluation rows, so a pool of initial plus arrived rows mixes two priors.
- **Scale of the budget.** At 0.5% to 5% of a slot of a few thousand rows, a slot's budget is tens to a couple of hundred labels, of which about a tenth are malware under random selection (the C3 ratio). The initial window holds thousands of rows.
- **Memory.** The approved cap is 1.5 GiB per process; BODMAS E0 peaked at 1.40 GiB (CLAIMS E-01).

## Options considered

### 1. New-label weight in the pool
- **A. Weight 1, no free parameter.** Arrived labels are rows like any other. Pro: nothing to tune, so a budget or delay contrast is not confounded with a weight; simple to explain. Con: at small budgets arrived labels are a small share of the pool, so retraining may change few predictions (a finding, reported as such).
- **B. A fixed up-weight `w` declared now.** Pro: small budgets have more pull. Con: `w` becomes a hyperparameter every contrast depends on; it needs a sensitivity row and a defence.
- **C. `w` chosen by a pre-declared influence rule.** Pro: not chosen by AUT. Con: still a tuned parameter, and the rule itself is a free choice.

### 2. Truncation of the pool
- **A. None.** Initial window plus every arrived label for the rest of the window. Pro: no parameter; growth is bounded by the budget (at most 5% of each slot); memory stays near the E0 level. Con: old initial rows are never forgotten.
- **B. Sliding: keep the last `K` slots.** Models forgetting; adds `K` and shrinks the pool on BODMAS where `nT` is 3.
- **C. Cap the number of arrived labels.** Bounds memory; the cap is arbitrary and interacts with the budget.

### 3. Budget base (D3)
- **A. Percentage of the evaluated slot after C3.** The slot the selector actually sees; the count follows from the slot's size on the scoring side.
- **B. Percentage of the raw slot before C3.** Budgets would depend on how many malware C3 discards, which varies by slot (CLAIMS W-01), so the same percentage would mean different counts for the same visible slot.

### 4. Retrain anchor (D7)
- **A. Before scoring evaluation slots 3, 6, 9, ... counted from the first evaluation slot of the window.** A retrain at slot 0 would have no label to use; the first event has up to three slots of queries behind it.
- **B. Counted from the window's first training slot.** Aligns with ADR-0005's stride but would fire before slots that depend on `nT`, so the same period would behave differently per dataset.

### 5. Parallelism and memory
- **A. One thread per run, default one worker.** The memory watchdog is process-wide, so two concurrent runs share the 1.5 GiB cap.
- **B. Raise the cap for parallel runs.** The cap is the researcher's (Phase 2); not changed here.

## Decision (choice)
1. **New-label weight: 1** (option 1A), chosen by the researcher on 2026-10-11.
2. **No truncation** (option 2A), chosen by the researcher on 2026-10-11. A label whose release slot is at or after the window's last slot is ignored and counted (the queue rule); windows are independent runs and nothing carries over.
3. **Budget base: the evaluated slot after C3** (option 3A). `n = floor(pct / 100 * n_slot + 1/2)`, capped at the slot size; `n` and `pct` are stored on every slot row.
4. **Retrain anchor: before scoring evaluation slots 3, 6, 9, ...** (option 4A). An event with no label that arrived since the last fit is logged as a no-op, not skipped silently and not refitted.
5. **Calibration slice:** a share of the budget (default 0.20) reserved as random labels. It is a stored, logged parameter with no effect under random selection; it becomes effective in Phase 8.
6. **C1 stays an assertion** against the whole pool including arrived rows, for every scored slot.
7. **Parallelism: across runs, one thread per run, default one worker** (option 5A). With the approved cap, two concurrent BODMAS runs were observed to exceed it (see Evidence).
8. **The label-influence check is a diagnostic, not a selector of the design.** If it shows that 0.5% changes very few predictions, that is reported as a limitation of the design. A weight or truncation change would be a new ADR by change request, with the stored results it makes stale listed.

## Consequences
- **Easier:** no tuned parameter in the pool; paired comparisons across budgets (a smaller budget's selection is a subset of a larger one's at the same seed); resumable runs (units checkpointed).
- **Harder or riskier:**
  - Arrived labels are a small share of the pool (on average 239 at 0.5% and 2,393 at 5% of the slot by the end of a LAMDA window, against an initial 29,422 rows; 70 and 705 against 14,116 on BODMAS; CLAIMS E-13, E-14). The diagnostic counts how many 0.5 decisions change after retraining: on LAMDA 0.7% to 2.1% of scored rows at the two budgets (4.4% to 7.7% of malware rows at 5%), on BODMAS 0.2% to 0.4% (E-13 to E-15). That is a count of changed decisions, not an effect on detection quality, and there is no noise floor (a refit on a pool with arbitrary extra rows, or with permuted arrived labels, was not run). Reports must not read "no gain" at 0.5% as "labels do not help", and must not call the counts "small" or "modest" without such a comparison.
  - The pool mixes raw initial rows and C3-subsampled arrived rows (two priors). A change of class prior in retraining is a property of the design.
  - **BODMAS window length.** With `nE = 6` and period 3 there is one useful retrain (before slot 3). At `d = 3` nothing queried in slots 0 to 2 has arrived by then, so periodic equals never on BODMAS (`tests/test_runner_sim.py`); at `d = 2` only slot-0 labels have. Delay contrasts on BODMAS are limited by construction, which ADR-0005's geometry makes true. A longer `nE` for BODMAS would be a new ADR and the researcher's decision.
  - Parallel runs are memory-bound on this machine.
- **Revisit when:** the label-influence check or the first grid results show a design limitation that makes a headline contrast uninformative; or Phase 8 introduces score-driven selectors (the calibration slice becomes effective).

## Evidence and references
- Queue, pool, runner and tests: `src/driftwatch/sim/queue.py`, `pool.py`, `selectors.py`, `policies.py`, `runner.py`; `tests/test_queue_delay.py`, `tests/test_sim_sealed.py`, `tests/test_sim_pool.py`, `tests/test_runner_sim.py`, `tests/test_runner_regression.py`.
- Label-influence diagnostic: `scripts/label_influence.py`; configs `configs/li_*.yaml`; tables `reports/tables/label_influence_lamda.csv` and `label_influence_bodmas.csv`; CLAIMS E-13 to E-15. It reads predictions only and computes no AUT or F1.
- Memory finding (CLAIMS E-20): a first attempt at the BODMAS diagnostic with `--workers 2` crossed the 1.5 GiB cap in one process (reported peak 1.50 GB) and was failed by the watchdog; the arms were then run one at a time. The BODMAS E1 run peaked at 1.47 GiB (98.2% of the cap). Parallelism across runs is therefore not usable at the approved cap; raising the cap is the researcher's decision.
- Run log (CLAIMS E-21). BODMAS diagnostic: three runs at 716608f failed on memory (9cf4f42b768ba56d, d17a45cd639f8c2f and a third overwritten at fa614c3); three runs at fa614c3 completed (34add4eca4bad834, 457d6a929177e93f, be725cfde75ff0d6); three runs at 2bd12d6 completed (ed348555adec05b6, 8076e24d690b20ad, 82c36f8d16241725) and are the ones cited. The reruns followed code changes from the leakage review (commit 0117287), not a result; the fa614c3 and 2bd12d6 label-influence tables are identical. LAMDA diagnostic arms ran once, at 2bd12d6 (04f986e9313f4538, dbe4452622b192ac, 4ac3d383dfdba007). E1: one run per dataset at 2bd12d6 (45ea4054625ca825, df138cc96fa91622).
- E1 comparator note (CLAIMS E-17 to E-19). The per-slot series scores only held-out rows of evaluation slots, with malware subsampled to the target ratio per slot. E0's window-level comparator scored all held-out rows of the pooled window (including training-era slots) after one global C3 draw. The two give different gaps on LAMDA (0.152 and 0.137 for E0; 0.029 and 0.040 per slot) and nearly the same on BODMAS. The comparator that should carry RQ1 is the researcher's decision before the prereg tag; see reports/G2.md.
- ADR-0004 (slots), ADR-0005 (windows), ADR-0006 (threshold, scaling); PROTOCOL.md D3, D7; PREREG.md pool row.
