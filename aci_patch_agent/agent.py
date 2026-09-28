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
You cannot edit the evaluator. Submit the code, not a verbal claim of success."""


def run_task(task, client, sandbox, *, max_actions=15, max_total_tokens=32_000):
    workspace = Workspace(task, sandbox)
    started = time.monotonic()
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Task: {task.id}\n{task.issue}\n\nsolution.py:\n{task.source}"}]
    events, responses = [], []
    actions = prompt_tokens = completion_tokens = 0
    costs = []
    status = "action_limit"
    submitted = False
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
        for call in calls:
            if actions >= max_actions:
                break
            actions += 1
            name, args = None, None
            call_id = call.get("id", "missing-id") if isinstance(call, dict) else "missing-id"
            try:
                name = call["function"]["name"]
                args = json.loads(call["function"]["arguments"])
                observation = workspace.execute(name, args)
            except (KeyError, TypeError, ValueError):
                observation = {"error": "Malformed tool call. Use a JSON object matching the tool schema."}
            events.append({"action": actions, "response": len(responses), "tool": name,
                           "arguments": args, "observation": observation})
            messages.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(observation)})
            if name == "submit" and observation.get("submitted"):
                submitted = True
                break
        if submitted:
            break
    evaluation = sandbox.check(task, workspace.source, final=True)
    if submitted:
        status = "passed" if evaluation["passed"] else "failed_tests"
        if evaluation.get("error"):
            status = "evaluation_error"
    return {"schema_version": 1, "task": task.id, "issue": task.issue,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "model": getattr(client, "model", "scripted-test"),
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
