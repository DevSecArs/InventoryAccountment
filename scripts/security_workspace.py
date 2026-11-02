"""Создание копии исходников без локальных секретов и рабочих данных."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root, work, env_report = map(Path, sys.argv[1:])
    root = root.resolve()
    work = work.resolve()
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    files = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root
    ).split(b"\0")
    bad_env = []
    failed = False
    excluded = {"node_modules", ".venv", "venv", ".pnpm-store", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "backups", "dumps", "volumes", ".data", ".git"}
    for raw in tracked:
        if raw:
            path = Path(os.fsdecode(raw))
            if any(part.startswith(".env") and part != ".env.example" for part in path.parts):
                bad_env.append(os.fsdecode(raw))
    env_report.write_text("".join(repr(name) + "\n" for name in bad_env), encoding="utf-8")
    failed = bool(bad_env)
    for raw in files:
        if not raw:
            continue
        path = Path(os.fsdecode(raw))
        parts = path.parts
        if not parts or path.is_absolute() or ".." in parts:
            failed = True
            continue
        if parts[0] == "reports" or any(part in excluded for part in parts):
            continue
        if any(part.startswith(".env") and part != ".env.example" for part in parts):
            continue
        if any(part in {"credentials", "secrets"} for part in parts):
            failed = True
            continue
        source = root / path
        if source == work or work in source.parents:
            continue
        if any((root.joinpath(*parts[:i])).is_symlink() for i in range(1, len(parts) + 1)):
            failed = True
            continue
        if not source.is_file():
            continue
        target = work / "source" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    if failed:
        print("Ошибка: обнаружены отслеживаемые env-файлы, credentials или ссылки.", file=sys.stderr)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
