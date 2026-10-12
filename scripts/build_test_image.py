"""Собрать Unix test-образ без обхода локальных node_modules и секретов."""

from __future__ import annotations

import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "Dockerfile.tests",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "alembic.ini",
)
DIRECTORIES = ("app", "alembic", "tests", "scripts", "frontend")
EXCLUDED = {"node_modules", "__pycache__", ".venv", ".git", "dist"}


def add_source(archive: tarfile.TarFile, path: Path) -> None:
    """Исключить зависимости до чтения их метаданных, включая WSL-ссылки."""
    if path.name in EXCLUDED or path.name.startswith(".env"):
        return
    if path.is_symlink() or path.suffix in {".pyc", ".tsbuildinfo"}:
        return
    if path.is_dir():
        for child in sorted(path.iterdir()):
            add_source(archive, child)
    else:
        archive.add(path, arcname=path.relative_to(ROOT).as_posix(), recursive=False)


def main() -> None:
    with tempfile.TemporaryFile() as context:
        with tarfile.open(fileobj=context, mode="w:gz") as archive:
            for name in (*FILES, *DIRECTORIES):
                add_source(archive, ROOT / name)
        context.seek(0)
        subprocess.run(
            [
                "docker",
                "build",
                "--progress=plain",
                "-f",
                "Dockerfile.tests",
                "-t",
                "inventory-accountment-tests:local",
                "-",
            ],
            stdin=context,
            cwd=ROOT,
            check=True,
        )


if __name__ == "__main__":
    main()
