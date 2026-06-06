"""FastAPI app for the REST surface. All endpoints require
``Authorization: Bearer <token>`` when a token is configured.

Built via ``create_app(...)`` with the platform components injected, so it's
testable with ``fastapi.testclient.TestClient`` and no live infra.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from ezra_core.belief.branching import BranchManager, ForwardStep
from ezra_core.belief.checker import ContradictionChecker
from ezra_core.belief.replay import reconstruct_state_at_turn, snapshot_now
from ezra_core.belief.store import BeliefStore
from ezra_core.mesh.base import BaseConnector
from ezra_core.policy.engine import PolicyDeniedError, PolicyEngine
from ezra_core.router import Router
from ezra_core.schemas.belief import BeliefSnapshot, Contradiction
from ezra_core.schemas.branch import Branch, BranchDiff
from ezra_core.schemas.context import AssembledContext
from ezra_core.schemas.mesh import MeshResult
from ezra_core.schemas.session_graph import AgentRegistration


class SnapshotRequest(BaseModel):
    session_graph_id: str
    scope: Optional[list[str]] = None
    as_of_turn: Optional[int] = None


class CheckRequest(BaseModel):
    session_graph_id: str
    agent_id: str
    claim: str
    topic: str


class MeshQueryRequest(BaseModel):
    session_graph_id: str
    agent_id: str
    query: str
    scope: list[str] = []
    topics: list[str] = []


class ReplayRequest(BaseModel):
    session_graph_id: str
    turn: int
    scope: Optional[list[str]] = None


class BranchRequest(BaseModel):
    session_graph_id: str
    turn: int
    branch_id: str
    description: Optional[str] = None


class BranchDiffRequest(BaseModel):
    original: str
    branch: str
    from_turn: int


class AssembleRequest(BaseModel):
    session_graph_id: str
    agent_id: str
    scope: list[str] = []
    user_input: str
    system_prompt: str = ""
    mesh_query: Optional[str] = None
    mesh_topics: list[str] = []


class RunForwardRequest(BaseModel):
    branch_id: str
    until_turn: int


def create_app(
    *,
    belief_store: BeliefStore,
    checker: Optional[ContradictionChecker] = None,
    branch_manager: Optional[BranchManager] = None,
    mesh: Optional[BaseConnector] = None,
    policy: Optional[PolicyEngine] = None,
    router: Optional[Router] = None,
    forward_step: Optional[ForwardStep] = None,
    bearer_token: Optional[str] = None,
) -> FastAPI:
    app = FastAPI(title="Ezra", version="0.1.0")
    pol = policy or PolicyEngine(enabled=False)

    async def auth(authorization: str = Header(default="")) -> None:
        if bearer_token and authorization != f"Bearer {bearer_token}":
            raise HTTPException(status_code=401, detail="invalid or missing bearer token")

    guarded = [Depends(auth)]

    @app.get("/ezra/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "checker": checker is not None,
            "mesh": mesh is not None,
            "branching": branch_manager is not None,
            "router": router is not None,
        }

    @app.post("/ezra/context/assemble", dependencies=guarded)
    async def context_assemble(req: AssembleRequest) -> AssembledContext:
        if router is None:
            raise HTTPException(status_code=400, detail="no router configured")
        agent = AgentRegistration(
            agent_id=req.agent_id,
            session_graph_id=req.session_graph_id,
            permission_scope=req.scope,
            spawned_at=datetime.now(timezone.utc),
        )
        try:
            return await router.assemble_context(
                agent=agent,
                user_input=req.user_input,
                system_prompt=req.system_prompt,
                mesh_query=req.mesh_query,
                mesh_topics=req.mesh_topics,
            )
        except PolicyDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/ezra/belief/snapshot", dependencies=guarded)
    async def belief_snapshot(req: SnapshotRequest) -> BeliefSnapshot:
        scope = set(req.scope) if req.scope is not None else None
        if req.as_of_turn is not None:
            return await reconstruct_state_at_turn(
                belief_store, req.session_graph_id, req.as_of_turn, scope_topics=scope
            )
        return await snapshot_now(belief_store, req.session_graph_id, scope_topics=scope)

    @app.post("/ezra/belief/check", dependencies=guarded)
    async def belief_check(req: CheckRequest) -> dict:
        if checker is None:
            return {"contradiction": None}
        active = await belief_store.get_active(req.session_graph_id, topic=req.topic)
        found: Optional[Contradiction] = checker.check(
            new_claim=req.claim, new_topic=req.topic, new_agent_id=req.agent_id, commitments=active
        )
        return {"contradiction": found.model_dump(mode="json") if found else None}

    @app.post("/ezra/mesh/query", dependencies=guarded)
    async def mesh_query(req: MeshQueryRequest) -> MeshResult:
        if mesh is None:
            raise HTTPException(status_code=400, detail="no mesh connector configured")
        try:
            pol.check_topics(req.scope, req.topics)
        except PolicyDeniedError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return await mesh.fetch(req.query, req.agent_id, req.scope)

    @app.post("/ezra/replay", dependencies=guarded)
    async def replay(req: ReplayRequest) -> BeliefSnapshot:
        scope = set(req.scope) if req.scope is not None else None
        return await reconstruct_state_at_turn(
            belief_store, req.session_graph_id, req.turn, scope_topics=scope
        )

    @app.post("/ezra/branch", dependencies=guarded)
    async def branch(req: BranchRequest) -> Branch:
        if branch_manager is None:
            raise HTTPException(status_code=400, detail="branching not configured")
        return await branch_manager.branch_from(
            session_graph_id=req.session_graph_id,
            turn=req.turn,
            branch_id=req.branch_id,
            description=req.description,
        )

    @app.post("/ezra/branch/diff", dependencies=guarded)
    async def branch_diff(req: BranchDiffRequest) -> BranchDiff:
        if branch_manager is None:
            raise HTTPException(status_code=400, detail="branching not configured")
        return await branch_manager.diff_branches(
            original=req.original, branch=req.branch, from_turn=req.from_turn
        )

    @app.post("/ezra/branch/run-forward", dependencies=guarded)
    async def branch_run_forward(req: RunForwardRequest) -> dict:
        if branch_manager is None:
            raise HTTPException(status_code=400, detail="branching not configured")
        if forward_step is None:
            # Running a branch forward re-executes agent turns, which needs a
            # configured agent step — supplied by the composition root, not the
            # generic REST surface. Honest 501 rather than a silent no-op.
            raise HTTPException(
                status_code=501,
                detail="run-forward requires a configured agent step (forward_step)",
            )
        results = await branch_manager.run_forward(
            branch_id=req.branch_id, until_turn=req.until_turn, step=forward_step
        )
        return {
            "branch_id": req.branch_id,
            "until_turn": req.until_turn,
            "steps": len(results),
        }

    return app
