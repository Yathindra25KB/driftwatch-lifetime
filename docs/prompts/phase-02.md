PHASE 2 | Data ingestion and data cards | MODE: build | CHANGE_REQUEST: none

## PROJECT
DriftWatch is an open-source study of how long a malware detector stays useful under label delay, a fixed analyst budget and conformal drift monitoring. One time-aware protocol (TESSERACT constraints C1-C3, AUT and A-AUT) is applied to pre-extracted LAMDA (Android) and BODMAS (Windows PE) feature files. I am the researcher, a final-year B.Tech CSE student; you are the engineering lead. Global rules are in CLAUDE.md. No malware is ever executed, opened or redistributed.

## MISSION
Turn LAMDA and BODMAS into time-indexed, memory-safe feature caches that the rest of the system loads one slot at a time, and produce the evidence that fixes the slot design. Answer the guide's week-1 [verify] questions with measurements, not assumptions.

## READ FIRST (if any of these is missing, stop and tell me which earlier phase is incomplete)
- CLAUDE.md
- docs/PROTOCOL.md
- docs/DECISIONS/
- docs/PHASES.md
- docs/ETHICS.md

## DELIVERABLES
1. One loader interface (dataset, slot) -> features, labels, metadata, plus a streaming iterator over slots, backed by on-disk caches under data/cache/ and a content-hashed data/manifest.json (source, version or commit, file hashes, row counts, build date). Rebuilds are idempotent and resumable.
2. LAMDA (Hugging Face, IQSeC-Lab/LAMDA): never materialise the full matrix densely. Stream the parquet in batches into one sparse cache per month. Ignore the dataset's provided 80/20 split. Keep month, family, vt_count and label. Document how the missing year 2015 is handled. I have an 8 GB laptop (7.2 GB usable). Before building, measure free memory and propose a peak-memory cap for me to approve, then record the measured peak against it.
3. BODMAS: features plus metadata (timestamp, family, label) into per-slot float32 caches. Do not normalise at ingestion; scaling is a training-window concern for later phases.
4. reports/data_inventory.md plus CSV tables and plots. For each dataset: row count, class balance per week or month, timestamp type and granularity (first-seen, crawl date or compile time) and what that means for C1, feature count, density, size on disk, duplicate feature vectors appearing in more than one candidate slot (a leakage risk), missing values, family counts, and for each candidate slot length (BODMAS 1, 2 and 4 weeks; LAMDA month and quarter) the per-slot sample and malware counts and which slots fail a minimum-size gate.
5. Data cards (docs/data_cards/lamda.md and bodmas.md): licence, citation, how labels were produced (including LAMDA's warning about antivirus-centric labelling and the vt_count rule), known biases and limits.
6. A synthetic fixture dataset under 1 MB with the same schema, committed, so CI and unit tests never need real data.
7. An ADR (next number) proposing slot lengths, the minimum-size gate and gap handling, backed by the inventory. Status PROPOSED until I approve it.

## CONSTRAINTS
- Pre-extracted feature files only. Never download, run or inspect samples. Never commit dataset content.
- LAMDA via huggingface_hub. BODMAS via the project's published links with resume support. If automated download fails (Google Drive quota is common) stop and give me exact manual steps; do not scrape or work around quotas.
- No train/test splitting and no models in this phase.

## ACCEPTANCE (show evidence)
- `driftwatch data verify` passes after a clean rebuild; hashes match the manifest.
- Tests: no row in two slots; slot timestamps monotone; deterministic loader output; fixture round trip.
- Measured peak memory, wall-clock and disk size of the LAMDA build are recorded in the inventory.
- The inventory answers timestamp type and granularity, feature count, density, slot occupancy, the 2015 gap and duplicates. Anything unanswerable is listed as an open question.
- I have approved the slot ADR (stop and ask me).

## STOP RULE
If LAMDA cannot be cached within the memory limit or its timestamps are unusable, stop and present the guide's fallbacks (yearly slots, or BODMAS-only for Tier 1) with evidence. Do not choose for me.

## WORKING METHOD
Plan mode first. Show me the cache format and the slot candidates before building. Ask me only for decisions that are mine (slot choice, fallbacks).

## RE-ENTRY
- update: apply CHANGE_REQUEST (for example a new dataset version or another slot length). Rebuild only affected caches, re-run verify, update the inventory, the data card and the ADR.
- maintain: check upstream dataset versions and licences, run `driftwatch data verify`, report drift. Never overwrite caches without a new manifest entry.

## HANDOFF
Before you stop: run the phase-closeout skill; update docs/PHASES.md with status, evidence links, commit hash and the hours I report; confirm these artifacts exist (or explain why not):
- src/driftwatch/data/loaders.py
- data/cache/
- data/manifest.json
- reports/data_inventory.md
- docs/data_cards/lamda.md
- docs/data_cards/bodmas.md
- tests/fixtures/
- docs/DECISIONS/ADR-0004-slot-definition.md
