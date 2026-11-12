"""Проверки ограничений запуска и публикации workflow."""

import re
import os
import shutil
import subprocess
import tempfile
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
        self.assertIn('"$GITHUB_SHA" "$backend" "$frontend" "$db"', staging)
        self.assertIn("timeout-minutes: 360", staging)
        self.assertNotRegex(self.workflow, r"(?m)^\s*concurrency:")
        deploy = (ROOT / "deploy" / "staging-deploy.sh").read_text(encoding="utf-8")
        self.assertIn('(( ${#replicas[@]} == 2 ))', deploy)
        self.assertIn("http://192.168.56.111:8081/version", deploy)

    @unittest.skipUnless(os.name == "posix" and shutil.which("bash") and shutil.which("flock"), "Требуются Bash и flock на POSIX")
    def test_staging_waits_for_existing_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            (state / "staging.env").write_text("", encoding="utf-8")
            (root / "docker-compose.staging.yml").write_text("", encoding="utf-8")
            source = (ROOT / "deploy" / "staging-deploy.sh").read_text(encoding="utf-8")
            script = root / "staging-deploy.sh"
            script.write_text(source.replace('state_dir="/opt/actions-runner/staging"', f'state_dir="{state}"'), encoding="utf-8")
            mocks = root / "bin"
            mocks.mkdir()
            for name, content in {"id": "echo gha-runner", "docker": f'touch "{root / "docker-called"}"; exit 47'}.items():
                executable = mocks / name
                executable.write_text(f"#!/bin/sh\n{content}\n", encoding="utf-8")
                executable.chmod(0o755)
            env = dict(os.environ, PATH=f"{mocks}{os.pathsep}{os.environ['PATH']}")
            holder = subprocess.Popen(
                ["bash", "-c", 'exec 9>"$1"; flock -x 9; echo locked; read -r', "bash", str(state / "deploy.lock")],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            )
            try:
                self.assertEqual(holder.stdout.readline().strip(), "locked")
                digest = "1" * 64
                refs = [f"192.168.56.111:5000/inventory/{name}@sha256:{digest}" for name in ("backend", "frontend", "db")]
                process = subprocess.Popen(["bash", str(script), "a" * 40, *refs], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    with self.assertRaises(subprocess.TimeoutExpired):
                        process.wait(timeout=1)
                    self.assertFalse((root / "docker-called").exists())
                    holder.stdin.write("release\n")
                    holder.stdin.flush()
                    holder.wait(timeout=5)
                    process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 47)
                    self.assertTrue((root / "docker-called").exists())
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()
            finally:
                if holder.poll() is None:
                    holder.kill()
                holder.communicate()

    def test_candidates_are_scanned_by_digest_and_image_id(self) -> None:
        build = self.workflow.split("\n  build:\n", 1)[1].split("\n  image_scan:\n", 1)[0]
        scan = self.workflow.split("\n  image_scan:\n", 1)[1].split("\n  publish:\n", 1)[0]
        self.assertIn("candidate-$GITHUB_SHA-$GITHUB_RUN_ID-$GITHUB_RUN_ATTEMPT", build)
        self.assertIn('docker pull "$reference"', scan)
        self.assertIn('= "$EXPECTED_ID"', scan)
        self.assertIn("image-ref: ${{ steps.candidate.outputs.reference }}", scan)
        self.assertNotIn("docker save", build)
        self.assertNotIn("actions/download-artifact@v4", scan)

    @unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Требуется Bash на POSIX")
    def test_failed_verification_preserves_successful_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            (state / "staging.env").write_text("POSTGRES_PASSWORD=test\n", encoding="utf-8")
            (root / "docker-compose.staging.yml").write_text("services: {}\n", encoding="utf-8")
            source = (ROOT / "deploy" / "staging-deploy.sh").read_text(encoding="utf-8")
            source = source.replace('state_dir="/opt/actions-runner/staging"', f'state_dir="{state}"')
            script = root / "staging-deploy.sh"
            script.write_text(source, encoding="utf-8")
            mocks = root / "bin"
            mocks.mkdir()
            for name, content in {
                "id": "echo gha-runner",
                "docker": 'case "$1" in ps) if [ "$2" = -aq ]; then printf "db\\none\\ntwo\\nnginx\\n"; else printf "one\\ntwo\\n"; fi;; inspect) case "$4" in db|nginx) service="$4";; *) service=backend;; esac; if [ "${BAD_HEALTH:-}" = "$4" ]; then echo "$service running unhealthy"; else echo "$service running healthy"; fi;; exec) [ "${FAIL_VERSION:-0}" = 0 ];; *) exit 0;; esac',
                "curl": "echo '{}'",
                "python3": 'cat >/dev/null; [ "${FAIL_VERSION:-0}" = 0 ]',
            }.items():
                executable = mocks / name
                executable.write_text(f"#!/bin/sh\n{content}\n", encoding="utf-8")
                executable.chmod(0o755)
            env = dict(os.environ, PATH=f"{mocks}{os.pathsep}{os.environ['PATH']}")
            sha, next_sha, digest = "a" * 40, "b" * 40, "1" * 64
            refs = [f"192.168.56.111:5000/inventory/{name}@sha256:{digest}" for name in ("backend", "frontend", "db")]
            run = lambda *args, env=env: subprocess.run(["bash", str(script), *args], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(run(sha, *refs).returncode, 0)
            before = (state / "images.env").read_bytes()
            self.assertNotEqual(run(next_sha, *refs, env=dict(env, FAIL_VERSION="1")).returncode, 0)
            self.assertEqual((state / "images.env").read_bytes(), before)
            self.assertFalse((state / "releases" / f"{next_sha}.env").exists())
            self.assertNotEqual(run(next_sha, *refs, env=dict(env, BAD_HEALTH="nginx")).returncode, 0)
            self.assertEqual((state / "images.env").read_bytes(), before)
            self.assertFalse((state / "releases" / f"{next_sha}.env").exists())
            self.assertEqual(run(sha).returncode, 0)
            self.assertNotEqual(run(next_sha).returncode, 0)


if __name__ == "__main__":
    unittest.main()
