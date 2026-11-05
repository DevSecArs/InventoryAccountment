"""Тесты обязательного одобрения DevSecArs."""

import unittest

from review_policy import approved


def review(login, state="APPROVED", sha="new", number=1):
    return {
        "id": number,
        "user": {"login": login},
        "state": state,
        "commit_id": sha,
    }


class ReviewPolicyTests(unittest.TestCase):
    def test_owner_approved(self):
        self.assertTrue(approved([review("DevSecArs")], "lyna917", "new"))

    def test_other_owner_only(self):
        self.assertFalse(approved([review("lyna917")], "contributor", "new"))

    def test_no_reviews(self):
        self.assertFalse(approved([], "contributor", "new"))

    def test_dismissed(self):
        self.assertFalse(approved(
            [review("DevSecArs", "DISMISSED")], "contributor", "new"
        ))

    def test_old_commit(self):
        self.assertFalse(approved(
            [review("DevSecArs", sha="old")], "contributor", "new"
        ))

    def test_changes_requested(self):
        self.assertFalse(approved(
            [review("DevSecArs", "CHANGES_REQUESTED")],
            "contributor", "new"
        ))

    def test_self_approval(self):
        self.assertFalse(approved([review("DevSecArs")], "DevSecArs", "new"))

    def test_latest_review_wins(self):
        reviews = [
            review("DevSecArs", number=1),
            review("DevSecArs", "CHANGES_REQUESTED", number=2),
        ]
        self.assertFalse(approved(reviews, "contributor", "new"))

    def test_comment_does_not_cancel_approval(self):
        reviews = [
            review("DevSecArs", number=1),
            review("DevSecArs", "COMMENTED", number=2),
        ]
        self.assertTrue(approved(reviews, "contributor", "new"))

    def test_reapproval(self):
        reviews = [
            review("DevSecArs", "CHANGES_REQUESTED", number=1),
            review("DevSecArs", number=2),
        ]
        self.assertTrue(approved(reviews, "contributor", "new"))


if __name__ == "__main__":
    unittest.main()
