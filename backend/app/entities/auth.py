"""Пользователи, сессии и операции аутентификации."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.postgresql import Base, DatabaseSession

HASH_ALGORITHM = "sha256"
TEXT_ENCODING = "utf-8"
SESSION_COOKIE = "inventory_session"
CSRF_HEADER = "X-CSRF-Token"
SESSION_LIFETIME = timedelta(days=7)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    login: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="operator")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class RegisterRequest(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Логин содержит только буквы, цифры, «_» и «-»")
        return normalized

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Укажите имя")
        return normalized


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("login")
    @classmethod
    def normalize_login(cls, value: str) -> str:
        return value.strip().lower()


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Укажите имя")
        return normalized


class UserResponse(BaseModel):
    id: str
    login: str
    full_name: str
    email: str | None = None
    role: str

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    user: UserResponse
    csrf_token: str


def _hash_password(password: str, salt: bytes | None = None) -> str:
    actual_salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM, password.encode(TEXT_ENCODING), actual_salt, 600_000
    )
    return f"pbkdf2_sha256$600000${actual_salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        expected = hashlib.pbkdf2_hmac(
            HASH_ALGORITHM, password.encode(TEXT_ENCODING), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(expected.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode(TEXT_ENCODING)).hexdigest()


def create_user(db: Session, payload: RegisterRequest) -> User:
    if db.query(User).count() != 0:
        raise ValueError("Начальная регистрация уже завершена")
    user = User(
        login=payload.login,
        password_hash=_hash_password(payload.password),
        full_name=payload.full_name,
        email=payload.email.strip() if payload.email else None,
        role="admin",
    )
    db.add(user)
    db.flush()
    return user


def create_session(db: Session, user: User) -> tuple[str, UserSession]:
    token = secrets.token_urlsafe()
    session = UserSession(
        user_id=user.id,
        token_hash=_token_hash(token),
        csrf_token=secrets.token_urlsafe(),
        expires_at=datetime.now(UTC) + SESSION_LIFETIME,
    )
    db.add(session)
    db.flush()
    return token, session


def get_current_user(request: Request, db: DatabaseSession) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация"
        )
    session = db.query(UserSession).filter(UserSession.token_hash == _token_hash(token)).first()
    now = datetime.now(UTC)
    if not session or session.expires_at.replace(tzinfo=UTC) <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия истекла")
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден"
        )
    request.state.auth_session = session
    return user


CurrentUser = Depends(get_current_user)


def require_csrf(request: Request, user: User = CurrentUser) -> User:
    session = request.state.auth_session
    token = request.headers.get(CSRF_HEADER)
    if token is None or not hmac.compare_digest(token, session.csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Недействительный CSRF-токен"
        )
    return user


CsrfUser = Depends(require_csrf)


def require_receipt_writer(user: User = CsrfUser) -> User:
    """Разрешить изменять поступления только оператору и администратору."""
    if user.role not in {"admin", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для изменения поступлений",
        )
    return user


ReceiptWriter = Depends(require_receipt_writer)


def require_admin(user: User = CsrfUser) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Требуются права администратора"
        )
    return user


AdminUser = Depends(require_admin)
