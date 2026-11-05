"""Проверки политики выявления критических изменений."""

import unittest
from unittest.mock import patch

import acceptance_policy as policy


class AcceptancePolicyTests(unittest.TestCase):
    def test_critical_files(self):
        paths = (
            ".github/workflows/ci.yml",
            ".github/CODEOWNERS",
            "Makefile",
            "backend/tests/unit/test_example.py",
            "frontend/src/app/App.test.tsx",
            "frontend/vite.config.ts",
            "tests/docker/semgrep-rules.yml",
            "scripts/container_check.py",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertTrue(policy.critical(path))

    def test_regular_file(self):
        self.assertFalse(policy.critical("backend/app/entities/item.py"))

    def test_deleted_test(self):
        with patch.object(
            policy, "git", return_value=b"D\0backend/tests/unit/test_item.py\0"
        ):
            result = policy.inspect("base", "head")
        self.assertTrue(any("Удалён" in item for item in result))

    def test_renamed_test(self):
        changes = b"R100\0backend/tests/unit/test_old.py\0backend/tests/unit/test_new.py\0"
        with patch.object(policy, "git", return_value=changes):
            with patch.object(policy.subprocess, "run") as run:
                run.return_value.stdout = ""
                result = policy.inspect("base", "head")
        self.assertTrue(any("переименован" in item for item in result))

    def test_skip_detection(self):
        changes = b"M\0frontend/src/app/App.test.tsx\0"
        with patch.object(policy, "git", return_value=changes):
            with patch.object(policy.subprocess, "run") as run:
                run.return_value.stdout = "+test.skip('important', () => {})"
                result = policy.inspect("base", "head")
        self.assertTrue(any("Пропуск теста" in item for item in result))

    def test_coverage_change(self):
        changes = b"M\0backend/pyproject.toml\0"
        with patch.object(policy, "git", return_value=changes):
            with patch.object(policy.subprocess, "run") as run:
                run.return_value.stdout = "+fail_under = 60"
                result = policy.inspect("base", "head")
        self.assertTrue(any("Покрытие" in item for item in result))

    def test_pipeline_change(self):
        changes = b"M\0.github/workflows/ci.yml\0"
        with patch.object(policy, "git", return_value=changes):
            with patch.object(policy.subprocess, "run") as run:
                run.return_value.stdout = "+continue-on-error: true"
                issues = policy.inspect("base", "head")
        self.assertTrue(any("Отключение анализатора" in issue for issue in issues))

    def test_semgrep_ignore_change(self):
        changes = b"M\0tests/docker/semgrep-rules.yml\0"
        with patch.object(policy, "git", return_value=changes):
            with patch.object(policy.subprocess, "run") as run:
                run.return_value.stdout = "+# nosemgrep"
                issues = policy.inspect("base", "head")
        self.assertTrue(any("критический файл" in issue for issue in issues))

    def test_regular_source_change_not_critical(self):
        changes = b"M\0backend/app/entities/item.py\0"
        with patch.object(policy, "git", return_value=changes):
            self.assertEqual(policy.inspect("base", "head"), [])

    def test_removed_quality_check(self):
        changes = b"M\0.github/workflows/ci.yml\0"
        with patch.object(policy, "git", return_value=changes):
            with patch.object(policy.subprocess, "run") as run:
                run.return_value.stdout = "-run: make quality"
                issues = policy.inspect("base", "head")
        self.assertTrue(any(
            "Удалено" in issue and "Изменение проверки" in issue
            for issue in issues
        ))

    def test_frontend_protection_boundaries(self):
        critical_paths = [
            "frontend/src/app/App.test.tsx",
            "frontend/src/app/App.spec.tsx",
            "frontend/src/test/setup.ts",
            "frontend/vite.config.ts",
            "frontend/tsconfig.app.json",
            "frontend/pnpm-lock.yaml",
        ]
        regular_paths = [
            "frontend/src/app/App.tsx",
            "frontend/src/features/auth/LoginPage.tsx",
        ]
        for name in critical_paths:
            with self.subTest(path=name):
                self.assertTrue(policy.critical(name))
        for name in regular_paths:
            with self.subTest(path=name):
                self.assertFalse(policy.critical(name))

    def test_no_changes(self):
        with patch.object(policy, "git", return_value=b""):
            self.assertEqual(policy.inspect("base", "head"), [])


if __name__ == "__main__":
    unittest.main()
