---
paths:
  - "src/driftwatch/conformal/**"
  - "src/driftwatch/monitors/**"
  - "tests/test_conformal*.py"
  - "tests/test_monitors*.py"
---
# Conformal and monitor rules

- Mondrian p-value: p_c(x) = (1 + #{calibration samples of class c with score >= s_c(x)}) / (n_c + 1); credibility = p-value of the predicted class.
- Exchangeability: calibration samples come only from the reserved random slice, never from actively selected samples. A contamination test must fail when this is violated.
- The initial calibration is a time-ordered hold-out inside the initial training window that was not used to train that model.
- Monitors never see true labels. The conformal monitor uses only calibration labels that have already arrived (spy test).
- Monitor hyperparameters and thresholds are frozen by a prereg addendum before E4. Do not tune a monitor until it wins; compare at matched labels spent and matched retrain counts.
- Do not re-implement HCC or Transcendent; cite them.
