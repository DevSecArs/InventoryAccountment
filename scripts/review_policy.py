"""Проверка обязательного одобрения владельца проекта."""

OWNER = "devsecars"


def approved(reviews, author, head_sha):
    """Проверять последнее существенное решение DevSecArs."""
    if author.lower() == OWNER:
        return False

    decisions = [
        review for review in reviews
        if review.get("user", {}).get("login", "").lower() == OWNER
        and review.get("state") in {
            "APPROVED", "CHANGES_REQUESTED", "DISMISSED"
        }
    ]
    if not decisions:
        return False

    latest = max(decisions, key=lambda review: review["id"])
    return (
        latest["state"] == "APPROVED"
        and latest.get("commit_id") == head_sha
    )
