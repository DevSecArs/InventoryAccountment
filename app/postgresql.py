"""Настройка подключения к PostgreSQL и управление транзакциями."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Базовый класс декларативных моделей приложения."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Создать единственный engine."""
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=settings.APP_DEBUG,
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    """Вернуть фабрику сессий."""
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


def get_db_session():
    """Предоставить запросу транзакционную сессию PostgreSQL."""
    with session_scope() as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_db_session)]


def is_database_ready() -> bool:
    """Проверить, что PostgreSQL принимает простой запрос."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, RuntimeError, ImportError):
        logger.exception("Проверка готовности PostgreSQL завершилась ошибкой")
        return False
    return True