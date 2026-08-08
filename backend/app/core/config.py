from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/deltracking.db"
    session_secret: SecretStr = SecretStr("development-only-change-me")
    smtp_encryption_key: SecretStr | None = None
    admin_username: str = "admin"
    admin_password: SecretStr | None = None
    tracking_app_id: SecretStr | None = None
    app_timezone: str = "Asia/Shanghai"

    schedule_interval_minutes: int = Field(default=30, ge=5, le=1440)

    @field_validator("admin_username", "app_timezone")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


@lru_cache
def get_settings() -> Settings:
    return Settings()
