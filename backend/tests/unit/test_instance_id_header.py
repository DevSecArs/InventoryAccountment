"""Проверки заголовка идентификатора экземпляра HTTP API."""

import socket

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.http import _add_instance_id, create_app


def test_instance_id_header_uses_container_hostname() -> None:
    response = _add_instance_id(JSONResponse({"code": "internal_error"}, status_code=500))

    assert response.headers["X-Instance-ID"] == socket.gethostname()


def test_version_returns_build_sha(monkeypatch) -> None:
    monkeypatch.setenv("BUILD_GIT_SHA", "a" * 40)
    response = TestClient(create_app()).get("/version")
    assert response.status_code == 200
    assert response.json() == {"sha": "a" * 40}
