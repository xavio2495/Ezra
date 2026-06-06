"""Runtime configuration, loaded from EZRA_* environment variables / .env.

Only the settings used by the platform are declared. Unknown EZRA_* vars (the
full reference set lives in .env.example) are ignored, not errors.
"""

from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EzraSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EZRA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM. Gemini 2.0 Flash/Flash-Lite were shut down 2026-06-01; the project now
    # targets the 3.5-flash line (verified live). Override via EZRA_LLM_MODEL etc.
    llm_model: str = "gemini/gemini-3.5-flash"
    llm_api_key: str = ""
    meta_agent_model: str = "gemini/gemini-3.5-flash"
    embedding_model: str = "gemini/gemini-embedding-001"

    # Storage
    mongodb_uri: str = ""
    mongodb_db: str = "ezra"
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"

    # Atlas Admin API — used to auto-allow the runtime's egress IP so the workload
    # connects from anywhere (GCP/dynamic IPs) without a manual Network Access step.
    mongodb_public_key: str = ""
    mongodb_private_key: str = ""
    mongodb_atlas_project_id: str = ""  # Atlas project (group) id; auto-discovered if blank
    atlas_auto_allow_egress: bool = True

    # Mesh connectors (federated sources). Blank = connector not configured.
    mongodb_mcp_url: str = "http://localhost:3001"
    snowflake_account: str = ""
    snowflake_user: str = ""
    snowflake_password: str = ""
    snowflake_role: str = ""
    snowflake_warehouse: str = ""
    snowflake_database: str = ""
    snowflake_schema: str = ""
    bigquery_project: str = ""
    bigquery_dataset: str = ""

    # Memory behaviour
    context_limit: int = 128000
    hot_max_turns: int = 8
    salience_decay_rate: float = 0.1
    warm_ttl_hours: int = 24

    # Contradiction detection (two-pass) + reconciler
    nli_model: str = "cross-encoder/nli-deberta-v3-base"
    nli_device: str = "auto"
    embedding_similarity_threshold: float = 0.85
    # Gemini embeddings cluster paraphrases lower than MiniLM, so the Gemini-backed
    # checker (no-torch path) needs a lower first-pass cutoff than the local one.
    gemini_checker_similarity_threshold: float = 0.65
    nli_confidence_threshold: float = 0.7
    default_merge_strategy: str = "last_write_wins"
    manual_resolution_timeout_seconds: int = 30

    # Policy
    policy_engine_enabled: bool = True

    # Meta-agents (both enabled by default)
    meta_agent_learning_enabled: bool = True
    meta_agent_lifecycle_enabled: bool = True
    core_promotion_access_count: int = 3
    lifecycle_schedule_active_minutes: int = 5
    lifecycle_schedule_closed_minutes: int = 60

    # Lifecycle
    default_archival_threshold_days: int = 90
    default_belief_retention_days: Optional[int] = None

    # Observability
    phoenix_endpoint: str = "http://localhost:6006/v1/traces"
    tracing_enabled: bool = True

    # REST API
    api_enabled: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    api_bearer_token: str = ""

    @field_validator("default_belief_retention_days", mode="before")
    @classmethod
    def _blank_is_infinite(cls, v):
        # `.env` sets EZRA_DEFAULT_BELIEF_RETENTION_DAYS= (blank) to mean infinite.
        if isinstance(v, str) and v.strip() == "":
            return None
        return v
