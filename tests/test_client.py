import io
import json
import unittest
from unittest.mock import patch

from aci_patch_agent.agent import run_task
from aci_patch_agent.client import OpenRouterClient
from aci_patch_agent.tasks import TASKS
from test_core import FakeSandbox


class ClientTest(unittest.TestCase):
    def test_malformed_provider_response_returns_trace_without_response_body(self):
        for payload in (None, {"choices": None}, {"choices": []},
                        {"choices": [{"message": None}]}):
            with self.subTest(payload=payload), patch.dict(
                "os.environ", {"OPENROUTER_API_KEY": "test-only"}
            ), patch(
                "aci_patch_agent.client.request.urlopen",
                return_value=io.BytesIO(json.dumps(payload).encode()),
            ):
                result = run_task(TASKS[0], OpenRouterClient(), FakeSandbox())

                self.assertEqual(result["status"], "api_error")
                self.assertFalse(result["passed"])
                self.assertEqual(result["events"], [{"error": "api_transport_or_response_error"}])
                self.assertNotIn("test-only", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
