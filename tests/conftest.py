"""Общие фикстуры тестов, работающих только с изолированной PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


def _assert_test_database() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    test_database_url = os.environ.get("TEST_DATABASE_URL", "")
    if os.environ.get("APP_ENV") != "test":
        raise RuntimeError("Тесты разрешены только при APP_ENV=test")
    if "_test" not in database_url or database_url != test_database_url:
        raise RuntimeError("Тесты требуют отдельный TEST_DATABASE_URL с суффиксом _test")


_assert_test_database()

from app.http import app
from app.postgresql import get_engine


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None, None, None]:
    """Очищать все таблицы после миграций, не заменяя их create_all()."""
    with get_engine().begin() as connection:
        connection.execute(
            text("TRUNCATE user_sessions, users, materials, suppliers, units CASCADE")
        )
    yield
    with get_engine().begin() as connection:
        connection.execute(
            text("TRUNCATE user_sessions, users, materials, suppliers, units CASCADE")
        )


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture()
def authenticated_client(client: TestClient) -> tuple[TestClient, dict[str, str]]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "login": "Admin_User",
            "password": "reliable-test-password",
            "full_name": "Администратор",
        },
    )
    assert response.status_code == 201
    return client, {"X-CSRF-Token": response.json()["csrf_token"]}
