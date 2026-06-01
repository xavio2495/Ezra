import asyncio
from datetime import datetime, timezone

import pytest

from ezra_core.belief.reconciler import ResolveContext, reconcile
from ezra_core.schemas.belief import Contradiction, Resolution


def _contradiction(topic: str = "tyres") -> Contradiction:
    return Contradiction(
        existing_commitment_id="c1",
        existing_agent_id="eng_a",
        new_input_claim="hard compound now",
        new_agent_id="eng_b",
        topic=topic,
        similarity_score=0.95,
        nli_confidence=0.9,
        detected_at=datetime.now(timezone.utc),
    )


async def test_last_write_wins():
    r = await reconcile(
        _contradiction(), merge_strategy="last_write_wins", existing_trust=1.0, new_trust=0.1
    )
    assert r.decision == "accept_new"
    assert r.merge_strategy_used == "last_write_wins"


async def test_highest_trust_new_wins_and_loses():
    win = await reconcile(
        _contradiction(), merge_strategy="highest_trust", existing_trust=0.4, new_trust=0.9
    )
    assert win.decision == "accept_new"

    lose = await reconcile(
        _contradiction(), merge_strategy="highest_trust", existing_trust=0.9, new_trust=0.4
    )
    assert lose.decision == "keep_existing"


async def test_manual_callback_decision():
    async def callback(event):
        return "keep_existing"

    r = await reconcile(
        _contradiction(),
        merge_strategy="manual",
        existing_trust=1.0,
        new_trust=1.0,
        on_contradiction=callback,
    )
    assert r.decision == "keep_existing"
    assert r.merge_strategy_used == "manual"


async def test_manual_timeout_falls_back_to_accept_new():
    async def slow_callback(event):
        await asyncio.sleep(0.5)
        return "keep_existing"

    r = await reconcile(
        _contradiction(),
        merge_strategy="manual",
        existing_trust=1.0,
        new_trust=1.0,
        on_contradiction=slow_callback,
        manual_resolution_timeout_seconds=0,
    )
    assert r.decision == "accept_new"
    assert r.merge_strategy_used == "manual_timeout_fallback"


async def test_manual_no_callback_falls_back():
    r = await reconcile(
        _contradiction(), merge_strategy="manual", existing_trust=1.0, new_trust=1.0
    )
    assert r.decision == "accept_new"
    assert r.merge_strategy_used == "manual_no_callback_fallback"


async def test_custom_resolver_signature_and_decision():
    seen = {}

    async def resolver(contradiction: Contradiction, ctx: ResolveContext) -> Resolution:
        seen["contradiction"] = contradiction
        seen["ctx"] = ctx
        if ctx.topic == "tyres":
            return Resolution.keep_existing()
        return Resolution.accept_new()

    r = await reconcile(
        _contradiction(),
        merge_strategy="custom",
        existing_trust=1.0,
        new_trust=1.0,
        custom_resolver=resolver,
    )
    assert r.decision == "keep_existing"
    assert isinstance(seen["contradiction"], Contradiction)
    assert isinstance(seen["ctx"], ResolveContext)
    assert seen["ctx"].existing_agent_id == "eng_a"


async def test_custom_resolver_can_fallback_to_builtin():
    async def resolver(contradiction, ctx) -> Resolution:
        return Resolution.fallback_to("highest_trust")

    r = await reconcile(
        _contradiction(),
        merge_strategy="custom",
        existing_trust=0.2,
        new_trust=0.9,
        custom_resolver=resolver,
    )
    # Delegated to highest_trust with new_trust > existing_trust → accept_new.
    assert r.decision == "accept_new"
    assert r.merge_strategy_used == "highest_trust"


async def test_custom_without_resolver_raises():
    with pytest.raises(ValueError):
        await reconcile(
            _contradiction(), merge_strategy="custom", existing_trust=1.0, new_trust=1.0
        )


def test_resolve_context_contemporaneous_count():
    from ezra_core.schemas.belief import Commitment

    def mk(topic):
        return Commitment(
            id=topic,
            session_graph_id="g",
            agent_id="a",
            turn_index=1,
            type="fact",
            claim="x",
            topic=topic,
            created_at=datetime.now(timezone.utc),
        )

    ctx = ResolveContext(
        topic="tyres",
        existing_agent_id="a",
        new_agent_id="b",
        existing_trust=1.0,
        new_trust=1.0,
        active_commitments=[mk("tyres"), mk("tyres"), mk("fuel")],
        regulatory_mode="strict",
    )
    assert ctx.contemporaneous_contradictions_on_topic("tyres") == 2
    assert ctx.regulatory_mode == "strict"  # extra app field attached
