#!/usr/bin/env python3
"""Выявление изменений, влияющих на критерии приёмки."""

import re
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args):
    return subprocess.check_output(["git", *args])


def critical(path):
    name = PurePosixPath(path).name
    frontend_config = {
        "frontend/package.json",
        "frontend/pnpm-lock.yaml",
        "frontend/pnpm-workspace.yaml",
        "frontend/vite.config.ts",
        "frontend/eslint.config.js",
        "frontend/prettier.config.mjs",
        "frontend/.prettierignore",
    }
    return (
        path.startswith((".github/", "scripts/", "tests/", "backend/tests/"))
        or (path.startswith("frontend/") and (
            test_file(path)
            or path.startswith("frontend/src/test/")
            or name.startswith("tsconfig") and name.endswith(".json")
            or path in frontend_config
        ))
        or path in {
            "AGENTS.md", "README.md", "Makefile",
            "Dockerfile", ".dockerignore", "docker-compose.yml",
            "backend/pyproject.toml", "backend/uv.lock",
        }
        or name.startswith(("Dockerfile", "docker-compose"))
    )


def test_file(path):
    name = PurePosixPath(path).name
    return (
        path.startswith(("backend/tests/", "tests/"))
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )



def needs_review(files):
    """Проверить новые и исходные пути файлов PR."""
    return any(
        critical(item["filename"])
        or critical(item.get("previous_filename", ""))
        for item in files
    )


def inspect(base, head):
    changes = git(
        "diff", "--name-status", "-z", "--find-renames",
        f"{base}...{head}",
    ).decode("utf-8", "surrogateescape").split("\0")

    issues = []
    index = 0

    while index < len(changes) and changes[index]:
        status = changes[index]
        index += 1
        old = changes[index]
        index += 1

        new = old
        if status.startswith(("R", "C")):
            new = changes[index]
            index += 1

        if not (critical(old) or critical(new)):
            continue

        issues.append(f"{status}: критический файл: {old}" +
                      (f" -> {new}" if old != new else ""))

        if status.startswith(("D", "R")) and test_file(old):
            issues.append(f"Удалён или переименован тест: {old}")

        if status.startswith("D"):
            continue

        diff = subprocess.run(
            ["git", "diff", "--unified=0", f"{base}...{head}", "--", new],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        patterns = {
            "Пропуск теста": r"\b(skip|skipif|xfail|todo|test\.skip|describe\.skip)\b",
            "Покрытие или исключения": r"\b(fail_under|thresholds?|coverage|exclude|omit)\b",
            "Отключение анализатора": r"\b(ignore|noqa|nosec|eslint-disable|semgrep|continue-on-error)\b",
            "Изменение проверки": r"\b(make test|make quality|pytest|ruff|mypy|bandit|pip-audit|mutmut)\b",
        }

        for line in diff.splitlines():
            if not line.startswith(("+", "-")) or line.startswith(("+++", "---")):
                continue
            for label, pattern in patterns.items():
                if re.search(pattern, line[1:], re.IGNORECASE):
                    action = "Добавлено" if line.startswith("+") else "Удалено"
                    issues.append(f"{action}: {label}: {new}")
                    break

    return list(dict.fromkeys(issues))


def main():
    strict = "--strict" in sys.argv[1:]
    args = [arg for arg in sys.argv[1:] if arg != "--strict"]
    if len(args) != 2:
        print("Использование: acceptance_policy.py [--strict] BASE HEAD", file=sys.stderr)
        return 2

    issues = inspect(args[0], args[1])
    if issues:
        print("Критические изменения: требуется обязательная проверка владельца:")
        for item in issues:
            print(f"- {item}")
        return 1 if strict else 0

    print("Критических изменений не обнаружено.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
