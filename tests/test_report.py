import json
from pathlib import Path
import tempfile
import unittest

from aci_patch_agent.report import report


class ReportTest(unittest.TestCase):
    def test_missing_attempt_stays_in_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "run.json").write_text(json.dumps({"tasks": ["a", "b"]}))
            (root / "a.json").write_text(json.dumps({"task": "a", "passed": True, "status": "passed"}))
            result = report(root)
            self.assertIn("1/2 (50.0%)", result)
            self.assertIn("missing_attempt", result)
