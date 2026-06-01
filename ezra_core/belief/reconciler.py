"""Reconciler — resolves a detected contradiction via one of four strategies.

Detection (``checker.py``) is separate: it produces a ``Contradiction``; this
module decides what to do about it. Strategies:

  - last_write_wins : newest commitment supersedes (accept_new).
  - highest_trust   : per-topic trust breaks the tie.
  - manual          : emit a callback; block up to a timeout, then fall back to
                      last_write_wins (accept_new).
  - custom          : application-defined resolver(contradiction, ResolveContext).
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, Sequence

from ezra_core.schemas.belief import (
    Commitment,
    Contradiction,
    ContradictionEvent,
    Resolution,
)
from ezra_core.schemas.session_graph import MergeStrategy

CustomResolver = Callable[[Contradiction, "ResolveContext"], Awaitable[Resolution]]
ContradictionCallback = Callable[[ContradictionEvent], Awaitable[str]]


class ResolveContext:
    """Context handed to a custom resolver. Extra app fields (e.g.
    ``regulatory_mode``) can be attached via ``metadata`` or as attributes."""

    def __init__(
        self,
        *,
        topic: str,
        existing_agent_id: str,
        new_agent_id: str,
        existing_trust: float,
        new_trust: float,
        active_commitments: Sequence[Commitment] = (),
        **metadata,
    ) -> None:
        self.topic = topic
        self.existing_agent_id = existing_agent_id
        self.new_agent_id = new_agent_id
        self.existing_trust = existing_trust
        self.new_trust = new_trust
        self._active = list(active_commitments)
        self.metadata = metadata
        for key, value in metadata.items():
            setattr(self, key, value)

    def contemporaneous_contradictions_on_topic(self, topic: str) -> int:
        return sum(1 for c in self._active if c.topic == topic)


async def reconcile(
    contradiction: Contradiction,
    *,
    merge_strategy: MergeStrategy,
    existing_trust: float,
    new_trust: float,
    manual_resolution_timeout_seconds: int = 30,
    custom_resolver: Optional[CustomResolver] = None,
    on_contradiction: Optional[ContradictionCallback] = None,
    resolve_context: Optional[ResolveContext] = None,
) -> Resolution:
    if merge_strategy == "last_write_wins":
        return Resolution(decision="accept_new", merge_strategy_used="last_write_wins")

    if merge_strategy == "highest_trust":
        decision = "accept_new" if new_trust > existing_trust else "keep_existing"
        return Resolution(decision=decision, merge_strategy_used="highest_trust")

    if merge_strategy == "manual":
        if on_contradiction is None:
            # No callback registered → immediate last_write_wins, with a warning trace.
            return Resolution(
                decision="accept_new",
                merge_strategy_used="manual_no_callback_fallback",
            )
        event = ContradictionEvent(
            contradiction=contradiction,
            existing_claim="",
            existing_trust=existing_trust,
            new_trust=new_trust,
            graph_state_snapshot_id="",
        )
        try:
            result = await asyncio.wait_for(
                on_contradiction(event),
                timeout=manual_resolution_timeout_seconds,
            )
            return Resolution(decision=result, merge_strategy_used="manual")
        except asyncio.TimeoutError:
            return Resolution(
                decision="accept_new", merge_strategy_used="manual_timeout_fallback"
            )

    if merge_strategy == "custom":
        if custom_resolver is None:
            raise ValueError("merge_strategy='custom' requires a custom_resolver")
        ctx = resolve_context or ResolveContext(
            topic=contradiction.topic,
            existing_agent_id=contradiction.existing_agent_id,
            new_agent_id=contradiction.new_agent_id,
            existing_trust=existing_trust,
            new_trust=new_trust,
        )
        resolution = await custom_resolver(contradiction, ctx)
        # A custom resolver may delegate to a built-in strategy.
        if resolution.decision == "fallback" and resolution.fallback_strategy is not None:
            return await reconcile(
                contradiction,
                merge_strategy=resolution.fallback_strategy,
                existing_trust=existing_trust,
                new_trust=new_trust,
                manual_resolution_timeout_seconds=manual_resolution_timeout_seconds,
                on_contradiction=on_contradiction,
            )
        return resolution

    raise ValueError(f"unknown merge strategy: {merge_strategy}")
