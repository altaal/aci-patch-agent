import json
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
        client = ScriptedClient([
            call("edit", start=2, end=2, replacement="    return ("),
            call("submit"), call("submit"),
        ])
        result = run_task(TASKS[0], client, FakeSandbox(), max_actions=3)
        self.assertIn("SyntaxError", client.requests[1][-1]["content"])
        self.assertEqual(result["status"], "failed_tests")
        self.assertFalse(result["passed"])

    def test_repeated_rejected_edit_stops_run_as_stuck(self):
        same_edit = call("edit", start=2, end=2, replacement="    return str(method)")
        client = ScriptedClient([same_edit, same_edit, call("submit")])

        result = run_task(TASKS[0], client, FakeSandbox(), max_actions=5)

        self.assertEqual(result["status"], "stuck")
        self.assertEqual(result["actions"], 2)
        self.assertEqual(result["model_calls"], 2)
        self.assertFalse(result["submitted"])
        self.assertTrue(result["events"][-1]["observation"]["stuck"])
        self.assertEqual(result["final_source"], result["initial_source"])

    def test_submit_does_not_self_certify_success(self):
        result = run_task(TASKS[0], ScriptedClient([call("submit"), call("submit")]), FakeSandbox())
        self.assertEqual(result["status"], "failed_tests")

    def test_submit_review_reaches_next_model_request(self):
        client = ScriptedClient([call("submit"), call("submit")])

        result = run_task(TASKS[0], client, FakeSandbox())

        feedback = json.loads(client.requests[1][-1]["content"])
        self.assertFalse(feedback["submitted"])
        self.assertTrue(feedback["review_required"])
        self.assertEqual(feedback["issue"], TASKS[0].issue)
        self.assertEqual(feedback["source"], TASKS[0].source)
        self.assertEqual(result["events"][0]["observation"], feedback)
        self.assertTrue(result["submitted"])
        self.assertEqual(result["model_calls"], 2)

    def test_batched_submits_cannot_skip_review(self):
        for max_actions in (2, 3):
            with self.subTest(max_actions=max_actions):
                message = call("submit")
                second_call = call("submit")["tool_calls"][0]
                second_call["id"] = "second-submit"
                message["tool_calls"].append(second_call)
                client = ScriptedClient([message, call("submit")])

                result = run_task(TASKS[0], client, FakeSandbox(), max_actions=max_actions)

                for event in result["events"][:2]:
                    self.assertFalse(event["observation"]["submitted"])
                    self.assertTrue(event["observation"]["review_required"])
                self.assertEqual(result["actions"], max_actions)
                if max_actions == 2:
                    self.assertFalse(result["submitted"])
                    self.assertEqual(result["status"], "action_limit")
                    self.assertEqual(result["model_calls"], 1)
                else:
                    self.assertTrue(result["submitted"])
                    self.assertEqual(result["model_calls"], 2)
                    feedback = client.requests[1][-2:]
                    self.assertEqual([m["tool_call_id"] for m in feedback],
                                     ["test-call", "second-submit"])
                    self.assertTrue(all(json.loads(m["content"])["review_required"] for m in feedback))

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
        result = run_task(TASKS[0], ScriptedClient([message, call("submit"), call("submit")]), FakeSandbox())
        self.assertIn("error", result["events"][0]["observation"])
        self.assertEqual(result["status"], "failed_tests")


