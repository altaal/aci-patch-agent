# Week 2: can an edit check change the outcome?

The comparison changes one tool policy: whether an edit with invalid Python syntax
is accepted. Its description tells the model the correct policy in each condition.
This is a combined policy-and-description comparison, not an isolated measurement
of runtime validation alone.

The same hosted model repaired ten new functions three times in each mode: 60
declared attempts. The task definitions and code hashes were recorded before the
run. Nothing was selected or discarded after seeing the scores. The original five
development tasks were not included.

| Mode | Passed | Attempts | Rate | Mean actions |
| --- | ---: | ---: | ---: | ---: |
| Checked | 30 | 30 | 100% | 4.10 |
| Unchecked | 29 | 30 | 96.7% | 4.57 |

## What failed

In [transpose, unchecked, attempt 2](results/week2-edit-check/transpose--unchecked--2.json),
the model first saw an example failure for rows with unequal lengths. It inserted a
fix above the existing return, removed too much of the function, and tried a line
range that no longer existed. Later edits introduced invalid indentation and
repeated the return line. It reached the 15-action limit without submitting. The
final evaluator could not execute the malformed function. The attempt stays failed.

This was the only failed attempt. The checked condition never needed to reject an
edit, so these runs did not directly demonstrate recovery from a syntax rejection.
Do not turn the 3.3 percentage-point difference into a claim of reliable improvement.

## What I learned

A useful result includes the trace that explains its limit. Here the mechanism is
plausible, but the experiment is too small and the observed trajectories differ.
The next artifact deliberately creates a recoverable tool fault, then measures
whether the model actually encounters and recovers from it:
[Agent Recovery Lab](https://github.com/altaal/agent-recovery-lab).

## Reproduce

Install using the README. Rebuild the saved table without a key:

```sh
python -m aci_patch_agent.ablation --report-only --output results/week2-edit-check
```

Run all 60 attempts again, using a new directory and your own model key:

```sh
python -m aci_patch_agent.ablation --output runs/edit-check-rerun
```

The runner records every declared attempt, including an API failure or missing
result. Repetitions describe variation on these tasks; they are not additional
independent tasks. Provider routing can vary even at temperature zero. These public
authored fixtures are not SWE-bench and are not a contamination-resistant benchmark.
