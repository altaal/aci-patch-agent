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

## Week 2 extension

A new clone of public commit `75111b9`, with a new Python 3.12 environment:

- Installed successfully; all 17 tests passed, including the ten additional
  fixtures and Docker checks.
- Regenerated both the original five-task report and the 60-attempt edit
  comparison without a Git diff.
- Verified that the experiment reporter keeps missing results and API errors in
  the declared denominator.
- Passed GitHub Actions on Linux/Python 3.11 at the same commit.

The saved live traces are original run evidence. Offline report regeneration is
not a claim that a later hosted-model run will produce the same trajectories.
