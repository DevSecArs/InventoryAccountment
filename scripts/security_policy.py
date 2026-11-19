"""Проверка severity в отчётах сканеров."""

import json
import sys


# Только две исторические синтетические фикстуры; новые исходники не исключаются.
HISTORICAL_TEST_FINDINGS = {
    "a396cee7fd2e116cb57a8e5287c425cd83f3adee:backend/tests/unit/test_observability.py:generic-api-key:142": 142,
    "efe9d944c8df0c4d0952c54e05ec3f087bc85c2a:backend/tests/unit/test_observability.py:generic-api-key:108": 108,
}


def is_historical_test_finding(entry):
    fingerprint = entry.get("Fingerprint")
    if fingerprint not in HISTORICAL_TEST_FINDINGS:
        return False
    commit, path, rule, _ = fingerprint.split(":")
    line = HISTORICAL_TEST_FINDINGS[fingerprint]
    return (
        entry.get("Commit") == commit
        and entry.get("File") == path
        and entry.get("RuleID") == rule
        and entry.get("StartLine") == line
        and entry.get("EndLine") == line
    )


def blocks(scanner, report):
    if scanner == "trivy":
        entries = (entry for result in report["Results"] or [] for entry in result.get("Vulnerabilities", []) or [])
        return any(str(entry.get("Severity") or "").upper() not in {"LOW", "MEDIUM"} for entry in entries)
    raise ValueError("Неизвестный сканер")


def classify(scanner, report, code):
    if scanner in ("gitleaks", "gitleaks-history"):
        if code not in (0, 1) or not isinstance(report, list):
            return "ERROR"
        if any(not isinstance(entry, dict) or not entry.get("RuleID") for entry in report):
            return "ERROR"
        if bool(report) != (code == 1):
            return "ERROR"
        if scanner == "gitleaks-history" and report:
            if all(is_historical_test_finding(entry) for entry in report):
                return "SUCCESS_WITH_EXCEPTIONS"
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
