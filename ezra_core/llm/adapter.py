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
        self, model: str = "gemini/gemini-embedding-001", *, api_key: Optional[str] = None
    ) -> None:
        self._model = model
        self._api_key = api_key

    def encode(self, text: str) -> list[float]:
        import litellm

        response = litellm.embedding(model=self._model, input=[text], api_key=self._api_key)
        return list(response["data"][0]["embedding"])


class GeminiNliClassifier:
    """NLI second-pass via a Gemini call instead of the local DeBERTa CrossEncoder.

    Same ``NliClassifier`` protocol (``classify(premise=, hypothesis=) ->
    NliResult``) — it just asks the model to label the entailment relationship and
    return its confidence as JSON. Lets the two-pass checker run in the lean image
    (no torch). The local ``LocalNliClassifier`` stays the default on GKE where the
    ``ml`` deps are present; this is the API-backed alternative.
    """

    def __init__(self, model: str = "gemini/gemini-3.1-flash-lite", *, api_key: Optional[str] = None):
        self._model = model
        self._api_key = api_key

    def classify(self, *, premise: str, hypothesis: str):
        import json

        import litellm

        from ezra_core.belief.checker import NliResult

        prompt = (
            "You are a natural-language-inference classifier. Given a premise and a "
            "hypothesis, decide whether the hypothesis is an entailment, neutral, or "
            "contradiction with respect to the premise. Respond ONLY with compact JSON: "
            '{"label": "entailment|neutral|contradiction", "confidence": 0.0-1.0}.\n\n'
            f"Premise: {premise}\nHypothesis: {hypothesis}"
        )
        response = litellm.completion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
            temperature=0.0,
        )
        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
        try:
            parsed = json.loads(text)
            label = str(parsed["label"]).lower()
            confidence = float(parsed["confidence"])
        except (json.JSONDecodeError, KeyError, ValueError):
            # Unparseable → treat as non-contradiction (the safe, no-reconcile path).
            return NliResult(label="neutral", confidence=0.0)
        if label not in ("entailment", "neutral", "contradiction"):
            label = "neutral"
        return NliResult(label=label, confidence=confidence)


def llm_from_settings(settings: EzraSettings) -> LLMAdapter:
    return LLMAdapter(settings.llm_model, api_key=settings.llm_api_key or None)
