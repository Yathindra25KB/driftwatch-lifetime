---
paths:
  - "src/driftwatch/data/**"
  - "scripts/leakage_canary.py"
  - "tests/test_constraints*.py"
  - "tests/test_leakage*.py"
  - "tests/fixtures/**"
---
# Data and slicer rules (C1-C3, leakage)

- C1: every training sample is strictly older than every evaluation sample. C2: each evaluation slot holds malware and benign samples from that slot's time window only. C3: each evaluation slot reaches the target malware ratio (docs/PROTOCOL.md) by seeded subsampling of malware only.
- C1-C3 are checks that raise exceptions, never warnings. Never weaken them to get green; write an ADR and ask instead.
- Never densify LAMDA. Stream parquet in batches; respect the peak-memory cap the researcher approved in Phase 2 (8 GB machine).
- Rolling windows never span a data gap; slots failing the minimum-size gate are skipped and logged.
- Duplicate feature vectors across slots are a leakage risk: count them and handle them per ADR.
- No normalisation at ingestion; scaling is fitted on the training window only.
- Never commit dataset content. Only the synthetic fixture (under 1 MB) is committed.
