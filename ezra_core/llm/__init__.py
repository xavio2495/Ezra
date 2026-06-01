"""LLM access via litellm — chat completion + embeddings."""

from ezra_core.llm.adapter import (
    GeminiEmbedder,
    LLMAdapter,
    LLMError,
    llm_from_settings,
)

__all__ = ["LLMAdapter", "LLMError", "GeminiEmbedder", "llm_from_settings"]
