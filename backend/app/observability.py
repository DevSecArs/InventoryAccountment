"""Безопасные структурированные журналы HTTP-запросов."""

import json
import logging
from datetime import UTC, datetime

from fastapi import Request
from prometheus_client import Counter, Gauge, Histogram

http_logger = logging.getLogger("inventory.http")
http_logger.setLevel(logging.INFO)
http_logger.propagate = False

if not http_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    http_logger.addHandler(handler)


def log_application_error(
    *,
    event: str,
    exception: Exception,
    request_id: str | None = None,
) -> None:
    """Записать тип ошибки без её текста, traceback и секретов."""
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "ERROR",
        "event": event,
        "error_type": type(exception).__name__,
    }
    if request_id is not None:
        record["request_id"] = request_id

    http_logger.error(json.dumps(record, ensure_ascii=False, separators=(",", ":")))


def safe_route_path(request: Request) -> str:
    """Получить шаблон полного маршрута без пользовательских данных."""
    route = request.scope.get("route")
    route_path = getattr(route, "path_format", None)

    if not isinstance(route_path, str):
        return "unmatched"

    root_path = request.scope.get("root_path", "")
    return f"{root_path}{route_path}" if root_path else route_path


def log_http_request(
    request: Request,
    *,
    status_code: int,
    duration_ms: float,
) -> None:
    """Записать только разрешённые поля HTTP-события."""
    # Неизвестные URL не записываем: в них могут быть секреты.
    safe_path = safe_route_path(request)

    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "INFO" if status_code < 500 else "ERROR",
        "event": "http_request",
        "method": request.method,
        "path": safe_path,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 3),
        "request_id": request.state.request_id,
    }

    http_logger.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))


# Метрики хранятся отдельно в каждой реплике backend.

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route", "status_code"],
)

HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

APP_READINESS = Gauge(
    "app_readiness",
    "Last observed readiness result: 1 ready, 0 unavailable",
)

RECEIPTS_CREATED = Counter(
    "inventory_receipts_created_total",
    "Successfully created inventory receipts",
)


def observe_http_request(
    request: Request,
    *,
    status_code: int,
    duration_ms: float,
) -> None:
    """Обновить метрики без пользовательских идентификаторов."""
    safe_route = safe_route_path(request)

    method = request.method
    HTTP_REQUESTS.labels(
        method=method,
        route=safe_route,
        status_code=str(status_code),
    ).inc()

    HTTP_DURATION.labels(
        method=method,
        route=safe_route,
    ).observe(duration_ms / 1000)

    # Считаем только успешное создание поступления.
    # Фактический URL используется для точного сравнения,
    # но никогда не становится меткой Prometheus.
    if (
        method == "POST"
        and request.scope.get("path") == "/api/v1/receipts/"
        and safe_route.rstrip("/") == "/receipts"
        and status_code == 201
    ):
        RECEIPTS_CREATED.inc()
