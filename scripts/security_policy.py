"""Проверка severity в отчётах сканеров."""

import json
import sys


def blocks(scanner, report):
    if scanner == "pnpm":
        entries = report["advisories"].values()
        return any(entry.get("severity", "").lower() not in {"low", "moderate"} for entry in entries)
    if scanner == "trivy":
        entries = (entry for result in report["Results"] or [] for entry in result.get("Vulnerabilities", []) or [])
        return any(entry.get("Severity", "").upper() not in {"LOW", "MEDIUM"} for entry in entries)
    raise ValueError("Неизвестный сканер")


if __name__ == "__main__":
    with open(sys.argv[2], encoding="utf-8") as source:
        report = json.load(source)
    result = blocks(sys.argv[1], report)
    print(f"{sys.argv[1]}: {'блокирующие находки' if result else 'блокирующих находок нет'}")
    sys.exit(int(result))
