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

    # --- AI via OmniRoute (master prompt 8.6; key must not be committed) ---
    ai_base_url: str = "https://llm.gorbunovr.ru/v1"
    ai_api_key: str | None = None
    ai_model: str = "ali/qwen-turbo"
    ai_timeout_seconds: float = 30.0
    ai_enabled: bool = True  # local-only policy switch (§8.6)
    ai_max_input_chars: int = 4000  # hard cap on digest size sent to the model
    epubcheck_jar: str = ""  # path to epubcheck.jar; empty = validation skipped
    audit_retention_days: int = 0  # 0 = keep forever; else delete older records
    outbox_retention_days: int = 30  # processed outbox events cleanup

    # --- Import (master prompt 6) ---
    import_roots: Annotated[list[str], NoDecode] = Field(default_factory=list)
    max_file_mb: int = 50
    max_files_per_batch: int = 20
    watched_inbox_enabled: bool = False
    watched_inbox_owner_email: str | None = None
    watched_inbox_interval_seconds: int = Field(default=60, ge=10)
    watched_inbox_min_age_seconds: int = Field(default=30, ge=0)

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
        if self.watched_inbox_enabled:
            if not self.import_roots:
                raise ValueError(
                    "LIBRARY_IMPORT_ROOTS is required when watched inbox is enabled",
                )
            if not self.watched_inbox_owner_email:
                raise ValueError(
                    "LIBRARY_WATCHED_INBOX_OWNER_EMAIL is required when watched inbox is enabled",
                )
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
