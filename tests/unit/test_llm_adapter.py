from types import SimpleNamespace

import pytest

from ezra_core.llm.adapter import GeminiEmbedder, LLMAdapter, LLMError


def _response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


async def test_complete_returns_content(monkeypatch):
    import litellm

    calls = {}

    async def fake_acompletion(**kwargs):
        calls.update(kwargs)
        return _response("pit on lap 18")

    monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
    adapter = LLMAdapter("gemini/gemini-2.0-flash", api_key="k")
    out = await adapter.complete([{"role": "user", "content": "when to pit?"}])

    assert out == "pit on lap 18"
    assert calls["model"] == "gemini/gemini-2.0-flash"
    assert calls["api_key"] == "k"


async def test_complete_retries_then_succeeds(monkeypatch):
    import litellm

    attempts = {"n": 0}

    async def flaky(**kwargs):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("rate limited")
        return _response("ok")

    monkeypatch.setattr(litellm, "acompletion", flaky)
    adapter = LLMAdapter("m", max_retries=2, base_backoff=0)
    assert await adapter.complete([{"role": "user", "content": "x"}]) == "ok"
    assert attempts["n"] == 2


async def test_complete_raises_after_exhausting_retries(monkeypatch):
    import litellm

    async def always_fail(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(litellm, "acompletion", always_fail)
    adapter = LLMAdapter("m", max_retries=1, base_backoff=0)
    with pytest.raises(LLMError):
        await adapter.complete([{"role": "user", "content": "x"}])


def test_embedder_encode(monkeypatch):
    import litellm

    def fake_embedding(**kwargs):
        assert kwargs["input"] == ["hello"]
        return {"data": [{"embedding": [0.1, 0.2, 0.3]}]}

    monkeypatch.setattr(litellm, "embedding", fake_embedding)
    assert GeminiEmbedder(api_key="k").encode("hello") == [0.1, 0.2, 0.3]
