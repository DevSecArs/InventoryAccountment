"""Проверить запущенный контейнерный API через его публичные HTTP-маршруты."""

from __future__ import annotations

import json
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, OpenerDirector, Request, build_opener

BASE_URL = "http://127.0.0.1:8000"


def request_json(
    opener: OpenerDirector,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Выполнить запрос и проверить успешный JSON-ответ без вывода cookie."""
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Accept": "application/json"}
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    if headers is not None:
        request_headers.update(headers)
    request = Request(f"{BASE_URL}{path}", data=body, headers=request_headers, method=method)
    try:
        with opener.open(request, timeout=10) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError(f"HTTP smoke-сценарий не прошёл на {path}") from error
    if not isinstance(decoded, dict):
        raise TypeError(f"Ожидался JSON-объект в ответе {path}")
    return decoded


def require_string(payload: dict[str, Any], key: str) -> str:
    """Вернуть непустое строковое поле JSON-ответа."""
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"В ответе нет строкового поля {key}")
    return value


def session_cookie_header(cookie_jar: CookieJar) -> str:
    """Получить сессионную cookie для HTTP smoke-сценария без вывода её значения."""
    for cookie in cookie_jar:
        if cookie.name == "inventory_session" and cookie.value:
            return f"{cookie.name}={cookie.value}"
    raise RuntimeError("API не выдал сессионную cookie")


def main() -> None:
    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    for health_path in ("/health/live", "/health/ready"):
        health = request_json(opener, health_path)
        if health.get("status") != "ok":
            raise RuntimeError(f"Проверка готовности не прошла: {health_path}")

    registration = request_json(
        opener,
        "/api/v1/auth/register",
        method="POST",
        payload={
            "login": "container-admin",
            "password": "container-smoke-password",
            "full_name": "Контейнерная проверка",
        },
    )
    csrf_token = require_string(registration, "csrf_token")
    session_cookie = session_cookie_header(cookie_jar)
    unit = request_json(
        opener,
        "/api/v1/units/",
        method="POST",
        payload={"code": "KG"},
        headers={"Cookie": session_cookie, "X-CSRF-Token": csrf_token},
    )
    unit_id = require_string(unit, "id")
    units = request_json(opener, "/api/v1/units/", headers={"Cookie": session_cookie})
    items = units.get("items")
    if not isinstance(items, list) or not any(
        isinstance(item, dict) and item.get("id") == unit_id and item.get("code") == "KG"
        for item in items
    ):
        raise RuntimeError("Созданная единица измерения не получена через API")
    print("Контейнерный API → PostgreSQL smoke-сценарий успешно завершён")


if __name__ == "__main__":
    main()
