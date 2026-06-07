"""Ezra-bound tool functions for a Google ADK agent — the platform surface.

``ezra_adk_tools(service)`` returns plain ``async def`` tool functions bound to a
scope-bound service (an in-process ``EzraService`` *or* a
:class:`ezra_client.RemoteEzraService`). They have no ``google-adk`` import, so
this module is importable without the optional ``adk`` extra; ADK 2.x wraps a
bare ``async def`` as a ``FunctionTool`` automatically.

This mirrors ``ezra_core.adk_service.adk.ezra_adk_tools`` so an agent drives a
deployed Ezra over the client exactly as it would in-process.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ezra_client.errors import PolicyDeniedError


class TurnCounter:
    """Monotonic per-graph turn index shared across an agent's commits."""

    def __init__(self, start: int = 0) -> None:
        self._n = start

    def next(self) -> int:
        self._n += 1
        return self._n


def ezra_adk_tools(
    service: Any,
    turns: Optional[TurnCounter] = None,
    events: Optional[list] = None,
) -> list[Callable]:
    """Return the Ezra-bound ADK tool functions for ``service``'s agent.

    ``commit_belief`` routes through ``service.commit``, so a claim contradicting
    another agent's active commitment triggers the platform's two-pass checker +
    reconciler server-side — nothing staged. ``events``, if given, collects each
    fetch and each detected-and-reconciled contradiction as a dict.
    """
    turns = turns or TurnCounter()

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
        rows = (
            len(result.data)
            if isinstance(result.data, list)
            else (0 if result.data is None else 1)
        )
        if events is not None:
            events.append(
                {
                    "kind": "fetch",
                    "agent": service.agent_id,
                    "source": result.provenance.source,
                    "time_travel_available": result.provenance.time_travel_available,
                    "rows": rows,
                }
            )
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
                "similarity": outcome.contradiction.similarity_score,
                "nli_confidence": outcome.contradiction.nli_confidence,
                "decision": outcome.resolution.decision,
                "strategy": outcome.resolution.merge_strategy_used,
            }
            result["contradiction"] = detail
            if events is not None:
                events.append(detail)
        return result

    async def revert_belief(commitment_id: str, reason: str) -> dict:
        """Undo a single previously-committed belief (git-revert). The belief
        leaves the active state but the full history is preserved.

        Args:
            commitment_id: The id of the commitment to revert.
            reason: Why it is being reverted, one short phrase.
        """
        try:
            marker = await service.revert(
                commitment_id, reason=reason, turn_index=turns.next()
            )
        except KeyError:
            return {"status": "error", "reason": f"no such commitment: {commitment_id}"}
        return {"status": "success", "reverted": commitment_id, "marker_id": marker.id}

    async def rewind_beliefs(turn: int, reason: str) -> dict:
        """Rewind the whole team's belief state back to how it stood at a turn,
        undoing every commitment made after it (append-only, fully auditable).

        Args:
            turn: The turn index to rewind to.
            reason: Why the team is rewinding, one short phrase.
        """
        result = await service.rewind(turn, reason=reason)
        return {
            "status": "success",
            "rewound_to_turn": result.rewound_to_turn,
            "undone": result.superseded_ids,
            "restored": result.reactivated_ids,
        }

    async def replay_beliefs(turn: int) -> dict:
        """Show the team's belief state as it stood at a prior turn (read-only).

        Args:
            turn: The turn index to reconstruct the state at.
        """
        snap = await service.replay(turn)
        return {
            "status": "success",
            "as_of_turn": turn,
            "beliefs": [
                {"agent": c.agent_id, "topic": c.topic, "claim": c.claim}
                for c in snap.commitments
            ],
        }

    async def branch_beliefs(turn: int, branch_id: str) -> dict:
        """Fork a counterfactual branch from a prior turn (a separate what-if graph
        seeded with the state as it stood then).

        Args:
            turn: The turn index to branch from.
            branch_id: A name for the new branch.
        """
        try:
            branch = await service.branch_from(turn, branch_id)
        except RuntimeError as exc:
            return {"status": "error", "reason": str(exc)}
        return {"status": "success", "branch_id": branch.branch_id, "from_turn": turn}

    return [
        recall,
        belief_snapshot,
        fetch_federated,
        commit_belief,
        revert_belief,
        rewind_beliefs,
        replay_beliefs,
        branch_beliefs,
    ]


__all__ = ["TurnCounter", "ezra_adk_tools"]
