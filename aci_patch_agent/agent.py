"""Model -> tool -> observation, until submission or a fixed budget."""

from datetime import datetime, timezone
import difflib
import json
import time

from .client import ModelError
from .tools import Workspace


SYSTEM_PROMPT = """You repair one small Python function in solution.py.
Use view to read numbered lines, edit to replace an inclusive range, test to run
examples, and submit when finished. Make exactly one tool call per response.
Tool observations describe the actual current state. Correct a refused edit using
that feedback. Tests check only examples; implement the entire issue specification.
Keep the named function and signature. Use only Python's standard library.
When a test fails, compare the expected result with the actual result.
Trace the failing input through the current code and identify the statement
that explains the difference. Inspect the current code before editing.
Make one small change, then test again. If the same failure remains, do not
repeat the same edit; revise your explanation of the bug.
If a tool reports that an action made no change, do not repeat that action unchanged. Inspect the current code and recent feedback, then choose a useful next step.
You cannot edit the evaluator. Submit the code, not a verbal claim of success."""


RECOVERY_PROMPT = """Your latest edit did not change the failing example's result.
Reconsider the diagnosis before editing again.
Use the current source and the supplied input, expected output, and actual output.
Identify a statement that produces the wrong value and choose a different repair.
Do not repeat an edit already shown to leave this failure unchanged.
After editing, run test. Before submitting, check every requirement in the issue."""


def _recovery_messages(task, source, events, actions_remaining):
    attempts = [
        {"action": event["action"], "tool": event["tool"], "arguments": event["arguments"],
         "observation": {key: value for key, value in event["observation"].items()
                         if key not in {"source", "total_lines"}}}
        for event in events if event.get("tool") in {"edit", "test"}
    ]
    context = {"task": task.id, "issue": task.issue, "source": source,
               "latest_example_test": events[-1]["observation"],
               "attempts": attempts, "actions_remaining": actions_remaining}
    return [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + RECOVERY_PROMPT},
            {"role": "user", "content": json.dumps(context)}]


