"""Typed application settings (master prompt 13.3)."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _split_roots(value: object) -> object:
    """Allow LIBRARY_IMPORT_ROOTS=/a,/b (comma-separated) besides JSON arrays."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class AppEnv(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    TEST_VPS = "test-vps"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LIBRARY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: AppEnv = AppEnv.DEVELOPMENT
    host: str = "127.0.0.1"
    port: int = 8001
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+asyncpg://library:library@127.0.0.1:55440/library",
    )
    db_echo: bool = False
    storage_root: str = "./storage"

    # --- Import (master prompt 6) ---
    import_roots: Annotated[list[str], NoDecode] = Field(default_factory=list)
    max_file_mb: int = 50
    max_files_per_batch: int = 20

    @field_validator("import_roots", mode="before")
    @classmethod
    def _parse_import_roots(cls, value: object) -> object:
        return _split_roots(value)

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    # --- Auth (macroportal-level, see ADR-0006) ---
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    device_token_ttl_days: int = 365
    cookie_secure: bool = True
    login_rate_limit: int = 5
    register_rate_limit: int = 3
    rate_limit_window_seconds: int = 60

    @model_validator(mode="after")
    def _require_jwt_secret(self) -> Settings:
        if self.jwt_secret is None:
            msg = (
                "LIBRARY_JWT_SECRET is required. "
                'Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
            raise ValueError(msg)
        return self

    @property
    def is_dev(self) -> bool:
        return self.app_env is AppEnv.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.app_env is AppEnv.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    return Settings()
