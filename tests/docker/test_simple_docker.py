"""Проверки сети и зависимостей простого Compose без запуска контейнеров."""

import json
import subprocess
import unittest
from pathlib import Path


class SimpleDockerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [
                "docker", "compose", "--env-file", ".env.example",
                "config", "--format", "json",
            ],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.services = json.loads(result.stdout)["services"]

    def test_only_frontend_publishes_port_5173(self) -> None:
        for name, service in self.services.items():
            if name != "frontend":
                self.assertFalse(service.get("ports"), name)
        ports = self.services["frontend"]["ports"]
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0]["published"], "5173")
        self.assertEqual(ports[0]["target"], 5173)

    def test_proxy_uses_internal_backend(self) -> None:
        self.assertEqual(
            self.services["frontend"]["environment"]["VITE_API_PROXY_TARGET"],
            "http://backend:8000",
        )

    def test_startup_waits_for_dependencies(self) -> None:
        for service, dependency in (("backend", "db"), ("frontend", "backend")):
            self.assertEqual(
                self.services[service]["depends_on"][dependency]["condition"],
                "service_healthy",
            )

    def test_database_uses_persistent_volume(self) -> None:
        volumes = self.services["db"]["volumes"]
        self.assertTrue(any(
            volume["type"] == "volume"
            and volume["target"] == "/var/lib/postgresql/data"
            for volume in volumes
        ))
