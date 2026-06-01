"""Policy engine — per-agent permission-scope enforcement (router step 2)."""

from ezra_core.policy.engine import PolicyDeniedError, PolicyEngine

__all__ = ["PolicyEngine", "PolicyDeniedError"]
