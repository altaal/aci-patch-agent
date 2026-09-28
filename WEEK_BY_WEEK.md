# Six weeks: build, measure, publish

This guide explains the work in plain language. The week labels are six delivery
stages, with a planned budget of **50 focused hours**. Work can finish ahead of the
calendar; the saved run timestamps show when experiments actually happened. The
hour budgets below are planning limits, not a claim that those hours were logged.

## A. Strategy

Ship three connected public repositories. First, **ACI Patch Agent** proves that
a model can choose tools, observe their results, edit code, and submit work for
evaluation. Second, **Agent Recovery Lab** reuses that implementation to test a
specific reliability question: does explaining a tool failure help the agent
recover? Third, **Agent Edit DPO** adds one small training experiment: prefer edits
that pass tests, train a small adapter, then measure the same agent tasks before
and after. This order gives a reviewer runnable engineering evidence first,
controlled measurements second, and recent post-training experience third. The
third artifact is a small experiment, not a claim that a tiny model competes with
the larger model used in the first two repositories.

## B. The three repositories

| Repository | One-line pitch | What is deliberately excluded |
| --- | --- | --- |
| [aci-patch-agent](https://github.com/altaal/aci-patch-agent) | A small coding agent with four tools and independently graded patches. | Arbitrary repositories, shell access, a UI, full SWE-bench, multiple agents. |
| [agent-recovery-lab](https://github.com/altaal/agent-recovery-lab) | The same agent tested with recoverable tool failures and two kinds of feedback. | A second agent framework, production incident simulation, extra fault families. |
| [agent-edit-dpo](https://github.com/altaal/agent-edit-dpo) | Test-verified edit preferences, an actual DPO adapter, and before/after agent scores. | GRPO, a reward-model project, a model sweep, large-model training. |

The first repo develops the SWE-agent/ACI theme already in progress: tool design,
line-based editing, test feedback, and completion. It does not need another course
or a new jetski study map. All code and fixtures are public, independently authored
examples. Employer code, private notebooks, and internal work data are not inputs.
Existing research and production work remain existing evidence; rebuilding them
is outside this project.

Each repo has at most these five deliverables: runnable code, fixed inputs,
evaluation traces, a numerical results table, and a short explanation of failures.

## A few words used below

- **Agent loop:** the model chooses an action, sees what happened, and chooses its
  next action. It keeps doing this until it submits or runs out of its allowed steps.
- **ACI:** agent-computer interface. Here it means the tools and feedback the model
  uses to interact with a file.
- **Evaluation:** run the resulting program on specified inputs and compare its
  behavior with the expected answers. The model does not grade itself.
- **Baseline:** the version used for comparison, such as feedback without a hint
  or the model before training.
- **Trace:** the saved sequence of model responses, tool calls, observations, and
  final score. It lets someone inspect why a number changed.
- **DPO:** direct preference optimization. Training that makes a model favor a
  chosen answer over a rejected answer relative to the original model.
- **LoRA adapter:** a small set of trained weights added to a frozen base model.
  We save these small weights instead of another full copy of the model.

**One scoring rule across all weeks:** a run passes only when the agent submits
and every final behavioral check passes. Correct code without submission is a
failed agent run. API errors, exhausted budgets, and missing attempts remain in
the denominator. None of these small public task sets establishes broad capability.

## C. Weekly tasks and ship gates

### Week 1: make one complete agent run public

**Budget: 8 hours.** Spend roughly 4 hours on the loop and tools, 2 on evaluation,
and 2 on running, documenting, and publishing it.

**The task in simple language:** give the model a broken Python function and a
description of the right behavior. Let it read the file, replace lines, run example
tests, and submit the result. Stop it after at most 15 actions. Run separate final
checks to decide whether it actually solved the problem.

For example, `normalize_method` must convert `b'GET'` into `'GET'` while preserving
ordinary strings. A runnable demo should show the model making this change itself,
not replay a scripted patch.

**Do the work:** implement `view`, `edit`, `test`, and `submit`; isolate generated
Python in Docker; save every action; run the five development tasks; publish the
README, code, results, and two failure explanations. Setup is part of this delivery,
not a separate week.

From the installed `aci-patch-agent` repo:

```sh
python -m aci_patch_agent run --task normalize-method --output runs/week1-demo
python -m aci_patch_agent run --output runs/week1-five
```

**Binary ship gate:** the repo is public; the README has installation steps and one
demo command; all five tasks have saved attempts; the table shows passes/5; the
failure note points to actual traces.

**Delivered evidence:** [five-task results](results/week1-five-tasks/summary.md),
[failure notes](FAILURES.md), and [fresh-clone checks](VERIFIED.md). The first run
passed **3/5**. One failure repeatedly changed the wrong part of interval merging.
Another produced a correct boolean parser but never submitted. Those attempts stay
in the record.

**STOP reading until this gate:** CS329A lectures/homework maps, the full SWE-agent
paper, ACI study maps, jetski prompt collections, and InternalGoogleJobs guides.
Open only documentation needed to make the next tool call or Docker command work.

### Week 2: compare two tool designs fairly

**Budget: 8 hours.** About 2 hours for ten fixed tasks, 3 for the comparison runner,
and 3 for execution, inspection, and publication.

**The task in simple language:** find out whether refusing edits with invalid Python
syntax changes the agent's results. Run the same ten new functions with the check
enabled and disabled. Use the same model and limits. Tell the model truthfully which
editor it has. Run each condition three times, for **60 total attempts**.

For example, an edit that leaves an `if` statement with no indented body is rejected
by the checked editor. The unchecked editor keeps it, so the next test can fail.
This compares the check and its description together.

**Do the work:** freeze the ten task definitions before running; declare all 60
attempts; save every result; calculate per-task and overall pass rates; inspect the
failed trace instead of selecting a better rerun.

```sh
python -m aci_patch_agent.ablation --output runs/week2-comparison
```

**Binary ship gate:** the manifest lists 60 attempts; 60 result files exist; both
conditions use identical task definitions and limits; the README includes a
ten-task table and the failed example; the offline report reproduces the table.

**Delivered evidence:** [results](results/week2-edit-check/summary.md) and
[interpretation](EXPERIMENTS.md). Checked edits passed **30/30**; unchecked edits
passed **29/30**. The failed transpose run accumulated invalid indentation and
never submitted. No checked run actually triggered syntax rejection, so the result
does not prove that the runtime check caused the difference.

**STOP reading until this gate:** more ACI papers, benchmark surveys, agent framework
comparisons, and new course maps. If a code decision needs the original rationale,
read only SWE-agent's **Section 3, Agent-Computer Interface**; otherwise read no paper.

### Week 3: make the agent encounter a recoverable problem

**Budget: 8 hours.** About 3 hours for fault injection, 2 for tests, and 3 for the
pilot and public second repo.

**The task in simple language:** sometimes a tool fails even when the agent is on
the right track. Create two small, controlled failures: a test call that times out
once, and a file view that initially returns only one line. The next call can work.
Compare a short error with the same error plus a useful recovery hint.

For example, compare `test_timeout` with `test_timeout; no tests ran; source is
unchanged; retry test`. Neither message supplies the correct patch. For a truncated
view, the hint tells the model which line range to request next.

**Do the work:** import the first repo at a pinned commit; add these two one-time
faults; test that the faults do not secretly change the source; run five scenarios
in two conditions. Record whether the agent actually encountered the fault. An
unexposed success is not evidence of recovery.

From the installed `agent-recovery-lab` repo:

```sh
python -m agent_recovery_lab.run --pilot --output runs/week3-pilot
```

**Binary ship gate:** the second repo is public; four fault-behavior tests pass;
the five-scenario pilot has ten traces; each trace records fault exposure; the
README has install instructions, the pilot command, and the measured table.

**Delivered evidence:** [pilot results](https://github.com/altaal/agent-recovery-lab/tree/main/results/week3-pilot).
Both feedback conditions passed **5/5**, and all ten attempts encountered their
fault. This establishes a working recovery experiment; the pilot cannot distinguish
the conditions because both reached 100%.

**STOP reading until this gate:** reliability surveys, orchestration frameworks,
memory systems, multi-agent designs, and jetski prompt expansions. Only inspect
the reused agent's tool contract when implementing the two faults.

### Week 4: measure recovery and explain its limits

**Budget: 8 hours.** About 2 hours for the full run, 3 for trace analysis, and 3 for
reporting and reproduction checks.

**The task in simple language:** expand the pilot to ten fixed scenarios. Run both
feedback conditions three times per scenario. Count completed repairs, actual fault
exposure, and actions used. Then explain the failures in language a reviewer can
check against the traces.

```sh
python -m agent_recovery_lab.run --output runs/week4-full
```

**Binary ship gate:** 60 declared attempts and 60 result files exist; the table
contains all ten tasks; API failures are counted; exposure counts are reported;
three concrete observations are documented; a fresh clone regenerates both saved
reports without changing them.

**Delivered evidence:** [full results](https://github.com/altaal/agent-recovery-lab/blob/main/results/week4-full/summary.md)
and [failure analysis](https://github.com/altaal/agent-recovery-lab/blob/main/FAILURES.md).
Terse feedback passed **26/30**; actionable feedback passed **29/30**. Among attempts
that encountered a fault, the counts were **26/28** and **29/29**. Three API errors
occurred before exposure and remain headline failures. Two terse palindrome runs
made correct code but kept editing until the action limit.

The actionable condition was not faster: mean actions were 6.30 versus 6.27. It
also had more recorded failed actions. Report these alongside the favorable pass
rate; ten tasks are not enough for a general reliability claim.

**STOP reading until this gate:** new fault taxonomies, larger benchmark catalogs,
new agent papers, and any report that expands into another study map. Read the saved
failed traces and the code that produces their observations.

### Week 5: train one small adapter from verified preferences

**Budget: 10 hours.** About 3 hours for preference data, 2 for an actual training
smoke test, 3 for one fixed training run, and 2 for artifacts and documentation.

**The task in simple language:** give a small model pairs of edits for the same
broken function. One edit passes the tests; the other does not. Train it to prefer
the passing edit. The point is to run the complete data-to-training pipeline and
save the resulting weights, not to promise a higher score.

**Do the work:** use only the five development functions from week 1 for training.
For each, pair an authored correct fix with ten distinct constant-return mistakes.
Verify both sides in Docker. This creates **50 pairs from five tasks**, not 50
independent tasks. Use 40 pairs for training; retain ten as a diagnostic reserve
that shares the same task prompts and is not a generalization test. Keep all ten
evaluation functions out of training.

Train `Qwen/Qwen2.5-0.5B-Instruct` using DPO and a small LoRA adapter. The base model
stays frozen. Fix seed 7, rank 8, learning rate 0.00001, and 40 optimizer steps.
Use one successful smoke step as the setup gate; do not turn this into a framework
comparison or a training curriculum.

From the installed `agent-edit-dpo` repo:

```sh
python -m agent_edit_dpo.download
python -m agent_edit_dpo.data --output runs/verified-preferences
python -m agent_edit_dpo.train --output runs/dpo-training --steps 40
```

The training command uses the committed `data/preferences.jsonl`; the separate
data command verifies that the dataset can be rebuilt without replacing it.

**Binary ship gate:** all 50 pairs have verification records; chosen edits pass and
rejected edits fail; training and evaluation task IDs do not overlap; one real
training run finishes; metrics prove weights changed; adapter weights, exact
configuration, and data provenance are public.

**Delivered evidence:** see [preference data](https://github.com/altaal/agent-edit-dpo/tree/main/data)
and [training record](https://github.com/altaal/agent-edit-dpo/tree/main/training/main).
The final training measurements are recorded in the third repo's README and metrics.
The recorded run completed 40 steps in 111.39 seconds, changed 96 trainable tensors,
and saved a 2.2 MB adapter. It trained 540,672 parameters while leaving base weights
frozen. These measurements establish that training ran; week 6 tests whether it helped.

**STOP reading until this gate:** GRPO, PPO, RLHF courses, reward-model papers,
distributed training, and model rankings. If needed, read only the original DPO
paper's **Section 4, Equation 7**, plus TRL's `DPOTrainer` usage documentation to
unblock the actual training call. No second training algorithm.

### Week 6: compare before and after, then make reproduction easy

**Budget: 8 hours.** About 3 hours for the fixed comparison, 3 for clean-clone
checks, and 2 for clear results, releases, and this guide.

**The task in simple language:** put the small model into the same four-tool agent
loop twice: once with the adapter disabled, once enabled. Run the same ten evaluation
functions in both cases, with three repetitions. See whether training helps the
agent finish real tool-driven repairs, not just prefer a training answer.

The small-model comparison allows six actions and 384 generated tokens per call
in both conditions. It uses a strict JSON tool format because the local model is
connected through text generation. These settings differ from weeks 2–4. Compare
the small model only with its own before-training baseline, not with the hosted
80B model's scores.

```sh
python -m agent_edit_dpo.evaluate --output runs/week6-before-after
```

This command uses the committed trained adapter. To evaluate a new training run,
add `--adapter runs/dpo-training/adapter`. Output directories must be new.

**Binary ship gate:** all 60 before/after traces are saved; task hashes match across
conditions; the table shows passes/30 for each; failed and invalid-output attempts
remain included; adapter loading works; all three repos install and pass their
documented checks from fresh clones; the public commits and release tags are pushed.

**Delivered evidence:** [before/after results](https://github.com/altaal/agent-edit-dpo/tree/main/results/week6-before-after)
and [lessons](https://github.com/altaal/agent-edit-dpo/blob/main/FAILURES.md).
Publish the measured outcome even if it is unchanged or worse. Greedy repetitions
can be identical; they do not create 30 independent tasks or a confidence interval.

**STOP reading until this gate:** new training methods, model-shopping lists,
portfolio redesign, application guides, and another six-week roadmap. Inspect the
results, fix reproduction problems, and release what actually ran.

## Reading and scope rules for every week

Use at most **20 minutes of intake per week**, included in the hour budget. Start
with a named code blocker. Read the smallest relevant API section, implement the
next step, and close it. Finishing a gate does not create a backlog of lectures to
catch up on. Applications and job-hunt work are outside this project.

## D. Three ways to drift, and the redirect

| Drift | Redirect rule |
| --- | --- |
| Make another paper or course map before coding. | Write the exact blocked command or function. If no code is blocked, close the reading and run the next task. |
| Turn a tiny agent into a framework, benchmark platform, or UI. | Keep four tools, ten evaluation tasks, two fault families, and one training method. An addition must replace existing scope, not extend the week. |
| Keep tuning until the score looks good or postpone publication to polish. | Freeze settings before the run, retain every failure, publish the result and its limit. A negative result with runnable evidence meets the gate. |

## E. This week's only task

Clone `aci-patch-agent`, follow its install steps, run the one-function live demo,
and explain its saved trace in your own words before opening any new study material.

## Targeted references, only when blocked

- [SWE-agent paper](https://arxiv.org/abs/2405.15793), Section 3: the tool-interface rationale.
- [DPO paper](https://arxiv.org/abs/2305.18290), Section 4, Equation 7: the preference objective.
- [TRL DPOTrainer](https://huggingface.co/docs/trl/dpo_trainer): the training API used here.

These references are implementation aids, not prerequisites or a reading syllabus.
