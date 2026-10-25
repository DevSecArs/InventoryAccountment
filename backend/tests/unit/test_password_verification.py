"""Проверки критических условий проверки пароля."""

import pytest

from app.entities.auth import _hash_password, _verify_password


@pytest.fixture()
def password_hash() -> str:
    return _hash_password("correct-password", salt=b"\x00" * 16)


def test_password_verification_accepts_only_matching_password(password_hash: str) -> None:
    assert _verify_password("correct-password", password_hash)
    assert not _verify_password("wrong-password", password_hash)


@pytest.mark.parametrize(
    "encoded",
    [
        "unknown$600000$00000000000000000000000000000000$deadbeef",
        "pbkdf2_sha256$not-a-number$00000000000000000000000000000000$deadbeef",
        "pbkdf2_sha256$600000$not-hex$deadbeef",
    ],
)
def test_password_verification_rejects_invalid_hash_data(encoded: str) -> None:
    assert not _verify_password("correct-password", encoded)
