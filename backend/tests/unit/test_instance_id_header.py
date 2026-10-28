"""Проверки заголовка идентификатора экземпляра HTTP API."""

import socket

from fastapi.responses import JSONResponse

from app.http import _add_instance_id


def test_instance_id_header_uses_container_hostname() -> None:
    response = _add_instance_id(JSONResponse({"code": "internal_error"}, status_code=500))

    assert response.headers["X-Instance-ID"] == socket.gethostname()
