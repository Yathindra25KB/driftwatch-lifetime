# Statistics review: E4 (RQ4, drift monitors)

**Reviewer:** stats-reviewer subagent (read-only), 21 Oct 2026, on branch `phase-09-monitors-e4` at 4a5d20b. It covered:
- `metrics/e4_tables.py`, `metrics/monitor_scores.py`, `scripts/make_e4.py`, `scripts/check_e4_vs_e3.py`;
- the E4 tables and figure;
- CLAIMS P-17, P-18 and E-48 to E-57;
- chapter 7, section 7.6.

**Verdict:** no blocker.
- The registered contrasts are computed correctly: pairing, the two-stage bootstrap, the 0.01 margin, and Holm within each family of 32.
- The claim rows reproduce the CSVs.
- The headline "no monitor beat periodic(3)" is supported.

Six major findings concern interpretation. They are resolved in 3b889b7 (code and tables) and in the commit that follows it (claims and text). CLAIMS E-59 to E-64 supersede E-52 to E-57, and E-65 adds the A-AUT standard deviation.

| # | Severity | Finding | Resolution |
|---|---|---|---|
| 1 | major | M-C does not test timing where a monitor saturates: its control then has the monitor's exact schedule. | Every contrast row now carries `identical_schedule_share`. An M-C row with share 1.0 is labelled `not_informative_identical_schedule` (BODMAS domain classifier, delay 0). Chapter 7 says that timing was tested on LAMDA (identical schedules in 0% to 28% of window-seed pairs) and that on BODMAS the test is weak [E-61, E-62]. |
| 2 | major | At BODMAS delay 3, three monitors give the same arm, so their rows are one comparison counted three times. | A `same_arm_as` column. E-60, E-62 and chapter 7 count distinct comparisons: 7 M-P rows below zero, not 9. |
| 3 | major | "Reversed" overstated rows inside the margin, and E4 has no working family-wise control. | A new verdict label, `reversed_within_margin`: no change larger than 0.01, interval below 0. Only LAMDA logistic regression with KS at delays 0 and 3 is "reversed". Chapter 7 calls these two-sided descriptive readings without family-wise control, and attributes the KS reversal at delay 0 to refit frequency (1.90 against 3.00 refits per window). |
| 4 | major | BODMAS monitor quality rests on about one drop window, so its intervals are artefacts. | The table counts `n_distinct_drop_slots` and `n_windows_with_drops`. Below 3 drop windows it gives counts only, with no interval. BODMAS: one window, one or two slots [E-63]. |
| 5 | major | Ratio replicates were dropped silently, and unevenly between precision and recall. | One replicate set for every ratio (replicates with a drop and an alarm). `n_boot_used` is recorded, and rows that lost more than 2.5% of replicates are flagged. |
| 6 | major | Precision and recall had no chance baseline. | Two exploratory columns, both labelled as not registered: `baseline_always_alarm_precision` and `baseline_random_recall_at_rate`. On LAMDA, precision is within 0.05 of always alarming, and recall is below random alarms at the same rate for KS, MMD and p-uniformity [E-63]. |
| 7 | minor | The addendum understates the Holm floor. | Chapter 7 states the floor (0.0625 with 10 seeds, higher under the 5-seed fallback), says what a floor-level raw p means, and says this was stated after the results [P-18]. |
| 8 | minor | Per-dataset minima were called "family" minima. | E-59 to E-62 say "among these rows" and give the family minimum of 0.0625. |
| 9 | minor | Seed blocks were not checked for equal windows. | `collect` raises when two seed sets cover different windows. |
| 10 | minor | Seed intersection was used silently; the Holm family shrank when a dataset was absent. | Contrasts align on seeds 0 to 9 and set `seed_fallback` otherwise. The Holm family is the requested datasets, with a missing contrast at p = 1. |
| 11 | minor | The labels check ran in one direction only. | It now checks both directions. |
| 12 | minor | Bootstrap diagnostics and provenance were missing. | Added: `boot_mean_minus_point`, `block_len_effective`, `window_stage_coarse`, `n_boot`, `boot_seed`. |
| 13 | minor | A-AUT was given without its SD. | E-65. |
| 14 | minor | Trigger-context drop events come from each arm's own F1. | E-64 and chapter 7 say so; the fall in alarm rate is described as consistent with rule R, not as measured cause. |
| 15 | minor | "Conservative for the monitor" is an argument, not a measurement. | Attributed to the addendum in E-61, E-62 and chapter 7. |
| 16 | minor | Chapter 8 said the monitors were not run. | Chapter 8 updated for E4. |
| 17 | note | Rows in a stratum are dependent. | Stated in E-59 to E-62 and in chapter 7. |

Also changed after the review: every A-AUT panel of the figure spans at least 0.02 (twice the margin), so differences far inside the margin no longer look large.
