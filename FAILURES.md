# Two failed live attempts

These observations come from the first five-task run. The task suite is deliberately
small and public. They are examples to investigate, not general claims about the model.

## Interval merging: editing the wrong operation

[Trace](results/week1-five-tasks/merge-intervals.json), actions 3 and 5:
the test returned `[[1, 3]]` instead of `[[1, 4]]` for `[[1, 4], [2, 3]]`.
The code assigned the later interval's end, which shrank the enclosing interval.
The model changed the overlap condition instead, then repeated the same edit in
actions 6 through 15. The editor accepted these no-op replacements. The agent
exhausted its budget and still failed the endpoint and reversed-interval checks.

Lesson: accepting syntactically valid edits is different from making progress.
An explicit no-change observation is a plausible next experiment, not a measured fix.

## Boolean parsing: correct code without a completed run

[Trace](results/week1-five-tasks/parse-bool.json), action 2:
replacing only the function header inserted a new body above the old return.
Action 3 tried to remove two lines and created an empty `else`; the editor refused
it and preserved the source. Later responses contained batches of tool calls,
including repeated insertions, despite the prompt requesting one call at a time.
The loop counts each call against the budget. It reached 15 actions without `submit`.

The final function passed all 10 behavioral checks, but this attempt correctly
counts as a failed agent run. Publishing 4/5 based only on the final code would
conceal the failure to finish the task.

Lesson: measure submission/termination alongside patch correctness. Keep this
attempt when testing a future change instead of replacing it with a better rerun.
