"""Точка входа для команды ``uvicorn app.main:app``."""

from app.http import app


__all__ = ("app",)
