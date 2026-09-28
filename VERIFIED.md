# Release checks, September 28, 2026

Checked from a fresh clone of commit `9861575`, using a new Python environment:

- Package installation succeeded.
- All 13 tests passed, including Docker execution and timeout cleanup.
- Regenerating the published table produced no Git diff.
- All five saved patches were executed again in fresh containers. Every final
  evaluation matched the published trace, including the passing-but-unsubmitted
  boolean parser.
- The documented live demo completed in four actions and passed all eight checks.
  Its separate [smoke-test trace](results/fresh-clone-smoke/) is preserved. It is
  not substituted into the original five-task score.
- Gitleaks found no secrets in the publication history.

The live run used macOS with a Linux ARM64 Docker engine. GitHub CI checks the
same container tests on Linux. CI never calls a model API.
