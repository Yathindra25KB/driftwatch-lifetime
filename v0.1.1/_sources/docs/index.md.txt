# DriftWatch

DriftWatch is an open-source study of how long a malware detector stays useful as malware changes. It applies one time-aware evaluation protocol (TESSERACT constraints C1 to C3, reported with AUT and A-AUT) to pre-extracted feature files from LAMDA (Android) and BODMAS (Windows PE), and asks how **label delay**, a fixed **analyst budget** and **conformal drift monitoring** change a detector's lifetime.

It never downloads, runs or redistributes malware. It describes how detectors decay, not how to evade them ([ethics](ETHICS.md)).

```{toctree}
:caption: Start here
:maxdepth: 1

../README
getting-started
```

```{toctree}
:caption: The study
:maxdepth: 1

PROTOCOL
PREREG
CLAIMS
GRID
../report/ch00_front_matter
../report/ch01_introduction
../report/ch02_landscape
../report/ch03_analysis
../report/ch04_latest_techniques
../report/ch05_related_work
../report/ch06_method
../report/ch07_experiments
../report/ch08_discussion
../report/ch09_conclusion
related_work_addendum
```

```{toctree}
:caption: Architecture
:maxdepth: 2

architecture/index
```

```{toctree}
:caption: Decisions and evidence
:maxdepth: 1
:glob:

DECISIONS/ADR-0*
reviews/*
PHASES
results_audit
../reports/G*
../reports/claims_audit
../reports/simulated_review
```

```{toctree}
:caption: Data, licences and ethics
:maxdepth: 1
:glob:

data_cards/*
licence_audit
ETHICS
```

```{toctree}
:caption: Operating the project
:maxdepth: 1

MAINTENANCE
RELEASING
ROADMAP
../CHANGELOG
reference
```
