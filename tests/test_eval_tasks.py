import os
import unittest

from aci_patch_agent.eval_tasks import EVAL_TASKS
from aci_patch_agent.sandbox import DockerSandbox
from aci_patch_agent.tasks import TASKS
from aci_patch_agent.tools import Workspace, tool_schemas


SOLUTIONS = (
    "def clamp(value, low, high):\n    if low > high: raise ValueError()\n    return max(low, min(value, high))\n",
    "def safe_mean(numbers):\n    if not numbers: raise ValueError()\n    return sum(numbers) / len(numbers)\n",
    "def flatten_once(groups):\n    return [item for group in groups for item in group]\n",
    "def count_words(text):\n    result = {}\n    for word in text.casefold().split(): result[word] = result.get(word, 0) + 1\n    return result\n",
    "def rotate_left(items, k):\n    if type(k) is not int: raise TypeError()\n    if not items: return []\n    k %= len(items)\n    return items[k:] + items[:k]\n",
    "def is_palindrome(text):\n    text = ''.join(c for c in text.casefold() if c.isalnum())\n    return text == text[::-1]\n",
    "def parse_pairs(text):\n    if not text.strip(): return {}\n    result = {}\n    for item in text.split(','):\n        if ':' not in item: raise ValueError()\n        key, value = item.split(':', 1)\n        key = key.strip()\n        if not key: raise ValueError()\n        result[key] = value.strip()\n    return result\n",
    "def running_total(values):\n    result, total = [], 0\n    for value in values:\n        total += value\n        result.append(total)\n    return result\n",
    "def strip_suffix(text, suffix):\n    return text[:-len(suffix)] if suffix and text.endswith(suffix) else text\n",
    "def transpose(matrix):\n    if not matrix: return []\n    if any(len(row) != len(matrix[0]) for row in matrix): raise ValueError()\n    return [list(row) for row in zip(*matrix)]\n",
)


class AblationTest(unittest.TestCase):
    def test_switch_changes_only_syntax_acceptance_and_description(self):
        checked, unchecked = Workspace(TASKS[0], None), Workspace(TASKS[0], None, checked=False)
        args = {"start": 2, "end": 2, "replacement": "    return ("}
        self.assertFalse(checked.execute("edit", args)["accepted"])
        self.assertTrue(unchecked.execute("edit", args)["accepted"])
        a, b = tool_schemas(True), tool_schemas(False)
        a[1]["function"]["description"] = b[1]["function"]["description"]
        self.assertEqual(a, b)

    def test_eval_tasks_are_distinct_from_development_tasks(self):
        self.assertEqual(len(EVAL_TASKS), 10)
        self.assertFalse({t.id for t in TASKS} & {t.id for t in EVAL_TASKS})

    @unittest.skipUnless(os.environ.get("ACI_DOCKER_TESTS") == "1", "requires Docker")
    def test_each_broken_fixture_fails_and_each_reference_passes(self):
        sandbox = DockerSandbox()
        for task, source in zip(EVAL_TASKS, SOLUTIONS):
            with self.subTest(task=task.id):
                self.assertFalse(sandbox.check(task, task.source, final=True)["passed"])
                result = sandbox.check(task, source, final=True)
                self.assertTrue(result["passed"], result)