class RecoveryTest(unittest.TestCase):
    def test_recovery_preserves_history_budgets_and_example_feedback(self):
        class SeparateFinalSandbox(FakeSandbox):
            def check(self, task, source, *, final=False):
                result = super().check(task, source, final=final)
                if final:
                    result["failures"] = ["FINAL_ONLY_FAILURE"]
                return result

        client = ScriptedClient([
            call("view"), call("test"),
            call("edit", start=2, end=2, replacement="    return 'GET'"),
            call("test"), call("submit"), call("submit"),
        ])

        result = run_task(TASKS[0], client, SeparateFinalSandbox())

        request = client.requests[4]
        self.assertEqual([m["role"] for m in request], ["system", "user"])
        context = json.loads(request[1]["content"])
        self.assertEqual(context["issue"], TASKS[0].issue)
        self.assertEqual(context["source"], "def normalize_method(method):\n    return 'GET'\n")
        self.assertEqual(context["latest_example_test"]["failures"], ["wrong answer"])
        self.assertEqual([a["tool"] for a in context["attempts"]], ["test", "edit", "test"])
        self.assertNotIn("FINAL_ONLY_FAILURE", json.dumps(client.requests))
        self.assertEqual(context["actions_remaining"], 11)
        self.assertEqual(result["events"][3]["recovery"]["messages"], request)
        self.assertEqual(sum("recovery" in e for e in result["events"]), 1)
        self.assertEqual(len(result["events"]), 6)
        self.assertEqual(len(result["responses"]), 6)
        self.assertEqual(result["actions"], 6)
        self.assertEqual(result["prompt_tokens"], 60)
        self.assertEqual(result["completion_tokens"], 30)
        self.assertTrue(result["submitted"])

    def test_same_failure_after_recovery_stops_as_stuck(self):
        client = ScriptedClient([
            call("test"), call("edit", start=2, end=2, replacement="    return 'GET'"),
            call("test"), call("edit", start=2, end=2, replacement="    return 'POST'"),
            call("test"), call("submit"),
        ])

        result = run_task(TASKS[0], client, FakeSandbox())

        self.assertEqual(result["status"], "stuck")
        self.assertEqual(result["actions"], 5)
        self.assertEqual(result["model_calls"], 5)
        self.assertFalse(result["submitted"])
        self.assertTrue(result["events"][-1]["observation"]["stuck"])
        self.assertEqual(sum("recovery" in e for e in result["events"]), 1)

    def test_repeated_test_without_changed_source_does_not_recover(self):
        client = ScriptedClient([
            call("test"), call("edit", start=2, end=2, replacement="    return ("),
            call("test"), call("submit"), call("submit"),
        ])

        result = run_task(TASKS[0], client, FakeSandbox())

        self.assertFalse(any("recovery" in e for e in result["events"]))
        self.assertTrue(result["submitted"])

    def test_different_failure_after_edit_does_not_recover(self):
        class ChangedFailureSandbox(FakeSandbox):
            def check(self, task, source, *, final=False):
                result = super().check(task, source, final=final)
                result["failures"] = [source]
                return result

        client = ScriptedClient([
            call("test"), call("edit", start=2, end=2, replacement="    return 'GET'"),
            call("test"), call("submit"), call("submit"),
        ])

        result = run_task(TASKS[0], client, ChangedFailureSandbox())

        self.assertFalse(any("recovery" in e for e in result["events"]))
        self.assertTrue(result["submitted"])

    def test_recovery_cannot_extend_action_or_token_budget(self):
        for limits, expected_status in (
            ({"max_actions": 3}, "action_limit"),
            ({"max_total_tokens": 45}, "token_limit"),
        ):
            with self.subTest(limits=limits):
                client = ScriptedClient([
                    call("test"), call("edit", start=2, end=2, replacement="    return 'GET'"),
                    call("test"), call("submit"),
                ])

                result = run_task(TASKS[0], client, FakeSandbox(), **limits)

                self.assertEqual(result["status"], expected_status)
                self.assertEqual(result["actions"], 3)
                self.assertEqual(result["model_calls"], 3)
                self.assertFalse(any("recovery" in e for e in result["events"]))
                self.assertFalse(result["submitted"])

    def test_recovery_discards_unexecuted_batched_calls_before_new_request(self):
        message = call("test")
        for index, reply in enumerate([
            call("edit", start=2, end=2, replacement="    return 'GET'"),
            call("test"), call("submit"),
        ], 1):
            tool_call = reply["tool_calls"][0]
            tool_call["id"] = f"batched-call-{index}"
            message["tool_calls"].append(tool_call)
        client = ScriptedClient([message, call("submit"), call("submit")])

        result = run_task(TASKS[0], client, FakeSandbox())

        self.assertEqual([m["role"] for m in client.requests[1]], ["system", "user"])
        self.assertEqual([e["tool"] for e in result["events"][:3]], ["test", "edit", "test"])
        self.assertEqual(result["actions"], 5)
        self.assertEqual(result["model_calls"], 3)
        self.assertFalse(result["events"][3]["observation"]["submitted"])
        self.assertTrue(result["submitted"])


if __name__ == "__main__":
    unittest.main()
