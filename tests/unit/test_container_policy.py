"""Негативные сценарии обязательной политики контейнеров."""

import copy
import unittest
from typing import Any
from unittest.mock import patch

from scripts.container_check import nonroot, pinned, run, validate_compose


class ContainerPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config: dict[str, Any] = {
            "services": {
                "app": {
                    "image": "example/api:local",
                    "user": "1000:1000",
                    "healthcheck": {"test": ["CMD", "true"]},
                    "ports": [{"host_ip": "127.0.0.1", "target": 8000}],
                },
                "migrate": {"image": "example/api:local", "user": "1000:1000"},
            }
        }

    def test_valid_daemon_and_one_shot(self) -> None:
        validate_compose(self.config)

    def test_rejects_root_aliases_and_missing_user(self) -> None:
        for user in ("", "root", "root:1000", "0", "00:1000"):
            with self.subTest(user=user):
                self.assertFalse(nonroot(user))
        self.assertTrue(nonroot("70:70"))

    def test_requires_explicit_non_latest_tag_or_digest(self) -> None:
        for image in (
            "postgres",
            "host:5000/repo",
            "repo:latest",
            "repo:latest@sha256:" + "a" * 64,
        ):
            with self.subTest(image=image):
                self.assertFalse(pinned(image))
        self.assertTrue(pinned("host:5000/repo:1.2"))
        self.assertTrue(pinned("repo@sha256:" + "a" * 64))

    def test_rejects_unsafe_compose_changes(self) -> None:
        changes = [
            {"user": "root"},
            {"image": "example/api:latest"},
            {"healthcheck": {}},
            {"healthcheck": {"disable": True}},
            {"healthcheck": {"test": ["NONE"]}},
            {"privileged": True},
            {"network_mode": "host"},
            {"cap_add": ["SETUID"]},
            {"ports": [{"host_ip": "0.0.0.0", "target": 8000}]},
            {"ports": [{"host_ip": "127.0.0.1", "target": 5432}]},
            {"build": {"args": {"API_TOKEN": "example"}}},
            {"build": {"args": {"API_KEY": "example"}}},
            {"build": {"args": {"DATABASE_URL": "example"}}},
        ]
        for change in changes:
            with self.subTest(change=change):
                config = copy.deepcopy(self.config)
                config["services"]["app"].update(change)
                with self.assertRaises(RuntimeError):
                    validate_compose(config)

    def test_database_port_and_unknown_services_are_rejected(self) -> None:
        for name in ("db", "unknown"):
            config = copy.deepcopy(self.config)
            config["services"][name] = config["services"].pop("app")
            with self.assertRaises(RuntimeError):
                validate_compose(config)

    def test_command_failure_does_not_leak_output(self) -> None:
        with patch("scripts.container_check.subprocess.run") as command:
            command.return_value.returncode = 1
            command.return_value.stderr = "private configuration"
            with self.assertRaisesRegex(RuntimeError, "кодом 1") as raised:
                run("docker", "compose", "config")
            self.assertNotIn("private", str(raised.exception))
