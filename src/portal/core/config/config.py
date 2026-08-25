"""Typed application settings (master prompt 13.3)."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def is_dev(self) -> bool:
        return self.app_env is AppEnv.DEVELOPMENT


@lru_cache
def get_settings() -> Settings:
    return Settings()
