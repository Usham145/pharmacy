import pytest

from app.schemas import PharmacyRegistration, UserCreate
from app.services.auth import create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_round_trip() -> None:
    password = "safe-password-123"
    stored = hash_password(password)

    assert stored != password
    assert verify_password(stored, password)
    assert not verify_password(stored, "wrong-password")


def test_access_token_contains_user_identity() -> None:
    token = create_access_token("alice", "pharmacist")

    decoded = decode_access_token(token)

    assert decoded.username == "alice"
    assert decoded.role == "pharmacist"


def test_new_accounts_require_eight_character_passwords() -> None:
    with pytest.raises(ValueError):
        UserCreate(username="alice", full_name="Alice", role="pharmacist", password="short")
    with pytest.raises(ValueError):
        PharmacyRegistration(
            name="Example Pharmacy",
            admin_username="admin",
            admin_full_name="Admin",
            admin_password="short",
        )