def run_task(task, client, sandbox, *, max_actions=15, max_total_tokens=32_000,
             workspace_factory=Workspace, show_initial_source=True):
    workspace = workspace_factory(task, sandbox)
    started = time.monotonic()
    initial = f"Task: {task.id}\n{task.issue}\n\n"
    initial += f"solution.py:\n{task.source}" if show_initial_source else "Use view to read solution.py."
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": initial}]
    events, responses = [], []
    actions = prompt_tokens = completion_tokens = 0
    costs = []
    status = "action_limit"
    submitted = False
    rejected_edits = set()
    review_response = None  # The model must receive the review before it can submit.
    last_test_failure = last_test_source = None
    restart_already_used = False  # True once we rebuild the conversation; only one restart is allowed.
    while actions < max_actions:
        if prompt_tokens + completion_tokens >= max_total_tokens:
            status = "token_limit"
            break
        try:
            response = client.complete(messages)
        except ModelError as error:
            status = "api_error"
            events.append({"error": str(error)})
            break
        responses.append(response)
        usage = response.get("usage", {})
        prompt_tokens += usage.get("prompt_tokens", 0) or 0
        completion_tokens += usage.get("completion_tokens", 0) or 0
        if isinstance(usage.get("cost"), (float, int)):
            costs.append(usage["cost"])
        message = response["message"]
        messages.append(message)
        calls = message.get("tool_calls") or []
        if not isinstance(calls, list) or not calls:
            actions += 1
            observation = {"error": "No tool call received; call view, edit, test, or submit."}
            events.append({"action": actions, "tool": None, "observation": observation})
            messages.append({"role": "user", "content": json.dumps(observation)})
            continue
        restart_requested = False  # True means rebuild the conversation after leaving the tool loop.
        for call in calls:
            if actions >= max_actions:
                break
            actions += 1
            name, args = None, None
            call_id = call.get("id", "missing-id") if isinstance(call, dict) else "missing-id"
            current_source = workspace.source
            try:
                name = call["function"]["name"]
                args = json.loads(call["function"]["arguments"])
                observation = workspace.execute(name, args)
            except (KeyError, TypeError, ValueError):
                observation = {"error": "Malformed tool call. Use a JSON object matching the tool schema."}

            if name == "edit" and observation.get("accepted") is False:
                signature = (current_source, json.dumps(args, sort_keys=True))
                if signature in rejected_edits:
                    observation["stuck"] = True
                    status = "stuck"
                else:
                    rejected_edits.add(signature)
            if name == "test":
                # All three checks must be true. Failing examples tell us what to fix;
                # a test-runner error (such as a timeout) does not give that evidence.
                if (
                    observation.get("passed") is False  # The test report explicitly says it did not pass.
                    and observation.get("failures")  # The list contains at least one failing example.
                    and not observation.get("error")  # No error prevented running or evaluating the tests.
                ):
                    # Convert failure details to text. Sorting dictionary keys makes
                    # equal details compare equal even if their key order differs.
                    failure = json.dumps(observation["failures"], sort_keys=True)
                    # The code changed, but the failing inputs, expected results,
                    # and actual results stayed the same: the edit did not help.
                    if failure == last_test_failure and current_source != last_test_source:
                        if restart_already_used:
                            # We already tried a fresh conversation once. End the run.
                            observation["stuck"] = True
                            status = "stuck"
                        else:
                            # Request a fresh conversation; the run continues within its budget.
                            restart_requested = True
                    # Save this failed test and the code it tested for the next comparison.
                    last_test_failure, last_test_source = failure, current_source
                else:
                    # A pass or a test-runner error ends the sequence of comparable failures.
                    last_test_failure = last_test_source = None
            if name == "submit" and observation.get("submitted"):
                if review_response is None:
                    review_response = len(responses)
                # Block every submit in this response, including batched calls.
                if len(responses) == review_response:
                    observation = {
                        "submitted": False,
                        "review_required": True,
                        "issue": task.issue,
                        "source": workspace.source,
                        "message": (
                            "Review the current code against the issue. "
                            "A review request does not mean the code contains a bug. "
                            "Leaving the code unchanged is a valid and preferred outcome "
                            "when it already meets the requirements. "

                            "Before making an edit, identify a specific input for which "
                            "the current code produces the wrong value or exception. "
                            "Compare the required behavior with what the current code "
                            "actually does, including behavior supplied automatically "
                            "by Python operations and standard-library functions. "

                            "If you cannot identify a concrete mismatch, leave the code "
                            "unchanged and call submit again now. "
                            "Do not refactor, clean up, add redundant exception handling, "
                            "or rewrite working code during this review. "

                            "If you identify a concrete mismatch, make only the smallest "
                            "change needed to fix it, then run test before submitting. "
                            "Passing the examples alone does not prove every requirement."
                        ),
                    }
            events.append({"action": actions, "response": len(responses), "tool": name,
                           "arguments": args, "observation": observation})
            messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(observation)})
            if name == "submit" and observation.get("submitted"):
                submitted = True
                break
            if status == "stuck" or restart_requested:
                # Exit only the inner for-loop: stop executing tools from this response.
                break
        if submitted or status == "stuck":
            # Exit the outer while-loop: the run is finished. Recovery alone does not exit here.
            break
        if restart_requested and actions < max_actions:
            if prompt_tokens + completion_tokens >= max_total_tokens:
                status = "token_limit"
                break
            restart_already_used = True
            # Start a complete new conversation; keep all counters and saved history.
            messages = _recovery_messages(task, workspace.source, events, max_actions - actions)
            review_response = None
            events[-1]["recovery"] = {
                "reason": "same_example_failure_after_edit",
                "messages": [dict(message) for message in messages],
            }
    evaluation = sandbox.check(task, workspace.source, final=True)
    if submitted:
        status = "passed" if evaluation["passed"] else "failed_tests"
        if evaluation.get("error"):
            status = "evaluation_error"
    return {"schema_version": 1, "task": task.id, "issue": task.issue,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model": getattr(client, "model", "scripted-test"),
            "show_initial_source": show_initial_source,
            "max_actions": max_actions, "max_total_tokens": max_total_tokens,
            "status": status, "passed": submitted and evaluation["passed"],
            "submitted": submitted, "actions": actions, "model_calls": len(responses),
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "reported_cost_usd": sum(costs) if costs and len(costs) == len(responses) else None,
            "seconds": round(time.monotonic() - started, 3), "initial_source": task.source,
            "final_source": workspace.source, "evaluation": evaluation,
            "patch": "".join(difflib.unified_diff(task.source.splitlines(True), workspace.source.splitlines(True),
                                                fromfile="a/solution.py", tofile="b/solution.py")),
            "responses": responses, "events": events}
