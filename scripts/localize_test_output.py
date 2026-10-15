"""Запустить команду проверки и перевести основные подписи её вывода на русский."""

from __future__ import annotations

import re
import subprocess
import sys


def localize(output: str) -> str:
    """Перевести итоговые подписи pytest и Vitest, сохранив диагностические данные."""
    replacements = (
        (r"(?m)^collected (\d+) items?$", r"Собрано тестов: \1"),
        (r"(?m)^=+ test session starts =+$", "=" * 15 + " начало проверки " + "=" * 15),
        (r"(?m)^=+ warnings summary =+$", "=" * 15 + " сводка предупреждений " + "=" * 15),
        (r"(?m)^=+ short test summary info =+$", "=" * 10 + " краткая сводка тестов " + "=" * 10),
        (r"(?m)^=+ tests coverage =+$", "=" * 15 + " покрытие тестами " + "=" * 15),
        (
            r"(?m)^Required test coverage of ([\d.]+%) reached\. Total coverage: ([\d.]+%)$",
            r"Минимальное покрытие (\1) достигнуто. Общее покрытие: \2",
        ),
        (r"(?m)^\s*Tests\s+(\d+) passed(?: \((\d+)\))?$", r"      Успешно тестов: \1 (из \2)"),
        (r"(?m)^\s*Test Files\s+(\d+) passed(?: \((\d+)\))?$", r"Успешно файлов: \1 (из \2)"),
        (r"(?m)^\s*Start at:", "  Начало:"),
        (r"(?m)^\s*Duration:", "  Длительность:"),
        (r"(?m)^JUNIT report written to", "Отчёт JUnit сохранён в"),
        (r"(?m)^generated xml file:", "Создан XML-отчёт:"),
    )
    localized = output
    for pattern, replacement in replacements:
        localized = re.sub(pattern, replacement, localized)

    # Переводим итоговые числа, сохраняя все поля, которые вывел инструмент.
    localized = re.sub(
        (
            r"(?m)^=+ (\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?"
            r"(?:, (\d+) warnings?)? in ([\d.]+s) =+$"
        ),
        lambda match: (
            f"Итог: успешно — {match[1]}; ошибок — {match[2] or '0'}; "
            f"пропущено — {match[3] or '0'}; предупреждений — {match[4] or '0'}; "
            f"время — {match[5]}"
        ),
        localized,
    )
    localized = re.sub(
        r"(?m)^\s*(\d+) passed, (\d+) failed(?:, (\d+) skipped)?$",
        lambda match: f"Успешно: {match[1]}; ошибок: {match[2]}; пропущено: {match[3] or '0'}",
        localized,
    )
    return localized


def main() -> int:
    command = sys.argv[1:]
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("Укажите команду проверки после --", file=sys.stderr)
        return 2

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    sys.stdout.write(localize(result.stdout))
    sys.stderr.write(localize(result.stderr))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
