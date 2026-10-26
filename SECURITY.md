# Security policy

## What counts

DriftWatch is research software that reads pre-extracted feature files. It never executes, opens or redistributes malware. Reports that matter:

- A vulnerability in the code (for example unsafe deserialisation of a downloaded file, path traversal in the cache builder, or a workflow that could leak a secret).
- A way for a downloaded file to make the tools execute code.
- Dataset content, a credential or personal data committed to the repository or shipped in a release.

## Out of scope

- Requests for evasion tooling, adversarial-example generation, or ways to defeat a detector. The project describes how detectors decay and does not provide such tooling (`docs/ETHICS.md`); these requests will be declined.
- Findings about the datasets themselves (report them to the dataset authors).

## How to report

Use GitHub's private vulnerability reporting (*Security → Report a vulnerability*) on the repository. If that is unavailable, email the address in `CITATION.cff` with the subject `DriftWatch security`. Please do not open a public issue for a vulnerability.

You can expect an acknowledgement within 7 days. This is a research project maintained by one person, so fixes are made on a best-effort basis; a fixed version is released with an entry in `CHANGELOG.md`.

## Supported versions

Only the latest release.
