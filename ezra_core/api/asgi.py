"""ASGI composition root for the REST API (production entrypoint).

``create_app`` takes injected components so it stays unit-testable; this module
is the thin "wire it from settings" layer the container runs:

    uvicorn ezra_core.api.asgi:app --host 0.0.0.0 --port 8080

With ``EZRA_MONGODB_URI`` set it builds the real cold-tier-backed surface
(Mongo belief store + branch manager). Without it, it still boots a health-only
app so the container is live for readiness probes before Atlas wiring. The
contradiction checker (needs the opt-in ``ml`` deps) and mesh connectors are
left unconfigured here — they are wired per-deployment as needed.

On GKE, secrets are delivered as files by the Secret Manager CSI add-on (it
mounts each Secret Manager secret as a file; it does NOT sync a Kubernetes
Secret). ``_load_secret_files`` reads that mount and exports each file as the
matching ``EZRA_*`` env var (``ezra-mongodb-uri`` -> ``EZRA_MONGODB_URI``) before
settings are read. ``setdefault`` means an explicit env var still wins, and the
whole step is a no-op when the mount is absent (local/dev).
"""

from __future__ import annotations

from ezra_core.api.app import create_app
from ezra_core.config import EzraSettings
from ezra_core.secret_files import load_secret_files


def build_app():
    load_secret_files()
    settings = EzraSettings()
    token = settings.api_bearer_token or None

    if not settings.mongodb_uri:
        from ezra_core.belief.store import InMemoryBeliefStore

        return create_app(belief_store=InMemoryBeliefStore(), bearer_token=token)

    # Full surface: build the Ezra runtime and expose every core feature over REST
    # (belief, branch, commit, recall, rewind, revert) so remote ADK agents can
    # drive a deployed Ezra. The contradiction checker is left OFF here so commits
    # over the network never incur embedding/NLI token cost — the in-process fleet
    # exercises two-pass detection; the remote surface is for belief lifecycle ops
    # (commit / rewind / revert / branch / replay).
    from ezra_core.adk_service.service import EzraService
    from ezra_core.runtime import Ezra

    ezra = Ezra.from_settings(settings, build_checker=False)
    ezra.checker = None

    def service_factory(session_graph_id: str, agent_id: str, scope: list[str]) -> EzraService:
        return EzraService(
            session_graph_id=session_graph_id,
            agent_id=agent_id,
            permission_scope=scope,
            belief_store=ezra.belief_store,
            warm=ezra.warm,
            checker=ezra.checker,
            mesh=None,
            branch_manager=ezra.branch_manager,
            policy=ezra.policy,
            merge_strategy=settings.default_merge_strategy,
            manual_resolution_timeout_seconds=settings.manual_resolution_timeout_seconds,
            audit_log=ezra.audit_log,
        )

    return create_app(
        belief_store=ezra.belief_store,
        checker=ezra.checker,
        branch_manager=ezra.branch_manager,
        policy=ezra.policy,
        service_factory=service_factory,
        audit_log=ezra.audit_log,
        bearer_token=token,
    )


app = build_app()
