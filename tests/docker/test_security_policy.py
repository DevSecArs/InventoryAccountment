"""Проверки блокировки severity в отчётах."""

import unittest

from scripts.security_policy import blocks, classify


class SecurityPolicyTests(unittest.TestCase):
    def test_scanner_outcomes(self):
        self.assertEqual(classify("gitleaks", [], 0), "SUCCESS")
        self.assertEqual(classify("gitleaks", [{"RuleID": "fixture"}], 1), "FINDINGS")
        self.assertEqual(classify("gitleaks", [], 1), "ERROR")
        self.assertEqual(classify("gitleaks", [], 2), "ERROR")
        clean = {"SchemaVersion": 2, "Results": [{"Target": "image"}]}
        finding = {"SchemaVersion": 2, "Results": [{"Target": "image", "Vulnerabilities": [{"Severity": "HIGH"}]}]}
        self.assertEqual(classify("trivy", clean, 0), "SUCCESS")
        self.assertEqual(classify("trivy", finding, 0), "FINDINGS")
        self.assertEqual(classify("trivy", clean, 1), "ERROR")
        self.assertEqual(classify("trivy", {}, 0), "ERROR")

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
