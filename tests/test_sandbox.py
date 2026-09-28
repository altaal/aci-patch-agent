import os
import subprocess
import unittest

from aci_patch_agent.sandbox import DockerSandbox
from aci_patch_agent.tasks import TASKS


SOLUTIONS = (
    "def normalize_method(method):\n    if isinstance(method, bytes):\n        return method.decode('ascii')\n    if isinstance(method, str):\n        return method\n    raise TypeError()\n",
    "def chunked(items, n):\n    if type(n) is not int:\n        raise TypeError()\n    if n <= 0:\n        raise ValueError()\n    return [items[i:i+n] for i in range(0, len(items), n)]\n",
    "def merge_intervals(intervals):\n    if any(a > b for a, b in intervals):\n        raise ValueError()\n    result = []\n    for a, b in sorted(intervals):\n        if result and a <= result[-1][1]:\n            result[-1][1] = max(b, result[-1][1])\n        else:\n            result.append([a, b])\n    return result\n",
    "def parse_bool(text):\n    if not isinstance(text, str):\n        raise TypeError()\n    text = text.strip().lower()\n    if text in ('true', 'yes', '1'):\n        return True\n    if text in ('false', 'no', '0'):\n        return False\n    raise ValueError()\n",
    "def unique_stable(items):\n    result = []\n    for item in items:\n        if item not in result:\n            result.append(item)\n    return result\n",
)


@unittest.skipUnless(os.environ.get("ACI_DOCKER_TESTS") == "1", "set ACI_DOCKER_TESTS=1 to run container checks")
class SandboxTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sandbox = DockerSandbox()
        cls.sandbox.preflight()

    def test_broken_fixtures_fail_and_reference_solutions_pass(self):
        for task, solution in zip(TASKS, SOLUTIONS):
            with self.subTest(task=task.id):
                broken = self.sandbox.check(task, task.source, final=True)
                self.assertIsNone(broken["error"], broken)
                self.assertFalse(broken["passed"], broken)
                correct = self.sandbox.check(task, solution, final=True)
                self.assertTrue(correct["passed"], correct)

    def test_timeout_fails_and_removes_container(self):
        command = ["docker", "ps", "-aq", "--filter", "name=aci-patch-"]
        before = set(subprocess.check_output(command, text=True).splitlines())
        sandbox = DockerSandbox(timeout=2)
        result = sandbox.check(TASKS[0], "while True: pass\n")
        self.assertFalse(result["passed"])
        self.assertEqual(result["error"], "execution_timeout")
        after = set(subprocess.check_output(command, text=True).splitlines())
        self.assertEqual(after - before, set())

    def test_printing_fake_success_does_not_pass(self):
        result = self.sandbox.check(TASKS[0], "print('PASS')\ndef normalize_method(x):\n    return 'GET'\n", final=True)
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
