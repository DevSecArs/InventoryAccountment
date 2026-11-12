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

    def test_publish_uses_verified_candidates_for_all_images(self) -> None:
        self.assertIn("for service in backend nginx db; do", self.publish)
        self.assertIn("needs.build.outputs.backend_digest", self.publish)
        self.assertIn("--all --preserve-digests", self.publish)
        self.assertIn('test "$(cat "published/$service.digest")" = "$digest"', self.publish)
        self.assertIn('test "sha256:$actual" = "$digest"', self.publish)
        self.assertNotIn("docker build", self.publish)
        self.assertNotIn("ghcr.io", self.publish)
        self.assertIn("published/$service-image.txt", self.publish)

    def test_staging_uses_checkout_without_system_deploy_account(self) -> None:
        staging = self.workflow.split("\n  deploy-staging:\n", 1)[1]
        self.assertIn("uses: actions/checkout@v4", staging)
        self.assertIn("bash deploy/staging-request.sh", staging)
        self.assertNotIn("sudo -n -u deploy", staging)
        self.assertIn('test "${#replicas[@]}" -eq 2', staging)
        self.assertIn("http://192.168.56.111:8081/version", staging)

    def test_candidates_are_scanned_by_digest_and_image_id(self) -> None:
        build = self.workflow.split("\n  build:\n", 1)[1].split("\n  image_scan:\n", 1)[0]
        scan = self.workflow.split("\n  image_scan:\n", 1)[1].split("\n  publish:\n", 1)[0]
        self.assertIn("candidate-$GITHUB_SHA-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT", build)
        self.assertIn('docker pull "$reference"', scan)
        self.assertIn('= "$EXPECTED_ID"', scan)
        self.assertIn("image-ref: ${{ steps.candidate.outputs.reference }}", scan)
        self.assertNotIn("docker save", build)
        self.assertNotIn("actions/download-artifact@v4", scan)


if __name__ == "__main__":
    unittest.main()
