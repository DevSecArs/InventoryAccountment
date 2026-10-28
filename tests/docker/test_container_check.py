"""Модульные проверки статического аудита без запуска Docker."""

import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("container_check", ROOT / "scripts" / "container_check.py")
assert SPEC and SPEC.loader
container_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(container_check)


def valid_fixture(root: Path = ROOT) -> dict:
    return {
        "services": {
            "nginx": {
                "image": "nginxinc/nginx-unprivileged:alpine",
                "user": "101:101",
                "ports": [{"published": "8080", "target": 8080, "protocol": "tcp", "host_ip": "0.0.0.0"}],
                "volumes": [{"type": "bind", "source": str(root / "nginx" / "default.conf"), "target": "/etc/nginx/conf.d/default.conf", "read_only": True}],
                "healthcheck": {"test": ["CMD", "wget", "-q", "-O", "/dev/null", "http://127.0.0.1:8080/health/live"]},
                "cpus": 0.25,
                "mem_limit": "128m",
                "pids_limit": 100,
            },
            "backend": {
                "deploy": {"replicas": 2},
                "healthcheck": {"test": ["CMD", "true"]},
                "cpus": 0.75,
                "mem_limit": "384m",
                "pids_limit": 100,
            },
            "frontend": {
                "healthcheck": {"test": ["CMD", "true"]},
                "cpus": 1.0,
                "mem_limit": "1024m",
                "pids_limit": 100,
            },
            "db": {
                "user": "postgres",
                "healthcheck": {"test": ["CMD", "true"]},
                "cpus": 0.75,
                "mem_limit": "384m",
                "pids_limit": 100,
            },
        }
    }


class ContainerCheckTests(unittest.TestCase):
    def test_import_does_not_call_subprocess(self) -> None:
        with patch.object(subprocess, "run", side_effect=AssertionError("subprocess вызван")):
            spec = importlib.util.spec_from_file_location("container_check_import", ROOT / "scripts" / "container_check.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

    def test_valid_configuration_returns_success_summary(self) -> None:
        with patch.object(container_check, "load_compose", return_value=valid_fixture()):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = container_check.main()
        self.assertEqual(result, 0)
        self.assertIn("Статическая проверка", output.getvalue())

    def test_audit_checks_each_structural_violation(self) -> None:
        mutations = [
            (lambda c: c["services"].pop("db"), "отсутствует обязательный сервис"),
            (lambda c: c["services"]["backend"].update(deploy={"replicas": 1}), "replicas"),
            (lambda c: c["services"]["backend"].update(container_name="api"), "container_name"),
            (lambda c: c["services"]["nginx"].update(image="nginx:latest"), "требуется образ"),
            (lambda c: c["services"]["nginx"].update(user="0:101"), "UID:GID"),
            (lambda c: c["services"]["nginx"].update(user=None), "UID:GID"),
            (lambda c: c["services"]["nginx"].update(ports=[{"published": "80", "target": 80}]), "8080:8080"),
            (lambda c: c["services"]["frontend"].update(ports=[{"published": "5173", "target": 5173}]), "публикация портов"),
            (lambda c: c["services"]["frontend"].update(network_mode="host"), "network_mode"),
            (lambda c: c["services"]["backend"].update(healthcheck={"test": ["NONE"]}), "healthcheck"),
            (lambda c: c["services"]["backend"].update(healthcheck={"test": []}), "healthcheck"),
            (lambda c: c["services"]["backend"].update(cpus=0), "cpus"),
            (lambda c: c["services"]["backend"].update(mem_limit="bad"), "mem_limit"),
            (lambda c: c["services"]["backend"].update(pids_limit=-1), "pids_limit"),
            (lambda c: c["services"]["nginx"].update(volumes=[]), "read-only"),
        ]
        for mutate, expected in mutations:
            with self.subTest(expected=expected):
                config = valid_fixture()
                mutate(config)
                self.assertTrue(any(expected in error for error in container_check.validate(config)))

    def test_root_override_forms_are_rejected_but_gid_zero_is_not_uid_zero(self) -> None:
        for value in ("root", "root:root", "0", "0:42", 0, "00:100"):
            with self.subTest(value=value):
                config = valid_fixture()
                config["services"]["frontend"]["user"] = value
                self.assertTrue(any("root" in error for error in container_check.validate(config)))
        config = valid_fixture()
        config["services"]["frontend"]["user"] = "1000:0"
        self.assertFalse(any("frontend:" in error for error in container_check.validate(config)))

    def test_vulnerable_legacy_port_schemes_are_rejected(self) -> None:
        for published, target in (("80", 80), ("5173", 5173)):
            with self.subTest(published=published):
                config = valid_fixture()
                config["services"]["nginx"]["ports"][0].update(published=published, target=target)
                self.assertTrue(any("8080:8080" in error for error in container_check.validate(config)))

    def test_multiple_errors_are_returned_together(self) -> None:
        config = valid_fixture()
        config["services"]["backend"]["cpus"] = 0
        config["services"]["frontend"]["healthcheck"] = {"disable": True}
        errors = container_check.validate(config)
        self.assertGreaterEqual(len(errors), 2)

    def test_config_loading_errors_are_sanitized(self) -> None:
        secret = "sentinel-private-password"
        cases = [
            (FileNotFoundError(), "Docker Compose CLI"),
            (subprocess.CompletedProcess([], 1, "", secret), "config завершился с ошибкой"),
            (subprocess.CompletedProcess([], 0, "{broken", ""), "некорректный JSON"),
        ]
        for failure, expected in cases:
            with self.subTest(expected=expected), patch.object(subprocess, "run", side_effect=failure):
                with self.assertRaisesRegex(ValueError, expected) as context:
                    container_check.load_compose()
                self.assertNotIn(secret, str(context.exception))

    def test_file_read_failures_are_reported_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Dockerfile").write_text("FROM python:3.12\n")
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                result = container_check.main(root)
        self.assertEqual(result, 1)
        self.assertIn("Не удалось прочитать", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_main_invokes_config_only_and_returns_nonzero_on_compose_error(self) -> None:
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "hidden")) as run:
            output = io.StringIO()
            with contextlib.redirect_stderr(output):
                result = container_check.main()
        self.assertEqual(result, 1)
        self.assertEqual(run.call_args.args[0], ["docker", "compose", "config", "--format", "json"])
        self.assertNotIn("hidden", output.getvalue())


if __name__ == "__main__":
    unittest.main()
