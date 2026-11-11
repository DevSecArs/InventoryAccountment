"""Проверки ограничений запуска и публикации workflow."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class RegistryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.trigger = cls.workflow.split("permissions:", 1)[0]
        cls.publish = cls.workflow.split("\n  publish:\n", 1)[1]

    def test_untrusted_pull_requests_do_not_trigger_workflow(self) -> None:
        self.assertNotRegex(self.trigger, r"(?m)^\s+pull_request(?:_target)?:")
        self.assertIn("workflow_dispatch:", self.trigger)
        self.assertEqual(re.findall(r"(?m)^      - (.+)$", self.trigger), ["dev", "main"])
        jobs = re.split(r"(?m)^  [a-z][a-z_-]*:\n", self.workflow.split("\njobs:\n", 1)[1])[1:]
        self.assertEqual(len(jobs), 10)
        for job in jobs:
            self.assertIn("runs-on: [self-hosted, linux, x64, inventory-registry]", job)
            self.assertTrue(
                "github.event_name == 'workflow_dispatch'" in job
                or "if: github.event_name == 'push' && github.ref == 'refs/heads/dev'" in job
            )

    def test_publish_requires_dev_push_and_all_checks(self) -> None:
        self.assertIn("if: github.event_name == 'push' && github.ref == 'refs/heads/dev'", self.publish)
        needs = self.publish.split("    permissions:", 1)[0]
        for job in ("container-check", "tests", "style", "security", "migrations", "backup-restore", "build", "image_scan"):
            with self.subTest(job=job):
                self.assertRegex(needs, rf"(?m)^      - {re.escape(job)}$")

    def test_publish_uses_verified_artifacts_for_all_images(self) -> None:
        self.assertIn("for service in backend nginx db; do", self.publish)
        self.assertIn("actions/download-artifact@v4", self.publish)
        self.assertIn("artifacts/$service-image.txt", self.publish)
        self.assertIn('test "$actual" = "$expected"', self.publish)
        self.assertIn('destination=frontend', self.publish)
        self.assertIn('192.168.56.111:5000/inventory/$destination:$GITHUB_SHA', self.publish)
        self.assertNotIn("docker build", self.publish)
        self.assertNotIn("ghcr.io", self.publish)
        self.assertIn("published/$service-image.txt", self.publish)


if __name__ == "__main__":
    unittest.main()
