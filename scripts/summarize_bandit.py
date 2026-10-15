"""Вывести краткую сводку SAST по JSON-отчёту Bandit."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _finding_word(count: int) -> str:
    """Вернуть слово «уязвимость» в нужной форме."""
    last_two = count % 100
    last = count % 10
    if 11 <= last_two <= 14:
        return "уязвимостей"
    if last == 1:
        return "уязвимость"
    if 2 <= last <= 4:
        return "уязвимости"
    return "уязвимостей"


def main() -> int:
    report_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports/bandit.json")
    scan_status = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print("+--------------------- SAST ---------------------+")
    print("Тип: Bandit — статический анализ Python-кода.")
    print("Область: результаты уровня High (настройка Bandit -lll).")

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        findings = report["results"]
        scan_errors = report.get("errors", [])
        if not isinstance(findings, list) or not isinstance(scan_errors, list):
            raise ValueError("поля results/errors в отчёте должны быть списками")
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        print(f"Результат: отчёт не удалось прочитать ({error}).")
        print(f"Отчёт: {report_path}")
        print("+------------------------------------------------+")
        return 1

    count = len(findings)
    if count:
        print(f"Результат: найдено {count} {_finding_word(count)}.")
    elif scan_errors:
        print(
            "Результат: Bandit сообщил об ошибках анализа "
            f"({len(scan_errors)}); чистым прогон считать нельзя."
        )
    elif scan_status == 0:
        print("Результат: уязвимостей не найдено — всё чисто.")
    else:
        print(
            f"Результат: Bandit завершился с кодом {scan_status}; подтвердить чистоту не удалось."
        )
    if scan_errors:
        print(f"Ошибок анализа Bandit: {len(scan_errors)}.")
    print(f"Отчёт: {report_path}")
    print("+------------------------------------------------+")
    return 1 if count or scan_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
