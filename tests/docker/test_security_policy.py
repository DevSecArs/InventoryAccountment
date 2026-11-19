"""Проверки блокировки severity в отчётах."""

import unittest

from scripts.security_policy import blocks, classify


class SecurityPolicyTests(unittest.TestCase):
    def test_scanner_outcomes(self):
        self.assertEqual(classify("gitleaks", [], 0), "SUCCESS")
        self.assertEqual(classify("gitleaks", [{"RuleID": "fixture"}], 1), "FINDINGS")
        self.assertEqual(classify("gitleaks", [], 1), "ERROR")
        self.assertEqual(classify("gitleaks", [], 2), "ERROR")
        clean = {"SchemaVersion": 2, "Results": [{"Target": "image", "Class": "os-pkgs", "Type": "alpine"}]}
        finding = {"SchemaVersion": 2, "Results": [{"Target": "image", "Class": "os-pkgs", "Type": "alpine", "Vulnerabilities": [{"Severity": "HIGH"}]}]}
        self.assertEqual(classify("trivy", clean, 0), "SUCCESS")
        self.assertEqual(classify("trivy", finding, 0), "FINDINGS")
        self.assertEqual(classify("trivy", clean, 1), "ERROR")
        self.assertEqual(classify("trivy", {}, 0), "ERROR")
        self.assertEqual(classify("trivy", {"SchemaVersion": 2, "Results": []}, 0), "ERROR")

    def test_history_exceptions_are_exact_and_do_not_apply_to_source(self):
        findings = []
        for commit, line in (
            ("a396cee7fd2e116cb57a8e5287c425cd83f3adee", 142),
            ("efe9d944c8df0c4d0952c54e05ec3f087bc85c2a", 108),
        ):
            path = "backend/tests/unit/test_observability.py"
            finding = {
                "RuleID": "generic-api-key", "File": path, "Commit": commit,
                "StartLine": line, "EndLine": line,
                "Fingerprint": f"{commit}:{path}:generic-api-key:{line}",
            }
            findings.append(finding)
            self.assertEqual(classify("gitleaks-history", [finding], 1), "SUCCESS_WITH_EXCEPTIONS")
            self.assertEqual(classify("gitleaks", [finding], 1), "FINDINGS")
            for key, value in (
                ("Fingerprint", "unrelated"), ("Commit", "0" * 40), ("File", "other.py"),
                ("RuleID", "other-rule"), ("StartLine", line + 1), ("EndLine", line + 1),
            ):
                with self.subTest(commit=commit, key=key):
                    self.assertEqual(classify("gitleaks-history", [dict(finding, **{key: value})], 1), "FINDINGS")
        self.assertEqual(classify("gitleaks-history", findings, 1), "SUCCESS_WITH_EXCEPTIONS")
        self.assertEqual(classify("gitleaks-history", findings + [{"RuleID": "new-secret"}], 1), "FINDINGS")
        self.assertEqual(classify("gitleaks-history", findings, 0), "ERROR")
        self.assertEqual(classify("gitleaks-history", findings, 2), "ERROR")
        self.assertEqual(classify("gitleaks-history", [], 1), "ERROR")
        self.assertEqual(classify("gitleaks-history", [], 0), "SUCCESS")

    def test_pip_audit(self):
        clean = {"dependencies": [{"name": "fixture", "vulns": []}]}
        finding = {"dependencies": [{"name": "fixture", "vulns": [{"id": "fixture"}]}]}
        self.assertEqual(classify("pip-audit", clean, 0), "SUCCESS")
        self.assertEqual(classify("pip-audit", finding, 1), "FINDINGS")
        self.assertEqual(classify("pip-audit", clean, 1), "ERROR")
        self.assertEqual(classify("pip-audit", {"dependencies": []}, 0), "ERROR")
        self.assertEqual(classify("pip-audit", clean, 2), "ERROR")

    def test_trivy_severity(self):
        for severity, expected in (("LOW", False), ("MEDIUM", False), ("HIGH", True), ("CRITICAL", True), ("UNKNOWN", True), ("", True)):
            with self.subTest(severity=severity):
                self.assertEqual(blocks("trivy", {"Results": [{"Vulnerabilities": [{"Severity": severity}]}]}), expected)

    def test_missing_or_invalid_report_fails(self):
        with self.assertRaises(KeyError):
            blocks("trivy", {})
        with self.assertRaises(ValueError):
            blocks("other", {})


if __name__ == "__main__":
    unittest.main()
