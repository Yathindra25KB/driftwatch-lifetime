---
paths:
  - "docs/PREREG.md"
  - "docs/prereg/**"
---
# Pre-registration rules

- docs/PREREG.md is locked once any prereg-vN tag exists; docs/prereg/addendum-vN.md is locked once prereg-vN exists. The guard hook blocks changes; do not try to work around it.
- After a lock, changes go only into a new addendum file, which the researcher approves before it is tagged.
- Show the researcher the diff and wait for approval before any prereg tag is created. Tags are created by the researcher's go, never moved or deleted.
