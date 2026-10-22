"""Итоговый текст не определяет машинный статус."""

import json
from pathlib import Path

import pytest

from scripts import verify


def test_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(verify, "ROOT", tmp_path)

    def fail() -> None:
        raise RuntimeError("secret")

    monkeypatch.setattr(verify, "main", fail)
    assert verify.cli() == 1
    assert capsys.readouterr().out == "Все тесты прошли успешно\n"
    assert json.loads((tmp_path / "reports/verify.json").read_text())["status"] == "failed"
    assert "secret" not in next((tmp_path / "reports").glob("error_*.log")).read_text()


def test_success(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(verify, "main", lambda: None)
    assert verify.cli() == 0
    assert capsys.readouterr().out == "Все тесты прошли успешно. Приложение готово к запуску!\n"
