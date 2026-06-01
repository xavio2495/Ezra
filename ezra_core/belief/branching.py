"""Branching replay — branch from a prior turn, mutate state, run forward, diff.

A branch is itself a first-class session graph (id == branch_id): we reconstruct
the parent's belief state as-of ``turn`` (time-aware supersession) and seed the
branch's belief store with those commitments re-keyed to the branch. From there
the branch can be mutated and run forward independently, then diffed against the
parent.

``run_forward`` takes an injected ``step`` coroutine (one turn of agent work) so
this is testable today; the real LLM/agent runner is wired in once the router +
llm adapter land.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional, Protocol
from uuid import uuid4

from ezra_core.belief.replay import reconstruct_state_at_turn, snapshot_now
from ezra_core.belief.store import BeliefStore
from ezra_core.schemas.belief import Commitment
from ezra_core.schemas.branch import Branch, BranchDiff
from ezra_core.schemas.session_graph import SessionGraph as SessionGraphRecord
from ezra_core.session_graph import SessionGraphStore

# One turn of forward execution within a branch. Returns anything (e.g. a model
# response); side effects (new commitments) go through the belief store.
ForwardStep = Callable[..., Awaitable[object]]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Branch metadata persistence (same Protocol + InMemory + Mongo shape as the
# other stores).
# --------------------------------------------------------------------------- #
class BranchStore(Protocol):
    async def save(self, branch: Branch) -> None: ...
    async def get(self, branch_id: str) -> Optional[Branch]: ...


class InMemoryBranchStore:
    def __init__(self) -> None:
        self._items: dict[str, Branch] = {}

    async def save(self, branch: Branch) -> None:
        self._items[branch.branch_id] = branch.model_copy(deep=True)

    async def get(self, branch_id: str) -> Optional[Branch]:
        b = self._items.get(branch_id)
        return b.model_copy(deep=True) if b is not None else None


class MongoBranchStore:
    def __init__(self, client, db_name: str, collection: str = "branches") -> None:
        self._c = client[db_name][collection]

    async def save(self, branch: Branch) -> None:
        doc = branch.model_dump(mode="json")
        doc["_id"] = branch.branch_id
        await self._c.replace_one({"_id": branch.branch_id}, doc, upsert=True)

    async def get(self, branch_id: str) -> Optional[Branch]:
        doc = await self._c.find_one({"_id": branch_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return Branch.model_validate(doc)


# --------------------------------------------------------------------------- #
# Manager
# --------------------------------------------------------------------------- #
class BranchManager:
    def __init__(
        self,
        *,
        graph_store: SessionGraphStore,
        belief_store: BeliefStore,
        branch_store: BranchStore,
    ) -> None:
        self._graphs = graph_store
        self._beliefs = belief_store
        self._branches = branch_store

    async def branch_from(
        self,
        *,
        session_graph_id: str,
        turn: int,
        branch_id: str,
        description: Optional[str] = None,
    ) -> Branch:
        snapshot = await reconstruct_state_at_turn(self._beliefs, session_graph_id, turn)

        parent = await self._graphs.get(session_graph_id)
        record = SessionGraphRecord(
            session_graph_id=branch_id,
            created_at=_utcnow(),
            description=description or f"branch of {session_graph_id}@turn{turn}",
            merge_strategy=parent.merge_strategy if parent else "last_write_wins",
        )
        await self._graphs.save(record)

        # Seed the branch's belief store with the parent's state as-of `turn`.
        for commitment in snapshot.commitments:
            await self._beliefs.append(
                commitment.model_copy(
                    update={"id": f"{branch_id}:{commitment.id}", "session_graph_id": branch_id}
                )
            )

        branch = Branch(
            branch_id=branch_id,
            parent_session_graph_id=session_graph_id,
            parent_turn=turn,
            created_at=_utcnow(),
            description=description,
        )
        await self._branches.save(branch)
        return branch

    async def mutate_belief(
        self,
        *,
        branch_id: str,
        agent_id: str,
        new_claim: str,
        topic: str,
        type: str = "decision",
        turn_index: Optional[int] = None,
    ) -> Commitment:
        branch = await self._branches.get(branch_id)
        if branch is None:
            raise KeyError(f"branch not found: {branch_id}")

        turn = turn_index if turn_index is not None else branch.parent_turn + 1
        commitment = Commitment(
            id=str(uuid4()),
            session_graph_id=branch_id,
            agent_id=agent_id,
            turn_index=turn,
            type=type,  # type: ignore[arg-type]
            claim=new_claim,
            topic=topic,
            created_at=_utcnow(),
        )
        await self._beliefs.append(commitment)
        branch.mutations.append(
            {"agent_id": agent_id, "claim": new_claim, "topic": topic, "turn_index": turn}
        )
        await self._branches.save(branch)
        return commitment

    async def run_forward(
        self,
        *,
        branch_id: str,
        until_turn: int,
        step: ForwardStep,
    ) -> list[object]:
        branch = await self._branches.get(branch_id)
        if branch is None:
            raise KeyError(f"branch not found: {branch_id}")

        results: list[object] = []
        for turn in range(branch.parent_turn + 1, until_turn + 1):
            results.append(await step(branch_id=branch_id, turn=turn))

        branch.forward_runs.append(
            {"from_turn": branch.parent_turn, "until_turn": until_turn, "steps": len(results)}
        )
        await self._branches.save(branch)
        return results

    async def diff_branches(
        self, *, original: str, branch: str, from_turn: int
    ) -> BranchDiff:
        orig = await snapshot_now(self._beliefs, original)
        brn = await snapshot_now(self._beliefs, branch)

        def by_topic(commitments):
            out: dict[str, set[str]] = {}
            for c in commitments:
                if c.turn_index >= from_turn:
                    out.setdefault(c.topic, set()).add(c.claim)
            return out

        orig_by_topic = by_topic(orig.commitments)
        brn_by_topic = by_topic(brn.commitments)

        diverged: list[dict] = []
        for topic in sorted(set(orig_by_topic) | set(brn_by_topic)):
            o = orig_by_topic.get(topic, set())
            b = brn_by_topic.get(topic, set())
            if o != b:
                diverged.append(
                    {
                        "topic": topic,
                        "only_in_original": sorted(o - b),
                        "only_in_branch": sorted(b - o),
                    }
                )

        return BranchDiff(
            original_session_graph_id=original,
            branch_id=branch,
            from_turn=from_turn,
            diverged_commitments=diverged,
        )
