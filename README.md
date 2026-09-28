# ACI Patch Agent

A small coding agent that edits Python, reads test feedback, and submits a patch.
The experiment asks whether the tools give a model enough accurate feedback to
repair its work. The model chooses every live action; the evaluator decides success.

Start with the [plain-language six-week guide](WEEK_BY_WEEK.md). It explains what
to build each week, why it matters, how to run it, and what the measured results mean.

```text
issue + source -> model -> view / edit / test -> observation -> model
                        -> submit -> separate behavioral evaluation
```

## Run it

Requires Python 3.11+ and a running Docker engine (Docker Desktop or Colima).
The host package uses only Python's standard library at runtime.

```sh
git clone https://github.com/altaal/aci-patch-agent.git
cd aci-patch-agent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
docker pull python@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9
```

Set `OPENROUTER_API_KEY` in your shell using your normal secret manager. Never
commit it. The commands below make paid model calls through OpenRouter.

One live demo:

```sh
python -m aci_patch_agent run --task normalize-method --output runs/demo
```

All five tasks:

```sh
python -m aci_patch_agent run --output runs/five-tasks
```

Existing output directories are refused, so reruns cannot erase failed attempts.
The default model is `qwen/qwen3-next-80b-a3b-instruct`, temperature 0, with at most
15 actions and 1,200 completion tokens per call. Malformed calls consume actions.
At 32,000 cumulative reported tokens the next model call is blocked; a final call
can exceed that threshold. These are request/action limits, not a dollar guarantee.
Provider routing and model updates mean live output may change on rerun.

## Tools and grading

| Tool | Behavior |
| --- | --- |
| `view` | Read numbered source lines, up to 100 at a time. |
| `edit` | Replace an inclusive line range; refuse invalid syntax without changing the source. |
| `test` | Run two example checks and return their observed results. |
| `submit` | End the loop and ask the independent evaluator to score the current source. |

Only the source string is editable. Model-generated Python executes in disposable,
non-root containers with no network, a read-only filesystem, memory/process limits,
and a timeout. No credentials or repository directory are mounted. Expected values
stay in the host evaluator; a fresh container returns actual values for comparison.
The container runner is deliberately small and is not a hardened service for
adversarial submissions. Docker must be available; there is no host-execution fallback.

The five tasks are authored development fixtures: bytes-to-text conversion,
chunking, interval merging, boolean parsing, and stable deduplication. Final scoring
uses both example and additional checks, whose expectations are explicit in each
issue. Additional checks are not sent to the model. They are public in the repo,
so this is not a contamination-resistant or held-out benchmark.

A task passes only if the agent submits and every final check passes. API errors,
timeouts, exhausted budgets, invalid submissions, and missing attempts stay in the
denominator. Passing syntax or the two example checks is not sufficient.

## Inspect the evidence

Every run saves `run.json` (model/settings, prompt/tools, source hashes, task hash,
container identity), one trace JSON per task (model messages, tool observations,
patch, final evaluation, usage and duration), `results.csv`, and `summary.md`.
The report command regenerates a table offline from these files; it does not rerun
the model or independently re-grade a saved patch.

## First live result: 3/5 tasks (60%)

One attempt per development task with the default configuration, September 28, 2026.
All five attempts are preserved, including both exhausted budgets.

| Task | Submitted and passed | Actions | Outcome |
| --- | --- | ---: | --- |
| normalize-method | Yes | 4 | All 8 checks passed. |
| chunked | Yes | 4 | All 8 checks passed. |
| merge-intervals | No | 15 | Repeated an ineffective edit; final checks failed. |
| parse-bool | No | 15 | Final code passed 10 checks, but the agent never submitted. |
| unique-stable | Yes | 4 | All 7 checks passed. |

[Raw traces and settings](results/week1-five-tasks/),
[CSV](results/week1-five-tasks/results.csv), and
[failure analysis](FAILURES.md) are committed. No best-attempt selection or repair
by hand was applied to these results. This tiny development run establishes that
the loop runs; it does not establish general coding ability or an ACI improvement.

Rebuild the table without a key:

```sh
python -m aci_patch_agent report results/week1-five-tasks
```

## What failed / what I learned

On interval merging, the model kept changing the overlap condition while leaving
the endpoint-shrinking bug in place. On boolean parsing, it produced correct code,
then continued editing, including a rejected syntax error and repeated code
insertion. It never submitted. Accurate test feedback and syntax checks are useful,
but they do not guarantee progress or termination. A code-correctness score alone
would hide the second failure. The next experiment should change the feedback for
stalls while holding the model and action budget fixed. See [the traces](FAILURES.md).

## Week 2: checked versus unchecked edits

Ten additional authored tasks, two edit modes, three attempts per task and mode.
The model, tasks, action budget, and system prompt are fixed. The syntax check and
its truthful tool description change together.

| Edit mode | Passed / attempts | Mean actions |
| --- | ---: | ---: |
| Checked | 30/30 (100%) | 4.10 |
| Unchecked | 29/30 (96.7%) | 4.57 |

[Per-task table](results/week2-edit-check/summary.md),
[all 60 traces](results/week2-edit-check/), and [interpretation](EXPERIMENTS.md).
The failed unchecked transpose attempt accumulated invalid indentation and never
submitted. No checked attempt triggered syntax rejection. This does **not** show
that the check caused the score difference: different trajectories and the changed
tool description also matter. Three repetitions of ten tasks are still ten tasks.

```sh
python -m aci_patch_agent.ablation --output runs/edit-check
python -m aci_patch_agent.ablation --report-only --output results/week2-edit-check
```

The first command makes live paid calls; the second rebuilds the saved report offline.
The five original development tasks remain separate from these ten evaluation tasks.

## Check the implementation

```sh
python -m unittest discover -s tests -v
ACI_DOCKER_TESTS=1 python -m unittest discover -s tests -v
```

The first command requires neither Docker nor a key. The second additionally checks
that all broken fixtures fail, all reference fixes pass, fake success text is not
accepted, and an infinite loop times out. Scripted clients are unit-test doubles,
not evidence of model capability. CI makes no model calls.

## Scope and provenance

This is an independent small implementation inspired by
[SWE-agent's agent-computer interface](https://arxiv.org/abs/2405.15793).
It extends a previous scripted syntax-versus-behavior exercise into a real model
loop. It does not reproduce SWE-agent, its lint policy, or a SWE-bench score.

Public-source starting points: [SWE-agent](https://github.com/SWE-agent/SWE-agent)
and the container execution approach in
[CS329A homework 2](https://github.com/stanford-cs329a/cs329a-homework2-fall2025-public).
No upstream agent framework is vendored. Task fixtures, tool interface, loop,
host-side grading, trace format and tests are implemented here.

Out of scope for this release: arbitrary repository access, a shell tool,
multi-agent orchestration, memory, a UI, full SWE-bench, and model training.
