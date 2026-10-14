"""Контракт контейнерной конфигурации и разделения рабочих/тестовых команд."""

import shutil
import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url

from app.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_database_password_is_encoded_without_changing_credentials() -> None:
    password = "local:p@ss/word%?"
    settings = Settings(
        DATABASE_URL="",
        POSTGRES_HOST="db",
        POSTGRES_USER="inventory_app",
        POSTGRES_PASSWORD=password,
        POSTGRES_DB="inventory",
    )
    url = make_url(settings.DATABASE_URL)
    assert url.host == "db"
    assert url.port == 5432
    assert url.password == password
    assert url.database == "inventory"


def make_plan(*arguments: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("make")
    assert executable is not None, "Запустите тесты в Linux test-образе с GNU Make"
    return subprocess.run(
        [executable, "-n", *arguments, "TEST_RUN_ID=contract", "PROJECT_NAME=inventory-live"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_down_preserves_working_data_and_test_cleanup_uses_separate_project() -> None:
    working = make_plan("down")
    testing = make_plan("test-clean")
    assert working.returncode == testing.returncode == 0
    assert "--project-name inventory-live" in working.stdout
    assert "--volumes" not in working.stdout
    assert "--project-name inventory-check-contract" in testing.stdout
    assert "--volumes" in testing.stdout
    assert "--project-name inventory-live" not in testing.stdout


def test_removed_flag_is_rejected_instead_of_selecting_another_database() -> None:
    result = make_plan("down", "DOCKER=1")
    assert result.returncode != 0
    assert "compose" not in result.stdout
