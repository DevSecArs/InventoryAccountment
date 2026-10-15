"""Не позволять мутационным тестам проверять исходную копию приложения."""

import os
import sys
from pathlib import Path

import pytest


def pytest_runtest_setup() -> None:
    """Проверить происхождение модулей перед каждым тестом в дочернем процессе."""
    expected = Path(os.environ["MUTATION_APP_ROOT"]).resolve()
    target = os.environ["MUTATION_MODULE"]
    if target not in sys.modules:
        pytest.exit("Целевой модуль мутации не импортирован тестом", returncode=4)
    for name, module in tuple(sys.modules.items()):
        if name == "app" or name.startswith("app."):
            filename = getattr(module, "__file__", None)
            if filename is None or not Path(filename).resolve().is_relative_to(expected):
                pytest.exit(f"Нарушена изоляция мутации: модуль {name}", returncode=4)
