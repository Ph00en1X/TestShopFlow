from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    BOT_TOKEN: str

    SHOP_NAME: str = "ShopFlow"

    USE_SQLITE: bool = False
    DATABASE_URL: str = "postgresql+asyncpg://shopflow:shopflow@localhost:5432/shopflow"
    SQLITE_PATH: str = "shopflow.db"

    REDIS_URL: str | None = "redis://localhost:6379/0"
    USE_MEMORY_FSM: bool = False

    ADMIN_IDS: list[int] = Field(default_factory=list)

    PAYMENT_CARD: str = "0000 0000 0000 0000"
    PAYMENT_HOLDER: str = "Иван Иванов"

    S3_BUCKET: str = ""
    S3_ENDPOINT: str = ""
    S3_KEY: str = ""
    S3_SECRET: str = ""

    TIMEZONE: str = "UTC"
    LOG_LEVEL: str = "INFO"

    ORDER_EXPIRY_HOURS: int = 24
    PAYMENT_REMINDER_AFTER_HOURS: int = 2
    PAYMENT_REMINDER_INTERVAL_HOURS: int = 6
    MAX_CART_ITEMS: int = 50

    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30

    BROADCAST_CHUNK_SIZE: int = 20
    BROADCAST_DELAY_MS: int = 1000

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "postgresql+asyncpg://shopflow:shopflow@localhost:5432/shopflow"
        if raw.startswith("postgres://"):
            return raw.replace("postgres://", "postgresql+asyncpg://", 1)
        if raw.startswith("postgresql://"):
            return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw.startswith("sqlite:///"):
            return raw.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return raw

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def normalize_redis_url(cls, value: str | None) -> str | None:
        raw = str(value or "").strip()
        return raw or None

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: list[int] | str | None) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(item) for item in value]
        raw = str(value).strip()
        if not raw:
            return []
        if raw.startswith("["):
            parsed = json.loads(raw)
            return [int(item) for item in parsed]
        return [int(item.strip()) for item in raw.split(",") if item.strip()]

    @field_validator("TIMEZONE")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        tz_name = str(value or "UTC").strip() or "UTC"
        ZoneInfo(tz_name)
        return tz_name

    @field_validator("LOG_LEVEL")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return str(value or "INFO").strip().upper() or "INFO"

    @field_validator(
        "ORDER_EXPIRY_HOURS",
        "PAYMENT_REMINDER_AFTER_HOURS",
        "PAYMENT_REMINDER_INTERVAL_HOURS",
        "MAX_CART_ITEMS",
        "DB_POOL_SIZE",
        "DB_MAX_OVERFLOW",
        "DB_POOL_TIMEOUT",
        "BROADCAST_CHUNK_SIZE",
        "BROADCAST_DELAY_MS",
    )
    @classmethod
    def positive_ints(cls, value: int) -> int:
        return max(1, int(value))

    @field_validator("SHOP_NAME", "PAYMENT_CARD", "PAYMENT_HOLDER", mode="before")
    @classmethod
    def normalize_strings(cls, value: str | None) -> str:
        return str(value or "").strip()

    @property
    def effective_database_url(self) -> str:
        if self.USE_SQLITE:
            db_path = Path(self.SQLITE_PATH or "shopflow.db")
            return f"sqlite+aiosqlite:///{db_path.as_posix()}"
        return self.DATABASE_URL


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()