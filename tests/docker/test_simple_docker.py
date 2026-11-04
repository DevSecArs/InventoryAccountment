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
        cls.nginx_config = (Path(__file__).resolve().parents[2] / "nginx" / "default.conf").read_text()

    def test_only_nginx_publishes_port_8080(self) -> None:
        for name, service in self.services.items():
            if name != "nginx":
                self.assertFalse(service.get("ports"), name)
        ports = self.services["nginx"]["ports"]
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0]["published"], "8080")
        self.assertEqual(ports[0]["target"], 8080)

    def test_backend_replicas_and_nginx_routing(self) -> None:
        self.assertEqual(self.services["backend"]["deploy"]["replicas"], 2)
        self.assertNotIn("container_name", self.services["backend"])
        self.assertNotIn("frontend", self.services)
        nginx = self.services["nginx"]
        self.assertEqual(nginx["build"]["target"], "nginx")
        self.assertEqual(set(nginx["depends_on"]), {"backend"})
        self.assertIn("server backend:8000 resolve max_fails=1 fail_timeout=5s", self.nginx_config)
        self.assertIn(
            "proxy_next_upstream error timeout http_502 http_503 http_504", self.nginx_config
        )
        self.assertIn("proxy_next_upstream_tries 1", self.nginx_config)
        self.assertIn("error_page 502 503 504 = @backend_retry", self.nginx_config)
        self.assertIn("if ($request_method !~ ^(GET|HEAD)$)", self.nginx_config)
        self.assertIn("proxy_connect_timeout 3s", self.nginx_config)
        self.assertIn("proxy_read_timeout 30s", self.nginx_config)
        self.assertIn("location ~ ^/(api|health)(/|$)", self.nginx_config)
        self.assertIn("try_files $uri /index.html", self.nginx_config)
        self.assertIn("try_files $uri =404", self.nginx_config)

    def test_startup_waits_for_dependencies(self) -> None:
        for service, dependency in (("backend", "db"), ("nginx", "backend")):
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
