"""Проверки структурированных журналов и защиты секретов."""

import json
import logging
import secrets
from datetime import datetime
from uuid import UUID

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.entities.unit import UnitCreate
from app.http import create_app
from app.observability import http_logger


def capture_http_logs():
    """Подключить временный обработчик к HTTP-журналу."""
    records = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(json.loads(record.getMessage()))

    handler = CaptureHandler()
    http_logger.addHandler(handler)
    return handler, records


def test_request_log_contains_required_fields():
    handler, records = capture_http_logs()
    try:
        response = TestClient(create_app()).get("/health/live")
    finally:
        http_logger.removeHandler(handler)

    assert response.status_code == 200
    assert len(records) == 1

    event = records[0]
    assert datetime.fromisoformat(event["timestamp"])
    assert event["level"] == "INFO"
    assert event["event"] == "http_request"
    assert event["method"] == "GET"
    assert event["path"] == "/health/live"
    assert event["status_code"] == 200
    assert event["duration_ms"] >= 0
    assert UUID(event["request_id"])
    assert event["request_id"] == response.headers["X-Request-ID"]


def test_request_log_does_not_expose_secrets():
    secret = "super-secret-password-123"
    handler, records = capture_http_logs()

    try:
        response = TestClient(create_app()).get(
            f"/unknown/{secret}?token={secret}",
            headers={"Authorization": f"Bearer {secret}"},
        )
    finally:
        http_logger.removeHandler(handler)

    assert response.status_code == 404
    assert len(records) == 1
    assert records[0]["path"] == "unmatched"
    assert records[0]["status_code"] == 404
    assert secret not in json.dumps(records)


def test_request_id_is_preserved():
    request_id = "550e8400-e29b-41d4-a716-446655440000"
    handler, records = capture_http_logs()

    try:
        response = TestClient(create_app()).get(
            "/health/live",
            headers={"X-Request-ID": request_id},
        )
    finally:
        http_logger.removeHandler(handler)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id
    assert len(records) == 1
    assert records[0]["request_id"] == request_id


def test_application_error_log_does_not_expose_exception_secret() -> None:
    """В журнал попадают тип ошибки и request_id, но не текст исключения."""
    import json
    import logging

    from app.observability import log_application_error

    class CaptureHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.records: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.records.append(record.getMessage())

    secret = secrets.token_hex(16)
    handler = CaptureHandler()
    logger = logging.getLogger("inventory.http")
    logger.addHandler(handler)

    try:
        log_application_error(
            event="unexpected_http_error",
            exception=RuntimeError("password=" + secret),
            request_id="test-request-123",
        )
    finally:
        logger.removeHandler(handler)

    assert len(handler.records) == 1

    event = json.loads(handler.records[0])

    assert event["level"] == "ERROR"
    assert event["event"] == "unexpected_http_error"
    assert event["error_type"] == "RuntimeError"
    assert event["request_id"] == "test-request-123"
    assert "timestamp" in event

    assert secret not in handler.records[0]
    assert "password=" not in handler.records[0]


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/probe/ok", 200),
        ("/probe/item/{secret}", 200),
        ("/probe/missing", 404),
        ("/api/v1/units/", 422),
        ("/probe/error", 500),
    ],
)
def test_http_logs_cover_outcomes_without_request_or_exception_secrets(path, expected, caplog):
    # Маркер генерируется, чтобы сканер не принимал тестовые данные за ключ.
    secret = secrets.token_urlsafe(24)
    path = path.replace("{secret}", secret)
    router = APIRouter()

    @router.get("/probe/ok")
    def success():
        return {"status": "ok"}

    @router.get("/probe/item/{value}")
    def item(value: str):
        return {"status": "ok"}

    @router.get("/probe/error")
    def failure():
        raise RuntimeError(secret)

    @router.post("/units/")
    def unit(payload: UnitCreate):
        return payload

    application = create_app([router])
    # Успех и ошибка проходят тот же middleware, что и API приложения.
    path = path.replace("/probe/", "/api/v1/probe/")
    handler, records = capture_http_logs()
    try:
        with TestClient(application) as client:
            response = client.request(
                "POST" if expected == 422 else "GET",
                path + "?token=" + secret,
                headers={
                    "Authorization": "Bearer " + secret,
                    "Cookie": "session=" + secret,
                    "X-Request-ID": secret,
                },
                json={"code": secret, "password": secret},
            )
    finally:
        http_logger.removeHandler(handler)
    assert response.status_code == expected
    assert secret not in response.text
    events = [event for event in records if event["event"] == "http_request"]
    assert len(events) == 1
    event = events[0]
    assert set(event) == {
        "timestamp",
        "level",
        "event",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "request_id",
    }
    assert datetime.fromisoformat(event["timestamp"])
    assert event["status_code"] == expected
    assert event["level"] == ("ERROR" if expected == 500 else "INFO")
    assert event["duration_ms"] >= 0
    assert str(UUID(event["request_id"])) == response.headers["X-Request-ID"]
    application_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name.startswith(("inventory.", "sqlalchemy.", "uvicorn."))
    )
    assert secret not in json.dumps(records) + application_logs
    if expected == 422:
        assert response.json()["code"] == "validation_error"
        assert response.json()["details"][0]["loc"] == ["body", "code"]
        assert "input" not in response.json()["details"][0]
        assert "ctx" not in response.json()["details"][0]
    if expected == 500:
        errors = [event for event in records if event["event"] == "unexpected_http_error"]
        assert len(errors) == 1
        assert errors[0]["request_id"] == event["request_id"]


def test_database_debug_does_not_enable_parameter_logging(monkeypatch):
    from unittest.mock import MagicMock

    from app import postgresql

    postgresql.close_database()
    create = MagicMock()
    monkeypatch.setattr(postgresql, "create_engine", create)
    monkeypatch.setattr(postgresql.settings, "APP_DEBUG", True)
    try:
        postgresql.get_engine()
        assert create.call_args.kwargs["echo"] is False
        assert create.call_args.kwargs["hide_parameters"] is True
    finally:
        postgresql.close_database()
