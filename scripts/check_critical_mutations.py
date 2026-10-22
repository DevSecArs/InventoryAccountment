"""Проверяет, что тесты блокируют ослабление критических бизнес-правил."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class CriticalMutation:
    """Одна осмысленная мутация и тест, который обязан её обнаружить."""

    name: str
    relative_path: str
    original: str
    replacement: str
    test: str
    expected_failure: str


MUTATIONS = (
    CriticalMutation(
        "quantity > 0 -> quantity >= 0",
        "entities/receipt.py",
        "if not value > 0:",
        "if not value >= 0:",
        "tests/unit/test_validation.py::test_receipt_quantity_zero_rejected",
        "DID NOT RAISE",
    ),
    CriticalMutation(
        "проверка уникальности материала отключена",
        "entities/receipt.py",
        "if len({item.material_id for item in values}) != len(values):",
        "if False:",
        "tests/unit/test_validation.py::test_receipt_items_reject_duplicate_material_ids_before_database_access",
        "DID NOT RAISE ValueError",
    ),
    CriticalMutation(
        "разрешён архивный поставщик",
        "entities/supplier.py",
        ".filter(Supplier.id == supplier_id, Supplier.archived_at.is_(None))",
        ".filter(Supplier.id == supplier_id)",
        "tests/integration/test_receipts.py::test_receipt_rejects_archived_links",
        "AssertionError",
    ),
    CriticalMutation(
        "разрешён архивный материал",
        "entities/material.py",
        ".filter(Material.id == material_id, Material.archived_at.is_(None))",
        ".filter(Material.id == material_id)",
        "tests/integration/test_receipts.py::test_receipt_rejects_archived_links",
        "AssertionError",
    ),
    CriticalMutation(
        "разрешено редактирование нечерновика",
        "entities/receipt.py",
        'if receipt.status != "draft":\n        raise ValueError("Изменять можно только черновик")',
        'if False:\n        raise ValueError("Изменять можно только черновик")',
        "tests/integration/test_receipts.py::test_receipt_update_rolls_back_conflicts_and_rejects_non_draft",
        "AssertionError",
    ),
    CriticalMutation(
        "проверка CSRF отключена",
        "entities/auth.py",
        'if not hmac.compare_digest(request.headers.get(CSRF_HEADER, ""), session.csrf_token):',
        "if False:",
        "tests/integration/test_api_catalogs.py::test_authentication_and_csrf_are_required",
        "AssertionError",
    ),
    CriticalMutation(
        "проверка роли администратора отключена",
        "entities/auth.py",
        'if user.role != "admin":',
        "if False:",
        "tests/integration/test_api_catalogs.py::test_non_admin_cannot_purge_archived_catalog",
        "AssertionError",
    ),
    CriticalMutation(
        "readiness успешен при недоступной БД",
        "http.py",
        "if not is_database_ready():",
        "if False:",
        "tests/integration/test_api_catalogs.py::test_readiness_reports_database_unavailable",
        "AssertionError",
    ),
)


def _mutate_copy(mutation: CriticalMutation, temporary_root: Path) -> None:
    """Заменить ровно одно критическое условие во временной копии приложения."""
    target = temporary_root / "app" / mutation.relative_path
    content = target.read_text(encoding="utf-8")
    occurrences = content.count(mutation.original)
    if occurrences != 1:
        raise RuntimeError(
            f"Для мутации «{mutation.name}» найдено условий: {occurrences}, ожидалось одно"
        )
    target.write_text(content.replace(mutation.original, mutation.replacement), encoding="utf-8")


def _run_test(
    mutation: CriticalMutation, temporary_root: Path, phase: str = "baseline"
) -> subprocess.CompletedProcess[str]:
    """Запустить тест с неизменяемым порядком импорта и проверкой происхождения кода."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(temporary_root), str(ROOT)))
    environment["PYTEST_ADDOPTS"] = "--no-cov"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["MUTATION_APP_ROOT"] = str(temporary_root / "app")
    environment["MUTATION_MODULE"] = "app." + mutation.relative_path.removesuffix(".py").replace(
        "/", "."
    )
    started = time.monotonic()
    try:
        result = subprocess.run(  # nosec B603: фиксированный локальный запуск pytest
            [
                sys.executable,
                "-m",
                "pytest",
                "--import-mode=importlib",
                "-p",
                "scripts.mutation_import_guard",
                str(ROOT / mutation.test),
            ],
            cwd=temporary_root,
            env=environment,
            check=False,
            text=True,
            capture_output=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        category = "timeout" if isinstance(error, subprocess.TimeoutExpired) else "launch"
        save_phase(mutation, phase, started, None, category)
        raise SystemExit(f"Мутация «{mutation.name}», {phase}: {category}") from None
    save_phase(mutation, phase, started, result.returncode, "completed")
    return result


def save_phase(
    mutation: CriticalMutation, phase: str, started: float, code: int | None, category: str
) -> None:
    directory = ROOT / "reports/mutations"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / f"{uuid.uuid4().hex}-{phase}.json"
    report.write_text(
        json.dumps(
            {
                "mutation": mutation.name,
                "test": mutation.test,
                "phase": phase,
                "duration": time.monotonic() - started,
                "limit": TEST_TIMEOUT_SECONDS,
                "code": code,
                "category": category,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def save_result(mutation: CriticalMutation, result: subprocess.CompletedProcess[str]) -> None:
    """Писать безопасную сводку без repr фикстур и токенов из traceback."""
    directory = ROOT / "reports/mutations"
    directory.mkdir(parents=True, exist_ok=True)
    report = directory / (
        mutation.relative_path.replace("/", "_") + "-" + mutation.test.rsplit("::", 1)[-1] + ".log"
    )
    test_name = mutation.test.rsplit("::", 1)[-1]
    report.write_text(
        f"Код: {result.returncode}\n"
        f"Целевой тест в stdout: {test_name in result.stdout}\n"
        f"Ожидаемая причина в stdout: {mutation.expected_failure in result.stdout}\n"
        f"stderr присутствует: {bool(result.stderr)}\n",
        encoding="utf-8",
    )
    print(f"Диагностика: {report}", flush=True)


def _run_mutation(mutation: CriticalMutation) -> None:
    """Проверить исходный тест, затем потребовать обнаружение изменения поведения."""
    with tempfile.TemporaryDirectory(prefix="critical-mutation-") as directory:
        temporary_root = Path(directory)
        shutil.copytree(
            ROOT / "app",
            temporary_root / "app",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        print(f"Baseline: {mutation.name}", flush=True)
        baseline = _run_test(mutation, temporary_root)
        if baseline.returncode != 0:
            save_result(mutation, baseline)
            raise SystemExit(f"Исходный тест для мутации «{mutation.name}» не прошёл")
        _mutate_copy(mutation, temporary_root)
        print(f"Изменённая копия: {mutation.name}", flush=True)
        result = _run_test(mutation, temporary_root, "mutation")

    save_result(mutation, result)
    test_name = mutation.test.rsplit("::", maxsplit=1)[-1]
    if result.returncode == 0:
        raise SystemExit(f"Мутация «{mutation.name}» пережила целевой тест")
    if (
        result.returncode != 1
        or test_name not in result.stdout
        or mutation.expected_failure not in result.stdout
    ):
        raise SystemExit(
            f"Мутация «{mutation.name}» завершилась не ожидаемой причиной отказа целевого теста"
        )
    print(f"OK: мутация обнаружена целевым тестом: {mutation.name}")


def main() -> None:
    """Последовательно проверить все критические мутации."""
    print(
        "На временной копии приложения намеренно изменяется условие. Падение целевого "
        "теста ожидаемо только при заданной причине: оно означает, что тест обнаружил "
        "дефект. Отказ исходного теста или неожиданная ошибка означают сбой проверки.",
        flush=True,
    )
    for mutation in MUTATIONS:
        _run_mutation(mutation)


if __name__ == "__main__":
    main()
