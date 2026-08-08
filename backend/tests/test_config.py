import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_read_environment_names(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("SESSION_SECRET", "a-session-secret")
    monkeypatch.setenv("SMTP_ENCRYPTION_KEY", key)
    monkeypatch.setenv("ADMIN_USERNAME", " operator ")
    monkeypatch.setenv("ADMIN_PASSWORD", "admin-password")
    monkeypatch.setenv("TRACKING_APP_ID", "tracking-app")
    monkeypatch.setenv("APP_TIMEZONE", "Asia/Shanghai")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///:memory:"
    assert settings.admin_username == "operator"
    assert settings.session_secret.get_secret_value() == "a-session-secret"
    assert settings.smtp_encryption_key is not None
    assert key not in repr(settings)
    assert "admin-password" not in repr(settings)
    assert "tracking-app" not in repr(settings)


def test_schedule_interval_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, schedule_interval_minutes=4)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, schedule_interval_minutes=1441)
