"""Проверки структурированных журналов и защиты секретов."""

import json
import logging
from datetime import datetime
from uuid import UUID

from fastapi.testclient import TestClient

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

    handler = CaptureHandler()
    logger = logging.getLogger("inventory.http")
    logger.addHandler(handler)

    try:
        log_application_error(
            event="unexpected_http_error",
            exception=RuntimeError("password=synthetic-secret-123"),
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

    assert "synthetic-secret-123" not in handler.records[0]
    assert "password=" not in handler.records[0]
