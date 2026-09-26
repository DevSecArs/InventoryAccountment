"""Проверяет, что тесты блокируют ослабление критических бизнес-правил."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
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
        "tests/integration/test_receipts.py::test_receipt_rejects_invalid_items",
        "AssertionError",
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
        'if receipt.status != "draft":',
        "if False:",
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


def _run_mutation(mutation: CriticalMutation) -> None:
    """Потребовать ожидаемую причину отказа целевого теста для мутации."""
    with tempfile.TemporaryDirectory(prefix="critical-mutation-") as directory:
        temporary_root = Path(directory)
        shutil.copytree(ROOT / "app", temporary_root / "app")
        _mutate_copy(mutation, temporary_root)
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join((str(temporary_root), str(ROOT)))
        environment["PYTEST_ADDOPTS"] = "--no-cov"
        try:
            result = subprocess.run(  # nosec B603: фиксированный локальный запуск pytest
                [sys.executable, "-m", "pytest", str(ROOT / mutation.test)],
                cwd=temporary_root,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
                timeout=TEST_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as error:
            raise SystemExit(
                f"Мутация «{mutation.name}» превысила лимит {TEST_TIMEOUT_SECONDS} секунд"
            ) from error

    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    test_name = mutation.test.rsplit("::", maxsplit=1)[-1]
    if result.returncode == 0:
        raise SystemExit(f"Мутация «{mutation.name}» пережила целевой тест")
    if test_name not in result.stdout or mutation.expected_failure not in result.stdout:
        raise SystemExit(
            f"Мутация «{mutation.name}» завершилась не ожидаемой причиной отказа целевого теста"
        )
    print(f"Мутация «{mutation.name}» уничтожена целевым тестом")


def main() -> None:
    """Последовательно проверить все критические мутации."""
    for mutation in MUTATIONS:
        _run_mutation(mutation)


if __name__ == "__main__":
    main()
