import pytest
from cryptography.fernet import Fernet

from app.core.security import (
    SecretCipher,
    SecretConfigurationError,
    hash_password,
    verify_password,
)


def test_password_hash_is_argon2_and_verifiable() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("$argon2")
    assert "correct horse battery staple" not in encoded
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)
    assert not verify_password("anything", "not-an-argon2-hash")


def test_secret_cipher_round_trip_and_wrong_key() -> None:
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    encrypted = cipher.encrypt("smtp-password-密钥")

    assert "smtp-password" not in encrypted
    assert cipher.decrypt(encrypted) == "smtp-password-密钥"

    wrong_cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    with pytest.raises(SecretConfigurationError):
        wrong_cipher.decrypt(encrypted)


def test_secret_cipher_rejects_invalid_key() -> None:
    with pytest.raises(SecretConfigurationError):
        SecretCipher("not-a-fernet-key")
