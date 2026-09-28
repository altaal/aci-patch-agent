import json
from pathlib import Path
import tempfile
import unittest

from aci_patch_agent.experiment import summarize_matrix


class ExperimentTest(unittest.TestCase):
    def test_missing_and_error_attempts_remain_in_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            attempts = [{"id": f"task--mode--{i}", "task": "task", "condition": "mode", "repeat": i}
                        for i in range(1, 4)]
            (path / "manifest.json").write_text(json.dumps({"conditions": ["mode"], "attempts": attempts}))
            for attempt, passed, actions, status in zip(attempts, [True, False], [3, 0], ["passed", "api_error"]):
                (path / (attempt["id"] + ".json")).write_text(json.dumps({**attempt, "passed": passed, "actions": actions, "status": status}))
            summarize_matrix(path)
            row = json.loads((path / "summary.json").read_text())["mode"]
            self.assertEqual((row["passed"], row["attempts"], row["actions_observed"]), (1, 3, 2))
            self.assertEqual(row["pass_rate"], 1/3)
            self.assertIn("missing_attempt", (path / "results.csv").read_text())
