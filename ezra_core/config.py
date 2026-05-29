"""Runtime configuration, loaded from EZRA_* environment variables / .env.

Only the settings used by code that exists today are declared. Unknown EZRA_*
vars (documented in .env.example for later sessions) are ignored, not errors.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class EzraSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EZRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Storage
    mongodb_uri: str = ""
    mongodb_db: str = "ezra"
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"

    # Memory behaviour
    context_limit: int = 128000
    hot_max_turns: int = 8
    salience_decay_rate: float = 0.1
