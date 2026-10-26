from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from app.entities import auth


def test_session_with_missing_user_is_rejected() -> None:
    request = Request({"type": "http", "headers": [(b"cookie", b"inventory_session=test-token")]})
    db = MagicMock()
    session = MagicMock()
    session.expires_at = datetime.now(UTC) + timedelta(days=1)
    db.query.return_value.filter.return_value.first.return_value = session
    db.get.return_value = None

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(request, db)

    assert error.value.status_code == 401
    assert error.value.detail == "Пользователь не найден"


def test_session_expiring_at_current_time_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)

    class FrozenDatetime:
        @staticmethod
        def now(tz: object) -> datetime:
            assert tz == UTC
            return now

    request = Request({"type": "http", "headers": [(b"cookie", b"inventory_session=test-token")]})
    db = MagicMock()
    session = MagicMock()
    session.expires_at = now
    db.query.return_value.filter.return_value.first.return_value = session

    monkeypatch.setattr(auth, "datetime", FrozenDatetime)

    with pytest.raises(HTTPException) as error:
        auth.get_current_user(request, db)

    assert error.value.status_code == 401
    assert error.value.detail == "Сессия истекла"


@pytest.mark.parametrize("role", ["admin", "operator"])
def test_receipt_writer_allows_authorized_roles(role: str) -> None:
    user = MagicMock()
    user.role = role

    assert auth.require_receipt_writer(user) is user


def test_receipt_writer_rejects_unauthorized_role() -> None:
    user = MagicMock()
    user.role = "viewer"

    with pytest.raises(HTTPException) as error:
        auth.require_receipt_writer(user)

    assert error.value.status_code == 403
    assert error.value.detail == "Недостаточно прав для изменения поступлений"


def test_create_session_generates_tokens_and_expiration() -> None:
    db = MagicMock()
    user = MagicMock()
    user.id = "test-user"

    token, session = auth.create_session(db, user)

    assert len(token) == 43
    assert len(session.csrf_token) == 43
    assert session.user_id == user.id
    assert session.token_hash == auth._token_hash(token)
    assert session.expires_at > datetime.now(UTC)
    assert session.expires_at <= datetime.now(UTC) + auth.SESSION_LIFETIME
    db.add.assert_called_once_with(session)
    db.flush.assert_called_once()
