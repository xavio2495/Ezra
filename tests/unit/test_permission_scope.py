import pytest

from ezra_core.policy.engine import PolicyDeniedError, PolicyEngine


def test_allows_in_scope_denies_out_of_scope():
    engine = PolicyEngine()
    assert engine.allows(["inventory", "warehouse"], "inventory") is True
    assert engine.allows(["inventory", "warehouse"], "procurement") is False


def test_check_topic_raises_with_topic_on_error():
    engine = PolicyEngine()
    with pytest.raises(PolicyDeniedError) as exc:
        engine.check_topic(["inventory"], "procurement")
    assert exc.value.topic == "procurement"


def test_check_topics_denies_first_out_of_scope():
    engine = PolicyEngine()
    engine.check_topics(["a", "b", "c"], ["a", "c"])  # all in scope → no raise
    with pytest.raises(PolicyDeniedError):
        engine.check_topics(["a", "b"], ["a", "z"])


def test_disabled_engine_allows_everything():
    engine = PolicyEngine(enabled=False)
    assert engine.allows([], "anything") is True
    engine.check_topic([], "anything")  # no raise
    engine.check_topics([], ["x", "y"])  # no raise


async def test_router_fetch_is_policy_gated():
    from ezra_core.mesh.snowflake import SnowflakeConnector
    from ezra_core.router import fetch

    connector = SnowflakeConnector("db.inventory", executor=lambda sql: [{"stock": 2}])
    engine = PolicyEngine()

    # In-scope topic → fetch succeeds.
    result = await fetch(
        connector=connector,
        policy=engine,
        query="current inventory",
        agent_id="inv",
        permission_scope=["inventory"],
        topics=["inventory"],
    )
    assert result.data == [{"stock": 2}]

    # Out-of-scope topic → denied before any data is fetched.
    with pytest.raises(PolicyDeniedError):
        await fetch(
            connector=connector,
            policy=engine,
            query="active procurement contracts",
            agent_id="inv",
            permission_scope=["inventory"],
            topics=["procurement"],
        )
