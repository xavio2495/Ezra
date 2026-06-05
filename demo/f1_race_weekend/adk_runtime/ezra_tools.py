"""ADK tools bound to one agent's :class:`EzraService`.

Each F1 agent gets its own toolset, closed over its scope-bound ``EzraService``
and a shared turn counter. The tools are plain async functions (ADK 2.x wraps a
bare function as a ``FunctionTool`` automatically) returning ``dict`` results with
a ``status`` key, per the ADK convention. The interesting one is
``commit_belief``: it routes through ``EzraService.commit``, so a claim that
contradicts another agent's active commitment triggers the real two-pass checker
and the reconciler — the contradiction is genuine, not staged.
"""

from __future__ import annotations

from typing import Callable, Optional

from ezra_core.adk_service.service import EzraService
from ezra_core.policy.engine import PolicyDeniedError


class TurnCounter:
    """Monotonic per-graph turn index shared across an agent's commits."""

    def __init__(self, start: int = 0) -> None:
        self._n = start

    def next(self) -> int:
        self._n += 1
        return self._n


def build_tools(
    service: EzraService, turns: TurnCounter, events: Optional[list] = None
) -> list[Callable]:
    """Return the ADK tool functions for ``service``'s agent.

    ``events``, if given, collects each detected-and-reconciled contradiction as a
    dict so the orchestrator can report what genuinely fired across the fleet.
    """

    async def recall(query: str) -> dict:
        """Recall relevant prior context (warm-tier summaries) for this agent.

        Args:
            query: What to recall, in natural language.
        """
        summaries = await service.recall(query, limit=5)
        return {"status": "success", "summaries": [s.summary for s in summaries]}

    async def belief_snapshot() -> dict:
        """List the team's currently-active beliefs visible to this agent's scope."""
        snap = await service.belief_snapshot()
        return {
            "status": "success",
            "beliefs": [
                {"agent": c.agent_id, "topic": c.topic, "claim": c.claim}
                for c in snap.commitments
            ],
        }

    async def fetch_federated(query: str, topic: str) -> dict:
        """Fetch live federated data from a connected source (policy-gated by scope).

        Args:
            query: The natural-language data request.
            topic: The topic tag this request falls under (e.g. 'tyres', 'weather').
        """
        try:
            result = await service.query(query, topics=[topic])
        except PolicyDeniedError as exc:
            return {
                "status": "denied",
                "reason": f"scope {service.permission_scope} does not include '{exc.topic}'",
            }
        except RuntimeError as exc:
            return {"status": "error", "reason": str(exc)}
        rows = len(result.data) if isinstance(result.data, list) else (0 if result.data is None else 1)
        if events is not None:
            events.append({
                "kind": "fetch",
                "agent": service.agent_id,
                "source": result.provenance.source,
                "time_travel_available": result.provenance.time_travel_available,
                "rows": rows,
            })
        return {
            "status": "success",
            "source": result.provenance.source,
            "time_travel_available": result.provenance.time_travel_available,
            "rows": rows,
            "data": result.data[:5] if isinstance(result.data, list) else result.data,
        }

    async def commit_belief(claim: str, topic: str) -> dict:
        """Commit a decision/fact as a team belief. Ezra checks it against existing
        beliefs and reconciles any contradiction automatically.

        Args:
            claim: The decision or fact to commit, as one concise sentence.
            topic: The topic tag for this claim (must be within your remit).
        """
        try:
            outcome = await service.commit(claim, topic, turn_index=turns.next())
        except PolicyDeniedError as exc:
            return {
                "status": "denied",
                "reason": f"'{exc.topic}' is outside your remit {service.permission_scope}",
            }
        result = {"status": "success", "committed": claim, "topic": topic}
        if outcome.contradiction is not None and outcome.resolution is not None:
            detail = {
                "kind": "contradiction",
                "topic": topic,
                "new_agent": service.agent_id,
                "new_claim": claim,
                "with_agent": outcome.contradiction.existing_agent_id,
                "decision": outcome.resolution.decision,
                "strategy": outcome.resolution.merge_strategy_used,
            }
            result["contradiction"] = detail
            if events is not None:
                events.append(detail)
        return result

    return [recall, belief_snapshot, fetch_federated, commit_belief]
