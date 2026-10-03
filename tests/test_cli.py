import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aci_patch_agent import cli
from aci_patch_agent.tasks import TASKS
from test_core import FakeSandbox, ScriptedClient, call


class CliTest(unittest.TestCase):
    def test_sandbox_error_is_saved_and_remaining_tasks_continue(self):
        class Sandbox(FakeSandbox):
            def preflight(self):
                return {"image": "test-only"}

            def check(self, task, source, *, final=False):
                if task.id == TASKS[0].id:
                    raise RuntimeError("Container cleanup failed")
                return super().check(task, source, final=final)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            client = ScriptedClient([call("submit")] * 4)
            with patch.object(cli, "TASKS", TASKS[:2]), patch.object(
                cli, "OpenRouterClient", return_value=client
            ), patch.object(cli, "DockerSandbox", return_value=Sandbox()), patch(
                "sys.argv", ["aci-patch-agent", "run", "--output", str(output)]
            ), contextlib.redirect_stdout(io.StringIO()):
                cli.main()

            first = json.loads((output / f"{TASKS[0].id}.json").read_text())
            second = json.loads((output / f"{TASKS[1].id}.json").read_text())
            self.assertEqual(first["status"], "sandbox_error")
            self.assertEqual(len(first["events"]), 2)
            self.assertEqual(len(first["responses"]), 2)
            self.assertEqual(second["status"], "failed_tests")
            self.assertTrue(second["submitted"])


if __name__ == "__main__":
    unittest.main()
