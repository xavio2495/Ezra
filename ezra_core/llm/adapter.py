"""litellm wrapper — provider-agnostic chat completion (with retry) + embeddings.

Default models target Gemini (AI Studio key in ``EZRA_LLM_API_KEY``), but any
litellm-supported model string works. ``litellm`` is imported lazily inside the
methods so importing this module stays cheap and unit tests can monkeypatch it.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ezra_core.config import EzraSettings


class LLMError(RuntimeError):
    """Raised when an LLM call fails after exhausting retries."""


class LLMAdapter:
    def __init__(
        self,
        model: str,
        *,
        api_key: Optional[str] = None,
        max_retries: int = 2,
        temperature: float = 0.7,
        base_backoff: float = 0.5,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._max_retries = max_retries
        self._temperature = temperature
        self._base_backoff = base_backoff

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> str:
        import litellm

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await litellm.acompletion(
                    model=model or self._model,
                    messages=messages,
                    api_key=self._api_key,
                    temperature=self._temperature if temperature is None else temperature,
                    **kwargs,
                )
                return response.choices[0].message.content
            except Exception as exc:  # noqa: BLE001 — retry any provider error
                last_exc = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(self._base_backoff * (2**attempt))
        raise LLMError(
            f"LLM call failed after {self._max_retries + 1} attempts: {last_exc}"
        ) from last_exc


class GeminiEmbedder:
    """Sync embedder (matches the warm tier / checker ``Embedder`` Protocol).

    Calls litellm's synchronous ``embedding`` so it can be used from the warm
    tier's sync ``encode``. Note: this blocks during the HTTP call — fine for
    the demo's scale; revisit with a batched/async path if it becomes hot.
    """

    def __init__(
        self, model: str = "gemini/text-embedding-004", *, api_key: Optional[str] = None
    ) -> None:
        self._model = model
        self._api_key = api_key

    def encode(self, text: str) -> list[float]:
        import litellm

        response = litellm.embedding(model=self._model, input=[text], api_key=self._api_key)
        return list(response["data"][0]["embedding"])


def llm_from_settings(settings: EzraSettings) -> LLMAdapter:
    return LLMAdapter(settings.llm_model, api_key=settings.llm_api_key or None)
