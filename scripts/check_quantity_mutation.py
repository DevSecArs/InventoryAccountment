"""Проверяет, что API-тесты уничтожают ослабление проверки количества."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "if not value > 0:"
MUTATION = "if not value >= 0:"
TEST = "tests/integration/test_receipts.py::test_receipt_rejects_invalid_items"


def main() -> None:
    """Запускает целевой тест с временной семантической мутацией исходника."""
    with tempfile.TemporaryDirectory(prefix="receipt-quantity-mutation-") as directory:
        temporary_root = Path(directory)
        temporary_app = temporary_root / "app"
        shutil.copytree(ROOT / "app", temporary_app)

        mutated_file = temporary_app / "entities" / "receipt.py"
        content = mutated_file.read_text(encoding="utf-8")
        if ORIGINAL not in content:
            raise RuntimeError("Не найдено исходное условие проверки количества")
        mutated_file.write_text(content.replace(ORIGINAL, MUTATION, 1), encoding="utf-8")

        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join((str(temporary_root), str(ROOT)))
        environment["PYTEST_ADDOPTS"] = "--no-cov"
        result = subprocess.run(  # nosec B603: фиксированный локальный запуск pytest
            [sys.executable, "-m", "pytest", str(ROOT / TEST)],
            cwd=temporary_root,
            env=environment,
            check=False,
            text=True,
            capture_output=True,
        )

    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    if result.returncode == 0:
        raise SystemExit("Мутация quantity > 0 -> quantity >= 0 пережила тест")
    if "1 failed" not in result.stdout:
        raise SystemExit("Целевой API-тест не выполнился при проверке мутации")
    print("Мутация quantity > 0 -> quantity >= 0 уничтожена целевым API-тестом")


if __name__ == "__main__":
    main()
