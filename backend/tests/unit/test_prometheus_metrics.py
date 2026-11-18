"""Проверки метрик Prometheus."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app import http
from app.http import create_app


@pytest.fixture(autouse=True)
def ready_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(http, "is_database_ready", lambda: True)


def metric_value(name: str, labels: dict[str, str] | None = None) -> float:
    value = REGISTRY.get_sample_value(name, labels or {})
    return float(value) if value is not None else 0.0


def test_http_requests_and_latency_metrics() -> None:
    client = TestClient(create_app())
    labels = {
        "method": "GET",
        "route": "/health/live",
        "status_code": "200",
    }

    before = metric_value("http_requests_total", labels)
    response = client.get("/health/live")
    after = metric_value("http_requests_total", labels)

    assert response.status_code == 200
    assert after == before + 1

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "http_request_duration_seconds_bucket" in metrics.text


def test_readiness_metric_reflects_database_status(monkeypatch) -> None:
    client = TestClient(create_app())

    monkeypatch.setattr(http, "is_database_ready", lambda: False)
    assert client.get("/health/ready").status_code == 503
    assert metric_value("app_readiness") == 0

    monkeypatch.setattr(http, "is_database_ready", lambda: True)
    assert client.get("/health/ready").status_code == 200
    assert metric_value("app_readiness") == 1

    # Scrape должен проверять БД заново без обращения к healthcheck.
    monkeypatch.setattr(http, "is_database_ready", lambda: False)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "app_readiness 0.0" in response.text
    monkeypatch.setattr(http, "is_database_ready", lambda: True)
    assert "app_readiness 1.0" in client.get("/metrics").text


def test_receipts_counter_counts_successful_creation_only() -> None:
    router = APIRouter(prefix="/receipts")

    @router.post("/", status_code=201)
    def create_receipt() -> dict[str, bool]:
        return {"created": True}

    client = TestClient(create_app([router]))
    before = metric_value("inventory_receipts_created_total")

    assert client.post("/api/v1/receipts/").status_code == 201
    assert client.get("/health/live").status_code == 200
    assert metric_value("inventory_receipts_created_total") == before + 1


def test_secret_does_not_appear_in_metrics() -> None:
    secret = "private-token-for-metrics-test"
    client = TestClient(create_app())

    response = client.get(
        f"/nonexistent/{secret}?token={secret}",
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert response.status_code == 404

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert secret not in metrics.text
