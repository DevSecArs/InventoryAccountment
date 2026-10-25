"""Единый последовательный запуск backend-тестов с русским выводом."""

from __future__ import annotations

import contextlib
import io
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
REPORTS = ROOT / "reports"


class TestOutput:
    """Плагин pytest для вывода и подсчёта результатов отдельных случаев."""

    def __init__(self) -> None:
        self.current_file: str | None = None
        self.file_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        self.total_passed = 0
        self.total_failed = 0
        self.seen: set[str] = set()
        self.buffers: dict[str, tuple[io.StringIO, io.StringIO]] = {}

    @staticmethod
    def _write(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    @staticmethod
    def _node_file(item: Any) -> str:
        return Path(str(item.path)).resolve().relative_to(ROOT).as_posix()

    @staticmethod
    def _description(nodeid: str) -> str:
        identifier = nodeid.split("::")[-1]
        labels = {
            "test_password_verification.py": "Проверка паролей",
            "test_application_lifecycle.py": "Жизненный цикл приложения",
            "test_compose_configuration.py": "Конфигурация подключения",
            "test_supply_report.py": "Формирование отчётов",
            "test_validation.py": "Проверка данных",
            "test_api_catalogs.py": "Справочники API",
            "test_receipt_posting.py": "Проведение поступлений",
            "test_receipts.py": "Поступления",
            "test_supply_reports.py": "Отчёты по поставкам",
        }
        return labels.get(Path(nodeid.split("::")[0]).name, "Тест")

    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        items.sort(key=lambda item: (self._node_file(item), item.nodeid))

    def pytest_runtest_logstart(self, nodeid: str, location: tuple[str, int, str]) -> None:
        file_path = Path(location[0]).resolve().relative_to(ROOT).as_posix()
        if file_path != self.current_file:
            self._finish_file()
            self.current_file = file_path
            title = self._description(nodeid)
            self._write(f"\n=========={title} / {file_path}==========\n")
        identifier = nodeid.split("::")[-1]
        self._write(f"----------Тест / {identifier}----------\n")
        self.buffers[nodeid] = (io.StringIO(), io.StringIO())

    @contextlib.contextmanager
    def pytest_runtest_call(self, item: Any) -> Any:
        output, errors = self.buffers[item.nodeid]
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            yield

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when == "teardown":
            self._print_test_output(report.nodeid)
        if report.when == "setup" and report.failed:
            self._record(report.nodeid, False)
        elif report.when == "call":
            self._record(report.nodeid, report.passed)
        elif report.when == "teardown" and report.failed:
            self._record(report.nodeid, False)

    def _record(self, nodeid: str, passed: bool) -> None:
        if nodeid in self.seen:
            if not passed:
                self.file_counts[self.current_file or ""][0] -= 1
                self.file_counts[self.current_file or ""][1] += 1
                self.total_passed -= 1
                self.total_failed += 1
                self._write("Результат: ПРОВАЛ (ошибка очистки)\n")
            return
        self.seen.add(nodeid)
        file_path = self.current_file or ""
        counts = self.file_counts[file_path]
        if passed:
            counts[0] += 1
            self.total_passed += 1
            self._write("Результат: УСПЕШНО\n")
        else:
            counts[1] += 1
            self.total_failed += 1
            self._write("Результат: ПРОВАЛ\n")

    def _print_test_output(self, nodeid: str) -> None:
        for buffer in self.buffers.pop(nodeid, ()):
            content = buffer.getvalue()
            if content:
                self._write(content if content.endswith("\n") else f"{content}\n")

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        self._finish_file()
        if exitstatus == 0 and self.total_passed == 0:
            self._write("Ошибка сессии: pytest не обнаружил тестов.\n")
        elif exitstatus == 1 and self.total_failed == 0:
            self._write("Ошибка сессии: сбор, настройка окружения или проверка покрытия завершились ошибкой.\n")
        self._write(f"Результат: успешно — {self.total_passed}, провально — {self.total_failed}\n")

    def _finish_file(self) -> None:
        if self.current_file is not None:
            passed, failed = self.file_counts[self.current_file]
            self._write(f"Результат файла: успешно — {passed}, провально — {failed}\n")
            self.current_file = None


def main() -> int:
    """Запустить оба набора backend-тестов в одной сессии pytest."""
    try:
        import pytest
    except ImportError:
        print("Не найден pytest. Подготовьте backend-окружение по README.md.", file=sys.stderr)
        return 2

    REPORTS.mkdir(exist_ok=True)
    os.chdir(BACKEND)
    plugin = TestOutput()
    result = pytest.main(
        ["-x", "-q", "--capture=sys", "tests/unit", "tests/integration"],
        plugins=[plugin],
    )
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
