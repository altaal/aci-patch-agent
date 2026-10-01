# Copyright 2026 Ali Taalimi. Licensed under the MIT License.
"""Check the publication command using synthetic private terms."""

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest


_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts"
    / "sync_weekly_guide.py"
)


class SyncWeeklyGuideTest(unittest.TestCase):
    """Run the command in an isolated sibling-project workspace."""

    def setUp(self) -> None:
        """Create a guide, an external policy, and an existing public copy."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.repository = self.root / "public-repo"
        scripts = self.repository / "scripts"
        scripts.mkdir(parents=True)
        self.script = scripts / _SCRIPT.name
        shutil.copyfile(_SCRIPT, self.script)
        self.source = self.root / "WEEK_BY_WEEK.md"
        self.source.write_text(
            "# Guide\n\nPublic examples.\n", encoding="utf-8"
        )
        self.policy = self.root / "publication_blocked_terms.txt"
        self.policy.write_text(
            "# Local rules\nprivate-marker\n", encoding="utf-8"
        )
        self.destination = self.repository / "WEEK_BY_WEEK.md"
        self.destination.write_text("Existing copy\n", encoding="utf-8")

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        """Run the copied script and capture its exit status and messages."""
        return subprocess.run(
            [sys.executable, str(self.script), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_clean_guide_can_be_synced_and_checked(self) -> None:
        """An allowed guide produces a copy that passes the check command."""
        self._run().check_returncode()
        self._run("--check").check_returncode()

    def test_blocked_term_preserves_existing_copy(self) -> None:
        """A case-insensitive match fails before replacing the public copy."""
        self.source.write_text("# Guide\n\nPRIVATE-MARKER\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            self.destination.read_text(encoding="utf-8"), "Existing copy\n"
        )

    def test_blocked_term_is_not_echoed_in_diagnostics(self) -> None:
        """Error output locates a match without repeating private content."""
        self.source.write_text("# Guide\n\nprivate-marker\n", encoding="utf-8")
        result = self._run()
        self.assertIn("line 3", result.stderr)
        self.assertNotIn("private-marker", result.stderr.casefold())

    def test_check_rejects_blocked_content(self) -> None:
        """Checking an existing publication also validates the source policy."""
        self.source.write_text("# Guide\n\nPrivate-Marker\n", encoding="utf-8")
        result = self._run("--check")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Blocked content", result.stderr)

    def test_missing_policy_preserves_existing_copy(self) -> None:
        """A missing policy cannot silently disable the publication guard."""
        self.policy.unlink()
        result = self._run()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            self.destination.read_text(encoding="utf-8"), "Existing copy\n"
        )

    def test_empty_policy_preserves_existing_copy(self) -> None:
        """Comments and blank lines alone are not a usable policy."""
        self.policy.write_text("# No rules\n\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(
            self.destination.read_text(encoding="utf-8"), "Existing copy\n"
        )

    def test_policy_inside_public_repository_is_rejected(self) -> None:
        """The command refuses a policy stored in its publication repository."""
        public_policy = self.repository / "policy.txt"
        shutil.copyfile(self.policy, public_policy)
        result = self._run("--blocked-terms", str(public_policy))
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside", result.stderr)

    def test_alternate_external_policy_is_used(self) -> None:
        """A supplied policy is enforced when using an alternate source."""
        alternate = self.root / "alternate.txt"
        alternate.write_text("other-marker\n", encoding="utf-8")
        self.source.write_text("# Guide\n\nother-marker\n", encoding="utf-8")
        result = self._run(
            "--source", str(self.source), "--blocked-terms", str(alternate)
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Blocked content", result.stderr)

    def test_sibling_project_links_are_preserved(self) -> None:
        """Publication keeps local and cross-repository link conversion."""
        self.source.write_text(
            "# Guide\n\n[Local](aci-patch-agent/README.md) and "
            "[Other](agent-recovery-lab/results).\n",
            encoding="utf-8",
        )
        self._run().check_returncode()
        self.assertTrue(
            self.destination.read_text(encoding="utf-8").endswith(
                "[Local](README.md) and "
                "[Other](https://github.com/altaal/"
                "agent-recovery-lab/tree/main/results).\n"
            )
        )


if __name__ == "__main__":
    unittest.main()
