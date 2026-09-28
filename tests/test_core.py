import unittest

from aci_patch_agent.agent import run_task
from aci_patch_agent.tasks import TASKS
from aci_patch_agent.tools import Workspace


class FakeSandbox:
    def check(self, task, source, *, final=False):
        return {"passed": False, "checks": 1, "failures": ["wrong answer"], "error": None}


class ScriptedClient:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.requests = []

    def complete(self, messages):
        self.requests.append([dict(m) for m in messages])
        return {"message": next(self.replies), "usage": {"prompt_tokens": 10, "completion_tokens": 5}, "model": "scripted-test"}


def call(name, **args):
    import json
    return {"role": "assistant", "content": None, "tool_calls": [{"id": "test-call", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.workspace = Workspace(TASKS[0], FakeSandbox())

    def test_syntax_rejection_preserves_previous_source(self):
        before = self.workspace.source
        result = self.workspace.execute("edit", {"start": 2, "end": 2, "replacement": "    return ("})
        self.assertFalse(result["accepted"])
        self.assertEqual(self.workspace.source, before)

    def test_invalid_range_and_bool_do_not_modify_source(self):
        before = self.workspace.source
        for start, end in [(0, 1), (2, 100), (True, 2)]:
            with self.subTest(start=start):
                result = self.workspace.execute("edit", {"start": start, "end": end, "replacement": "pass"})
                self.assertIn("error", result)
                self.assertEqual(self.workspace.source, before)

    def test_syntax_valid_is_not_behaviorally_correct(self):
        result = self.workspace.execute("edit", {"start": 2, "end": 2, "replacement": "    return 'GET'"})
        self.assertTrue(result["accepted"])
        self.assertFalse(self.workspace.execute("test", {})["passed"])

    def test_unknown_tool_does_not_execute(self):
        self.assertIn("error", self.workspace.execute("shell", {"command": "echo nope"}))


class LoopTest(unittest.TestCase):
    def test_rejected_edit_feedback_reaches_next_model_request(self):
        client = ScriptedClient([call("edit", start=2, end=2, replacement="    return ("), call("submit")])
        result = run_task(TASKS[0], client, FakeSandbox(), max_actions=3)
        self.assertIn("SyntaxError", client.requests[1][-1]["content"])
        self.assertEqual(result["status"], "failed_tests")
        self.assertFalse(result["passed"])

    def test_submit_does_not_self_certify_success(self):
        result = run_task(TASKS[0], ScriptedClient([call("submit")]), FakeSandbox())
        self.assertEqual(result["status"], "failed_tests")

    def test_multiple_tool_calls_consume_budget_individually(self):
        message = call("view")
        message["tool_calls"] += call("submit")["tool_calls"]
        result = run_task(TASKS[0], ScriptedClient([message]), FakeSandbox(), max_actions=1)
        self.assertEqual(result["status"], "action_limit")
        self.assertEqual(result["actions"], 1)
        self.assertFalse(result["passed"])

    def test_no_tool_calls_cannot_loop_forever(self):
        client = ScriptedClient([{"role": "assistant", "content": "Done!"}] * 2)
        result = run_task(TASKS[0], client, FakeSandbox(), max_actions=2)
        self.assertEqual(result["status"], "action_limit")
        self.assertEqual(len(client.requests), 2)

    def test_bad_tool_json_is_observation_not_crash(self):
        message = call("edit")
        message["tool_calls"][0]["function"]["arguments"] = "{"
        result = run_task(TASKS[0], ScriptedClient([message, call("submit")]), FakeSandbox())
        self.assertIn("error", result["events"][0]["observation"])
        self.assertEqual(result["status"], "failed_tests")


if __name__ == "__main__":
    unittest.main()
