from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken


class SecretConfigurationError(ValueError):
    """Raised when a server-side encryption secret is unusable."""


_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("password must not be empty")
    return _password_hasher.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return _password_hasher.verify(encoded_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


class SecretCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (TypeError, ValueError) as exc:
            raise SecretConfigurationError(
                "SMTP_ENCRYPTION_KEY must be a URL-safe 32-byte Fernet key"
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise ValueError("plaintext must not be empty")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError, ValueError) as exc:
            raise SecretConfigurationError("encrypted secret cannot be decrypted") from exc
