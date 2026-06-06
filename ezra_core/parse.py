"""Router step 1 — Parse. Classify the agent's input into a ``ParsedIntent`` that
drives step 5 (fetch decision): does this turn need live external data, on which
topics, how urgent.

Two implementations: ``HeuristicIntentParser`` (keyword/rule-based, no LLM call —
cheap and the safe default, honouring the spec's "small classifier" framing) and
``LLMIntentParser`` (a structured-JSON Gemini call — the user's "bring the LLM for
critical data fetch" path, more accurate on ambiguous input). Both are injected so
the router and tests stay decoupled from the choice.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Protocol, Sequence

from pydantic import BaseModel, Field


class ParsedIntent(BaseModel):
    needs_fetch: bool = False
    topics: list[str] = Field(default_factory=list)
    urgency: float = Field(default=0.0, ge=0, le=1)
    entities: list[str] = Field(default_factory=list)


class IntentParser(Protocol):
    def parse(self, user_input: str, *, scope: Sequence[str] = ()) -> ParsedIntent: ...


# Words that signal the agent is reaching for current/external state rather than
# recalling memory. Tuned for the demo domains; extend per deployment.
_FETCH_CUES = re.compile(
    r"\b(latest|current|now|live|today|recent|historical|history|look\s*up|fetch|"
    r"query|data|results?|standings?|telemetry|inventory|stock|price|forecast|"
    r"weather|record|stats?|how many|what (?:is|are|was|were)|show me)\b",
    re.IGNORECASE,
)
_URGENT = re.compile(r"\b(now|immediately|urgent|asap|critical|emergency|lap \d+)\b", re.IGNORECASE)


class HeuristicIntentParser:
    """No-LLM parser: flags a fetch when the input contains data-seeking cues and
    selects in-scope topics by keyword. ~0ms; the default."""

    def parse(self, user_input: str, *, scope: Sequence[str] = ()) -> ParsedIntent:
        text = user_input.lower()
        needs_fetch = bool(_FETCH_CUES.search(user_input))
        topics = [t for t in scope if t.lower() in text]
        # If a fetch is indicated but no scope topic matched, fall back to the whole
        # scope so policy (not the parser) decides what's allowed.
        if needs_fetch and not topics:
            topics = list(scope)
        urgency = 1.0 if _URGENT.search(user_input) else (0.5 if needs_fetch else 0.0)
        return ParsedIntent(needs_fetch=needs_fetch, topics=topics, urgency=urgency)


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


class LLMIntentParser:
    """Structured-JSON Gemini parser for the fetch decision. Falls back to the
    heuristic parser on any model/parse failure, so the router never breaks."""

    def __init__(self, model: str = "gemini/gemini-3.5-flash", *, api_key: Optional[str] = None):
        self._model = model
        self._api_key = api_key
        self._fallback = HeuristicIntentParser()

    def parse(self, user_input: str, *, scope: Sequence[str] = ()) -> ParsedIntent:
        import litellm

        prompt = (
            "Decide whether answering this needs LIVE external/federated data "
            "(vs. only memory/reasoning), and classify it. Respond ONLY with compact "
            'JSON: {"needs_fetch": bool, "topics": [<subset of the allowed topics>], '
            '"urgency": 0.0-1.0, "entities": [str]}.\n\n'
            f"Allowed topics: {list(scope)}\nInput: {user_input}"
        )
        try:
            resp = litellm.completion(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self._api_key,
                temperature=0.0,
            )
            data = _parse_json_object(resp.choices[0].message.content)
            if not data:
                return self._fallback.parse(user_input, scope=scope)
            scope_set = {s.lower() for s in scope}
            topics = [t for t in data.get("topics", []) if str(t).lower() in scope_set]
            return ParsedIntent(
                needs_fetch=bool(data.get("needs_fetch", False)),
                topics=topics,
                urgency=max(0.0, min(1.0, float(data.get("urgency", 0.0) or 0.0))),
                entities=[str(e) for e in data.get("entities", [])],
            )
        except Exception:  # noqa: BLE001 — never let parsing break the turn
            return self._fallback.parse(user_input, scope=scope)


def parser_from_settings(settings) -> LLMIntentParser:
    """Production parser via the meta model (cheap). Vertex models use ADC."""
    from ezra_core.llm.adapter import is_vertex_model

    key = None if is_vertex_model(settings.meta_agent_model) else (settings.llm_api_key or None)
    return LLMIntentParser(settings.meta_agent_model, api_key=key)
