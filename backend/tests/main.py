"""Единый последовательный запуск всех backend-тестов с русским выводом."""

from __future__ import annotations

import contextlib
import io
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent


class TestOutput:
    """Плагин pytest для вывода и учёта результатов тестовых случаев."""

    def __init__(self) -> None:
        self.current_file: str | None = None
        self.file_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        self.total_passed = 0
        self.total_failed = 0
        self.seen: set[str] = set()
        self.reports: dict[str, dict[str, Any]] = defaultdict(dict)
        self.buffers: dict[str, tuple[io.StringIO, io.StringIO]] = {}

    @staticmethod
    def _write(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    @staticmethod
    def _relative_path(path: str | Path) -> str:
        return Path(path).resolve().relative_to(ROOT).as_posix()

    @staticmethod
    def _description(path: str | Path) -> str:
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
        return labels.get(Path(path).name, "Файл тестов")

    def pytest_collection_modifyitems(self, items: list[Any]) -> None:
        items.sort(key=lambda item: (str(item.path), item.nodeid))

    def pytest_runtest_logstart(self, nodeid: str, location: tuple[str, int, str]) -> None:
        path = self._relative_path(location[0])
        if path != self.current_file:
            self._finish_file()
            self.current_file = path
            self._write(f"\n=========={self._description(path)} / {path}==========\n")
        identifier = nodeid.split("::")[-1]
        self._write(f"----------Тест / {identifier}----------\n")
        self.buffers[nodeid] = (io.StringIO(), io.StringIO())

    def pytest_runtest_call(self, item: Any) -> Any:
        output, errors = self.buffers[item.nodeid]
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            yield

    def pytest_runtest_logreport(self, report: Any) -> None:
        self.reports[report.nodeid][report.when] = report
        if report.when != "teardown":
            return
        phases = self.reports.pop(report.nodeid, {})
        self._print_test_output(report.nodeid)
        final = next(
            (phases[phase] for phase in ("setup", "call", "teardown")
             if phase in phases and phases[phase].failed),
            None,
        )
        if final:
            self._record(report.nodeid, "ПРОВАЛ", final.longrepr)
        else:
            call = phases.get("call")
            skipped = next((phase for phase in phases.values() if phase.skipped), None)
            if call is not None and getattr(call, "wasxfail", False):
                self._record(report.nodeid, "ОЖИДАЕМОЕ ПАДЕНИЕ", call.wasxfail)
            elif skipped is not None:
                self._record(report.nodeid, "ПРОПУСК", skipped.longrepr)
            else:
                self._record(report.nodeid, "УСПЕШНО")

    def _record(self, nodeid: str, status: str, detail: Any = None) -> None:
        if nodeid in self.seen:
            return
        self.seen.add(nodeid)
        if status in {"УСПЕШНО", "ПРОВАЛ"}:
            counts = self.file_counts[self.current_file or ""]
            index = 0 if status == "УСПЕШНО" else 1
            counts[index] += 1
            if index == 0:
                self.total_passed += 1
            else:
                self.total_failed += 1
        self._write(f"Результат: {status}\n")
        if detail:
            self._write(f"{detail}\n")

    def _print_test_output(self, nodeid: str) -> None:
        for buffer in self.buffers.pop(nodeid, ()):
            content = buffer.getvalue()
            if content:
                self._write(content if content.endswith("\n") else f"{content}\n")

    def pytest_collectreport(self, report: Any) -> None:
        if report.failed:
            self._write(f"Ошибка сбора тестов: {report.longrepr}\n")

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        self._finish_file()
        if not self.seen:
            self._write("Ошибка сессии: pytest не обнаружил тестовых случаев.\n")
        if exitstatus == 1 and self.total_failed == 0:
            self._write(
                "Ошибка сессии: настройка окружения или проверка покрытия завершились ошибкой.\n"
            )
        elif exitstatus not in (0, 1):
            self._write(f"Ошибка сессии: pytest завершился с кодом {exitstatus}.\n")
        self._write(f"Результат: успешно — {self.total_passed}, провально — {self.total_failed}\n")

    def _finish_file(self) -> None:
        if self.current_file is not None:
            passed, failed = self.file_counts[self.current_file]
            self._write(f"Результат файла: успешно — {passed}, провально — {failed}\n")
            self.current_file = None


def main() -> int:
    """Запустить найденные backend-тесты одной pytest-сессией."""
    try:
        import pytest
    except ImportError:
        print("Не найден pytest. Подготовьте backend-окружение по README.md.", file=sys.stderr)
        return 2
    hook = pytest.hookimpl(hookwrapper=True)(TestOutput.pytest_runtest_call)
    TestOutput.pytest_runtest_call = hook  # type: ignore[method-assign]

    reports = Path(os.environ.get("REPORTS_DIR", ROOT / "reports")).resolve()
    try:
        reports.mkdir(parents=True, exist_ok=True)
        os.chdir(BACKEND)
    except OSError as error:
        print(f"Ошибка подготовки каталога отчётов: {error}", file=sys.stderr)
        return 2

    plugin = TestOutput()
    arguments = [
        "-o", "addopts=", "-x", "-q", "--capture=sys", "--strict-markers", "--cov=app.entities",
        "--cov-report=term-missing", f"--cov-report=xml:{reports / 'coverage.xml'}",
        f"--cov-report=html:{reports / 'htmlcov'}", f"--junitxml={reports / 'junit.xml'}",
        "--cov-fail-under=80", "tests",
    ]
    result = pytest.main(arguments, plugins=[plugin])
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
