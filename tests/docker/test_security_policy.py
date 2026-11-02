"""Проверки блокировки severity в отчётах."""

import unittest

from scripts.security_policy import blocks


class SecurityPolicyTests(unittest.TestCase):
    def test_pnpm_severity(self):
        for severity, expected in (("low", False), ("moderate", False), ("high", True), ("critical", True), ("", True)):
            with self.subTest(severity=severity):
                self.assertEqual(blocks("pnpm", {"advisories": {"1": {"severity": severity}}}), expected)

    def test_trivy_severity(self):
        for severity, expected in (("LOW", False), ("MEDIUM", False), ("HIGH", True), ("CRITICAL", True), ("UNKNOWN", True), ("", True)):
            with self.subTest(severity=severity):
                self.assertEqual(blocks("trivy", {"Results": [{"Vulnerabilities": [{"Severity": severity}]}]}), expected)

    def test_missing_or_invalid_report_fails(self):
        with self.assertRaises(KeyError):
            blocks("pnpm", {})
        with self.assertRaises(KeyError):
            blocks("trivy", {})
        with self.assertRaises(ValueError):
            blocks("other", {})


if __name__ == "__main__":
    unittest.main()
