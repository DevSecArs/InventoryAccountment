"""Контракт контейнерной конфигурации и разделения рабочих/тестовых команд."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest
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


@pytest.mark.parametrize(
    "target", ["setup", "up", "run", "down", "status", "migrate", "backup", "restore"]
)
def test_working_make_commands_pass_env_path_as_one_argument(tmp_path: Path, target: str) -> None:
    env_file = tmp_path / "settings space; $(touch injected).env"
    env_file.write_text("POSTGRES_PASSWORD=example-only\n", encoding="utf-8")
    result, arguments = run_mock_make(tmp_path, target, str(env_file))
    assert result.returncode == 0, result.stderr
    assert arguments.count("--env-file") >= 1
    for index, argument in enumerate(arguments):
        if argument == "--env-file":
            assert arguments[index + 1] == str(env_file)
    assert not (ROOT / "injected").exists()
    assert "example-only" not in result.stdout + result.stderr


@pytest.mark.parametrize("env_file", [None, ""])
def test_unset_or_empty_env_file_keeps_default_compose_behavior(
    tmp_path: Path, env_file: str | None
) -> None:
    result, arguments = run_mock_make(tmp_path, "down", env_file)
    assert result.returncode == 0, result.stderr
    assert "--env-file" not in arguments
    assert "down" in arguments


@pytest.mark.parametrize("directory", [False, True])
def test_invalid_env_file_stops_before_compose(tmp_path: Path, directory: bool) -> None:
    env_file = tmp_path / "private-settings"
    if directory:
        env_file.mkdir()
    result, arguments = run_mock_make(tmp_path, "down", str(env_file))
    assert result.returncode != 0
    assert not arguments
    assert "ENV_FILE" in result.stderr
    assert str(env_file) not in result.stderr


def test_test_cleanup_does_not_read_external_env_file(tmp_path: Path) -> None:
    result, arguments = run_mock_make(tmp_path, "test-clean", str(tmp_path / "missing.env"))
    assert result.returncode == 0, result.stderr
    assert "compose.test.env" in arguments
    assert str(tmp_path / "missing.env") not in arguments
    assert "inventory-check-env-contract" in arguments
    assert "inventory-live" not in arguments


def run_mock_make(
    tmp_path: Path, target: str, env_file: str | None
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    docker = tmp_path / "docker"
    docker.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@" >> "$COMPOSE_TEST_LOG"\n', encoding="utf-8")
    docker.chmod(0o700)
    log = tmp_path / "arguments"
    environment = os.environ.copy()
    environment.pop("ENV_FILE", None)
    if env_file is not None:
        environment["ENV_FILE"] = env_file
    environment["PATH"] = f"{tmp_path}{os.pathsep}{environment['PATH']}"
    environment["COMPOSE_TEST_LOG"] = str(log)
    executable = shutil.which("make")
    assert executable is not None, "Запустите тесты в Linux test-образе с GNU Make"
    result = subprocess.run(
        [
            executable,
            target,
            "TEST_RUN_ID=env-contract",
            "PROJECT_NAME=inventory-live",
            "BACKUP=backups/example.dump",
        ],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return result, log.read_text().splitlines() if log.exists() else []
