"""HTTP API приложения на FastAPI."""

from __future__ import annotations

import logging
import os
import socket
from collections.abc import AsyncIterator, Iterable, Iterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.entities.routers import (
    auth_router,
    material_router,
    receipt_router,
    report_router,
    supplier_router,
    unit_router,
)
from app.observability import log_application_error, log_http_request, observe_http_request
from app.postgresql import close_database, is_database_ready, session_scope

logger = logging.getLogger(__name__)
REQUEST_ID_HEADER = "X-Request-ID"
INSTANCE_ID_HEADER = "X-Instance-ID"


class HealthResponse(BaseModel):
    """Состояние проверяемого компонента."""

    status: str


class ErrorResponse(BaseModel):
    """Единый формат ошибки HTTP API."""

    code: str
    message: str
    details: Any = None
    request_id: str


def get_db_session() -> Iterator[Session]:
    """Предоставить запросу транзакционную сессию PostgreSQL."""
    with session_scope() as session:
        yield session


def _get_request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    return request_id if isinstance(request_id, str) else str(uuid4())


def _valid_request_id(value: str | None) -> str:
    if value is None:
        return str(uuid4())
    try:
        return str(UUID(value))
    except (ValueError, AttributeError):
        return str(uuid4())


def _add_instance_id(response: JSONResponse) -> JSONResponse:
    response.headers[INSTANCE_ID_HEADER] = socket.gethostname()
    return response


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    body = ErrorResponse(
        code=code,
        message=message,
        details=details,
        request_id=_get_request_id(request),
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Освободить пул БД после завершения обработки запросов сервером."""
    try:
        yield
    finally:
        close_database()


def create_app(entity_routers: Iterable[APIRouter] = ()) -> FastAPI:
    """Создать приложение и подключить переданные роутеры сущностей."""
    application = FastAPI(
        title="InventoryAccountment API",
        description="HTTP API системы складского учёта",
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    @application.get("/version")
    def version() -> dict[str, str]:
        return {"sha": os.environ.get("BUILD_GIT_SHA", "unknown")}

    @application.middleware("http")
    async def response_headers_middleware(request: Request, call_next: Any) -> Any:
        request.state.request_id = _valid_request_id(request.headers.get(REQUEST_ID_HEADER))
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started) * 1000
            log_http_request(
                request,
                status_code=500,
                duration_ms=duration_ms,
            )
            observe_http_request(
                request,
                status_code=500,
                duration_ms=duration_ms,
            )
            raise

        duration_ms = (perf_counter() - started) * 1000
        log_http_request(
            request,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        observe_http_request(
            request,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return _add_instance_id(response)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exception: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="validation_error",
            message="Переданы некорректные данные",
            details=exception.errors(),
        )

    @application.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exception: HTTPException) -> JSONResponse:
        detail = exception.detail
        message = detail if isinstance(detail, str) else "Запрос не выполнен"
        details = None if isinstance(detail, str) else detail
        return _error_response(
            request,
            status_code=exception.status_code,
            code=f"http_{exception.status_code}",
            message=message,
            details=details,
        )

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
        log_application_error(
            event="unexpected_http_error",
            exception=exception,
            request_id=_get_request_id(request),
        )
        response = _error_response(
            request,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="internal_error",
            message="Внутренняя ошибка сервера",
        )
        response.headers[REQUEST_ID_HEADER] = _get_request_id(request)
        return _add_instance_id(response)

    @application.get(
        "/health/live",
        response_model=HealthResponse,
        tags=["health"],
        summary="Проверить жизнеспособность приложения",
    )
    async def liveness() -> HealthResponse:
        return HealthResponse(status="ok")

    @application.get(
        "/health/ready",
        response_model=HealthResponse,
        responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
        tags=["health"],
        summary="Проверить готовность приложения и PostgreSQL",
    )
    def readiness() -> HealthResponse:
        if not is_database_ready():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PostgreSQL недоступна",
            )
        return HealthResponse(status="ok")

    api_router = APIRouter(prefix="/api/v1")
    for entity_router in entity_routers:
        api_router.include_router(entity_router)
    application.include_router(api_router)

    return application


app = create_app(
    [auth_router, unit_router, material_router, supplier_router, receipt_router, report_router]
)

# Тип зависимости для будущих роутеров сущностей.
DatabaseSession = Annotated[Session, Depends(get_db_session)]
