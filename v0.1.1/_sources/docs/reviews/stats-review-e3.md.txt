# Statistics review of the E3 tables and text

Reviewer: stats-reviewer subagent, read-only, 16 Oct 2026, on `reports/tables/e3_*.csv`, `reports/figures/e3_selection.png`, CLAIMS E-40 to E-47, chapter 7 section 7.5, the README and chapter 8, against `docs/prereg/addendum-v2.md` and `docs/PREREG.md`. Every number in section 7.5 and the README matched the CSVs; the findings concern wording, framing and traceability.

| # | Sev. | Finding | Disposition |
|---|---|---|---|
| 1 | major | The LAMDA five-seed rows are the Main-cell contrasts of the addendum (seeds 5 to 9 are conditional), but the table code labels them `seed_robustness` and lists 10-seed rows as `not_computed`; with five paired seeds the smallest Wilcoxon p is 0.0625, so no LAMDA row can pass Holm and the only Holm-significant rows are the BODMAS ones, which do not test shrinkage. | Text corrected (7.5, README, CLAIMS E-41, E-42): says the rows are the Main-cell contrasts, that the verdicts on LAMDA rest on the interval rule alone, and that no RQ3 result on LAMDA is supported by an adjusted test. The role label in `e3_tables.py` is left as is so the committed tables keep their hashes; it is named in the text and in E-42. |
| 2 | major | "Positive in all eight rows" read as eight replications; the rows share the random arm, windows and seeds, and LAMDA has about four independent blocks. | Text corrected: not independent, intervals likely too narrow, lowest ends (0.0008 to 0.0024) not to be read as excluding zero with confidence; "in this sample". |
| 3 | major | "Equivalent to zero" misreads the verdict, whose margin (0.01) is as large as most delay-0 advantages. | Text corrected: defined as "interval includes zero and lies within plus or minus 0.01"; LR credibility at 2% added; the weakness of these verdicts stated. |
| 4 | major | "Worth up to hundredths of A-AUT on BODMAS" overstated and causal; one lower end is borderline. | Text corrected to "higher by 0.003 to 0.008, interval upper ends up to 0.012"; borderline row and bootstrap-mean note added. |
| 5 | major | Score comparison used verdict words without intervals. | Text and heading say point estimates only; "indistinguishable" removed. |
| 6 | major | The trap arm's coverage and credibility are confounded by not retraining, too. | Text (7.5), CLAIMS E-45 and the discussion corrected: nothing is read from the arm as evidence about contamination. |
| 7 | major | Class-prior confound understated; the centroid arm (class mix near random) is not above random; no claim that credibility adds over uncertainty. | Added to 7.5 and README, with "no interval computed". |
| 8 | minor | Ablation wording causal and trend-based; "slightly below nominal in most rows" was wrong (all twelve are below 0.90). | Corrected. |
| 9 | minor | LAMDA label counts and plain-unit effects missing. | Label counts added (43.6 and 87.3 per slot). The per-slot-of-delay unit for the interaction is not computed; listed as not done. |
| 10 | minor | CLAIMS E-44 and E-47 notes (zero by construction; duplicate BODMAS seed sets); E-41 Holm p tests delay-0 advantage. | Fixed in the rows. |
| 11 | minor | Figure: connecting line implies a decay shape; footer. | Line removed, footer says "two delays only"; figure regenerated (tables unchanged). The five-seed set is what the figure plots, as its footer says. |
| 12 | minor | Chapter 6 section 6.11 was stale. | Updated. |

Verdict (reviewer): the numbers and decision words reproduce from the stored tables; the main exposure was interpretive (the LAMDA rows labelled as robustness, verdict words used against a margin as large as the effects). Items 1 to 7 were to be fixed before the text is cited; they are. No third pass has been run on the revised text.

Update, 20 Oct 2026: LAMDA seeds 5 to 9 were run on the researcher's go, so finding 1 no longer applies to the Main cells; the ten-seed LAMDA rows are the registered primary rows (CLAIMS E-42, section 7.5 rewritten). The text of that paragraph was revised after this review and has not had a further independent pass.
