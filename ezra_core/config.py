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

    # LLM
    llm_model: str = "gemini/gemini-2.0-flash"
    llm_api_key: str = ""
    meta_agent_model: str = "gemini/gemini-2.0-flash-lite"
    embedding_model: str = "gemini/text-embedding-004"

    # Storage
    mongodb_uri: str = ""
    mongodb_db: str = "ezra"
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"

    # Memory behaviour
    context_limit: int = 128000
    hot_max_turns: int = 8
    salience_decay_rate: float = 0.1
    warm_ttl_hours: int = 24

    # Contradiction detection (two-pass) + reconciler
    nli_model: str = "cross-encoder/nli-deberta-v3-base"
    nli_device: str = "auto"
    embedding_similarity_threshold: float = 0.85
    nli_confidence_threshold: float = 0.7
    default_merge_strategy: str = "last_write_wins"
    manual_resolution_timeout_seconds: int = 30

    # Policy
    policy_engine_enabled: bool = True
