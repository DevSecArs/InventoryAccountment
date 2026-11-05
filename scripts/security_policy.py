"""Проверка severity в отчётах сканеров."""

import json
import sys


def blocks(scanner, report):
    if scanner == "trivy":
        entries = (entry for result in report["Results"] or [] for entry in result.get("Vulnerabilities", []) or [])
        return any(str(entry.get("Severity") or "").upper() not in {"LOW", "MEDIUM"} for entry in entries)
    raise ValueError("Неизвестный сканер")


def classify(scanner, report, code):
    if scanner == "gitleaks":
        if code not in (0, 1) or not isinstance(report, list):
            return "ERROR"
        if any(not isinstance(entry, dict) or not entry.get("RuleID") for entry in report):
            return "ERROR"
        if bool(report) != (code == 1):
            return "ERROR"
        return "FINDINGS" if report else "SUCCESS"
    if scanner == "pip-audit":
        if code not in (0, 1) or not isinstance(report, dict) or not isinstance(report.get("dependencies"), list):
            return "ERROR"
        dependencies = report["dependencies"]
        if not dependencies or any(not isinstance(item, dict) or not isinstance(item.get("vulns"), list) for item in dependencies):
            return "ERROR"
        found = any(item["vulns"] for item in dependencies)
        if found != (code == 1):
            return "ERROR"
        return "FINDINGS" if found else "SUCCESS"
    if scanner == "trivy":
        if code != 0 or not isinstance(report, dict) or report.get("SchemaVersion") != 2 or not isinstance(report.get("Results"), list):
            return "ERROR"
        if not any(isinstance(item, dict) and item.get("Class") == "os-pkgs" and item.get("Type") for item in report["Results"]):
            return "ERROR"
        if any(not isinstance(item, dict) or not item.get("Target") or not isinstance(item.get("Vulnerabilities", []), list) for item in report["Results"]):
            return "ERROR"
    else:
        return "ERROR"
    found = blocks(scanner, report)
    return "FINDINGS" if found else "SUCCESS"


if __name__ == "__main__":
    try:
        with open(sys.argv[2], encoding="utf-8") as source:
            report = json.load(source)
        print(classify(sys.argv[1], report, int(sys.argv[3])))
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        print("ERROR")
