"""Проверка отказа при изменении HEAD."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_pr_review


class GitHubReviewAPITests(unittest.TestCase):
    def test_stale_event_fails(self):
        event = {
            "pull_request": {
                "number": 7,
                "head": {"sha": "old"},
            }
        }
        pr = {
            "state": "open",
            "number": 7,
            "base": {"ref": "dev"},
            "head": {"sha": "new"},
            "user": {"login": "contributor"},
        }

        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "event.json"
            event_file.write_text(json.dumps(event))

            environment = {
                "GITHUB_REPOSITORY": "DevSecArs/InventoryAccountment",
                "GITHUB_EVENT_PATH": str(event_file),
            }
            with patch.dict(os.environ, environment):
                with patch.object(check_pr_review, "github", side_effect=[pr, [{"filename": "Makefile"}], [], pr]):
                    self.assertEqual(check_pr_review.main(), 1)


    def test_regular_pr_without_owner_approval(self):
        event = {
            "pull_request": {
                "number": 7,
                "head": {"sha": "current"},
            }
        }
        pr = {
            "state": "open",
            "number": 7,
            "base": {"ref": "dev"},
            "head": {"sha": "current"},
            "user": {"login": "contributor"},
        }

        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "event.json"
            event_file.write_text(json.dumps(event))

            environment = {
                "GITHUB_REPOSITORY": "DevSecArs/InventoryAccountment",
                "GITHUB_EVENT_PATH": str(event_file),
            }
            with patch.dict(os.environ, environment):
                with patch.object(
                    check_pr_review, "github",
                    side_effect=[
                        pr,
                        [{"filename": "backend/app/entities/item.py"}],
                        [],
                        pr,
                    ],
                ):
                    self.assertEqual(check_pr_review.main(), 0)

    def test_renamed_critical_file_requires_approval(self):
        event = {
            "pull_request": {
                "number": 7,
                "head": {"sha": "current"},
            }
        }
        pr = {
            "state": "open",
            "number": 7,
            "base": {"ref": "dev"},
            "head": {"sha": "current"},
            "user": {"login": "contributor"},
        }
        files = [{
            "filename": "backend/app/old_test_backup.py",
            "previous_filename": "backend/tests/unit/test_item.py",
            "status": "renamed",
        }]

        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "event.json"
            event_file.write_text(json.dumps(event))

            environment = {
                "GITHUB_REPOSITORY": "DevSecArs/InventoryAccountment",
                "GITHUB_EVENT_PATH": str(event_file),
            }
            with patch.dict(os.environ, environment):
                with patch.object(
                    check_pr_review, "github",
                    side_effect=[pr, files, [], pr],
                ):
                    self.assertEqual(check_pr_review.main(), 1)

    def test_unsupported_base_branch(self):
        event = {
            "pull_request": {
                "number": 7,
                "head": {"sha": "current"},
            }
        }
        pr = {
            "state": "open",
            "number": 7,
            "base": {"ref": "feature/other"},
            "head": {"sha": "current"},
            "user": {"login": "contributor"},
        }
        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "event.json"
            event_file.write_text(json.dumps(event))
            environment = {
                "GITHUB_REPOSITORY": "DevSecArs/InventoryAccountment",
                "GITHUB_EVENT_PATH": str(event_file),
            }
            with patch.dict(os.environ, environment):
                with patch.object(check_pr_review, "github", return_value=pr):
                    self.assertEqual(check_pr_review.main(), 1)

    def test_valid_owner_approval(self):
        self.check_review("DevSecArs", 0)

    def test_other_owner_cannot_approve(self):
        self.check_review("lyna917", 1)

    def check_review(self, reviewer, expected):
        event = {
            "pull_request": {
                "number": 7,
                "head": {"sha": "current"},
            }
        }
        pr = {
            "state": "open",
            "number": 7,
            "base": {"ref": "dev"},
            "head": {"sha": "current"},
            "user": {"login": "contributor"},
        }
        reviews = [{
            "id": 1,
            "user": {"login": reviewer},
            "state": "APPROVED",
            "commit_id": "current",
        }]

        with tempfile.TemporaryDirectory() as directory:
            event_file = Path(directory) / "event.json"
            event_file.write_text(json.dumps(event))

            environment = {
                "GITHUB_REPOSITORY": "DevSecArs/InventoryAccountment",
                "GITHUB_EVENT_PATH": str(event_file),
            }
            with patch.dict(os.environ, environment):
                with patch.object(
                    check_pr_review, "github",
                    side_effect=[pr, [{"filename": "Makefile"}], reviews, pr],
                ):
                    self.assertEqual(check_pr_review.main(), expected)


if __name__ == "__main__":
    unittest.main()
