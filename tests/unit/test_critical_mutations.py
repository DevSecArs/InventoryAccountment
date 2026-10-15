"""Регрессии реального дочернего pytest, включая конкурирующую исходную копию."""

import shutil
from pathlib import Path

import pytest

from scripts import check_critical_mutations as runner


@pytest.fixture
def mutation_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "app").mkdir()
    (tmp_path / "app/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app/rule.py").write_text(
        "def valid(value):\n    return value > 0\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "tests/test_rule.py").write_text(
        "from app.rule import valid\ndef test_zero():\n    assert not valid(0)\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir()
    shutil.copyfile(
        runner.ROOT / "scripts/mutation_import_guard.py",
        tmp_path / "scripts/mutation_import_guard.py",
    )
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    return tmp_path


def mutation(replacement: str = "value >= 0") -> runner.CriticalMutation:
    return runner.CriticalMutation(
        "zero",
        "rule.py",
        "value > 0",
        replacement,
        "tests/test_rule.py::test_zero",
        "AssertionError",
    )


def test_mutated_copy_is_executed_instead_of_original(mutation_project: Path) -> None:
    runner._run_mutation(mutation())
    assert "value > 0" in (mutation_project / "app/rule.py").read_text(encoding="utf-8")


def test_surviving_mutation_is_rejected(mutation_project: Path) -> None:
    with pytest.raises(SystemExit, match="пережила"):
        runner._run_mutation(mutation("value > 1"))


def test_failing_baseline_is_not_counted_as_killed(mutation_project: Path) -> None:
    (mutation_project / "tests/test_rule.py").write_text(
        "from app.rule import valid\ndef test_zero():\n    assert valid(0)\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="Исходный тест"):
        runner._run_mutation(mutation())


def test_guard_rejects_import_from_original_tree(mutation_project: Path, tmp_path: Path) -> None:
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    # Копии app нет: Python найдёт исходную app из второго пути PYTHONPATH.
    result = runner._run_test(mutation(), isolated)
    assert result.returncode == 4
    assert "Нарушена изоляция мутации" in result.stdout + result.stderr
