"""Настройка подключения к PostgreSQL и управление транзакциями."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL_ENV = "DATABASE_URL"
logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Базовый класс декларативных моделей приложения."""


def get_database_url() -> str:
    """Вернуть и проверить строку подключения из окружения."""
    database_url = os.getenv(DATABASE_URL_ENV)
    if not database_url:
        raise RuntimeError(f"Переменная окружения {DATABASE_URL_ENV} не задана")

    driver_name = make_url(database_url).drivername
    if driver_name != "postgresql" and not driver_name.startswith("postgresql+"):
        raise RuntimeError("DATABASE_URL должна указывать на PostgreSQL")
    return database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Создать единственный engine с проверкой соединения перед выдачей из пула."""
    return create_engine(get_database_url(), pool_pre_ping=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Вернуть фабрику сессий, связанную с engine приложения."""
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


@contextmanager
def session_scope() -> Iterator[Session]:
    """Закрыть сессию, зафиксировав успех или отменив ошибочную транзакцию."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_database_ready() -> bool:
    """Проверить, что PostgreSQL принимает простой запрос."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, RuntimeError, ImportError):
        logger.exception("Проверка готовности PostgreSQL завершилась ошибкой")
        return False
    return True
