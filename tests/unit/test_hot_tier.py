from fakeredis import FakeAsyncRedis

from ezra_core.tiers.hot import HotTier


def _hot(max_turns: int = 8) -> HotTier:
    return HotTier(FakeAsyncRedis(decode_responses=True), max_turns=max_turns)


async def test_per_agent_isolation():
    hot = _hot()
    await hot.append_turn("g", "a", {"content": "hi-a"})
    await hot.append_turn("g", "b", {"content": "hi-b"})

    a_turns = await hot.get_turns("g", "a")
    b_turns = await hot.get_turns("g", "b")
    assert len(a_turns) == 1 and a_turns[0]["content"] == "hi-a"
    assert len(b_turns) == 1 and b_turns[0]["content"] == "hi-b"


async def test_turns_capped_and_ordered():
    hot = _hot(max_turns=3)
    for i in range(5):
        await hot.append_turn("g", "a", {"i": i})
    turns = await hot.get_turns("g", "a")
    assert [t["i"] for t in turns] == [2, 3, 4]  # oldest evicted, order preserved


async def test_pinned_beliefs_and_mesh_result():
    hot = _hot()
    await hot.set_pinned_beliefs("g", "a", [{"claim": "x"}])
    await hot.set_mesh_result("g", "a", {"stock": 2})
    assert await hot.get_pinned_beliefs("g", "a") == [{"claim": "x"}]
    assert await hot.get_mesh_result("g", "a") == {"stock": 2}
    # untouched agent is empty
    assert await hot.get_pinned_beliefs("g", "b") == []
    assert await hot.get_mesh_result("g", "b") is None


async def test_clear_agent():
    hot = _hot()
    await hot.append_turn("g", "a", {"content": "x"})
    await hot.set_pinned_beliefs("g", "a", [{"claim": "y"}])
    await hot.clear_agent("g", "a")
    assert await hot.get_turns("g", "a") == []
    assert await hot.get_pinned_beliefs("g", "a") == []
