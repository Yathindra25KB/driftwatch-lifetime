# DriftWatch claims ledger

Every number or claim of consequence that appears in the README, the report (`report/`) or the paper (`paper/`) must have a row here first.

## Rules

1. **No row, no claim.** A number without a row is written as `[verify]` or left out.
2. **Traceable.** Each row names the result file that produced the value and the commit that produced that file. For external facts it names the source and the access date.
3. **Tagged.** `[verified]` means checked against a source or a stored result. `[verify]` means still to check. `[estimate]` means a planning number. `[measured]` means a timing or size from a run on this machine.
4. **Never evidence:** toy, sandbox or synthetic-fixture numbers, including the guide's sandbox table in §7. They may appear only as labelled code-behaviour checks.
5. **Never "first".** No contribution is claimed as "first". State what was measured.
6. **Corrections append.** A changed value gets a new row that names the claim it supersedes; old rows are never edited away.
7. **Regenerable.** Values from experiments must regenerate from stored per-slot predictions with `scripts/make_tables.py` (Phase 6 onward).

## Ledger

| Claim ID | Statement | Value | Source file | Commit | Tag | Access date |
|---|---|---|---|---|---|---|
