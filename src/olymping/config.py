from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: SecretStr | None = None
    owner_telegram_id: int = 0
    timezone: str = "Europe/Moscow"
    database_url: str = "sqlite+aiosqlite:///./data/olymping.db"
    data_dir: Path = Path("data/calendar")
    ctftime_base_url: str = "https://ctftime.org/api/v1"
    ctftime_sync_interval_hours: int = Field(default=6, ge=1, le=168)
    ctftime_lookahead_days: int = Field(default=180, ge=7, le=730)
    reminder_poll_seconds: int = Field(default=60, ge=10, le=3600)
    reminder_grace_hours: int = Field(default=24, ge=1, le=168)
    log_level: str = "INFO"

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("owner_telegram_id")
    @classmethod
    def valid_owner(cls, value: int) -> int:
        if value < 0:
            raise ValueError("OWNER_TELEGRAM_ID must be a positive Telegram ID")
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
