"""Two-pass contradiction detection — pipeline logic with deterministic fakes.

The real local-model validation (DeBERTa) is a separate, opt-in test at the
bottom, gated on EZRA_RUN_NLI_TESTS (it downloads ~hundreds of MB and needs the
`ml` dependency group).
"""

import os
from datetime import datetime, timezone

import pytest

from ezra_core.belief.checker import ContradictionChecker, NliResult
from ezra_core.schemas.belief import Commitment


def _c(cid: str, claim: str, *, topic: str = "tyres", agent: str = "eng_a") -> Commitment:
    return Commitment(
        id=cid,
        session_graph_id="g1",
        agent_id=agent,
        turn_index=1,
        type="decision",
        claim=claim,
        topic=topic,
        created_at=datetime.now(timezone.utc),
    )


class FakeEmbedder:
    """Returns a preset vector per claim; unknown claims get an orthogonal one."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._v = vectors

    def encode(self, text: str) -> list[float]:
        return self._v.get(text, [0.0, 0.0, 1.0])


class FakeNli:
    def __init__(self, result: NliResult) -> None:
        self.result = result
        self.calls = 0

    def classify(self, *, premise: str, hypothesis: str) -> NliResult:
        self.calls += 1
        return self.result


# Two claims the embedder treats as near-identical (cosine ~1.0).
_CLOSE = {"soft compound now": [1.0, 0.0, 0.0], "hard compound now": [1.0, 0.01, 0.0]}


async def test_contradiction_detected_when_similar_and_nli_contradiction():
    checker = ContradictionChecker(
        FakeEmbedder(_CLOSE), FakeNli(NliResult("contradiction", 0.95))
    )
    found = checker.check(
        new_claim="hard compound now",
        new_topic="tyres",
        new_agent_id="eng_b",
        commitments=[_c("c1", "soft compound now")],
    )
    assert found is not None
    assert found.existing_commitment_id == "c1"
    assert found.nli_confidence == 0.95


async def test_embedding_close_but_nli_not_contradiction_is_ignored():
    nli = FakeNli(NliResult("neutral", 0.99))
    checker = ContradictionChecker(FakeEmbedder(_CLOSE), nli)
    found = checker.check(
        new_claim="hard compound now",
        new_topic="tyres",
        new_agent_id="eng_b",
        commitments=[_c("c1", "soft compound now")],
    )
    assert found is None
    assert nli.calls == 1  # second pass ran, but label wasn't 'contradiction'


async def test_low_similarity_skips_nli_second_pass():
    nli = FakeNli(NliResult("contradiction", 0.99))
    embedder = FakeEmbedder({"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0]})  # orthogonal
    checker = ContradictionChecker(embedder, nli)
    found = checker.check(
        new_claim="b", new_topic="tyres", new_agent_id="x", commitments=[_c("c1", "a")]
    )
    assert found is None
    assert nli.calls == 0  # first pass filtered it out — NLI never invoked


async def test_topic_mismatch_skips():
    checker = ContradictionChecker(
        FakeEmbedder(_CLOSE), FakeNli(NliResult("contradiction", 0.99))
    )
    found = checker.check(
        new_claim="hard compound now",
        new_topic="fuel",
        new_agent_id="x",
        commitments=[_c("c1", "soft compound now", topic="tyres")],
    )
    assert found is None


async def test_confidence_below_threshold_ignored():
    checker = ContradictionChecker(
        FakeEmbedder(_CLOSE),
        FakeNli(NliResult("contradiction", 0.5)),
        nli_confidence_threshold=0.7,
    )
    found = checker.check(
        new_claim="hard compound now",
        new_topic="tyres",
        new_agent_id="x",
        commitments=[_c("c1", "soft compound now")],
    )
    assert found is None


async def test_superseded_and_redacted_commitments_skipped():
    checker = ContradictionChecker(
        FakeEmbedder(_CLOSE), FakeNli(NliResult("contradiction", 0.99))
    )
    superseded = _c("c1", "soft compound now")
    superseded.superseded = True
    found = checker.check(
        new_claim="hard compound now",
        new_topic="tyres",
        new_agent_id="x",
        commitments=[superseded],
    )
    assert found is None


async def test_router_belief_check_consistent_claim_returns_none():
    from ezra_core.router import belief_check

    checker = ContradictionChecker(
        FakeEmbedder(_CLOSE), FakeNli(NliResult("neutral", 0.99))
    )
    contradiction, resolution = await belief_check(
        checker=checker,
        commitments=[_c("c1", "soft compound now")],
        new_claim="hard compound now",
        new_topic="tyres",
        new_agent_id="eng_b",
        new_trust=1.0,
        merge_strategy="last_write_wins",
    )
    assert contradiction is None and resolution is None


async def test_router_belief_check_reconciles_with_per_agent_trust():
    from ezra_core.router import belief_check

    checker = ContradictionChecker(
        FakeEmbedder(_CLOSE), FakeNli(NliResult("contradiction", 0.95))
    )
    trust = {"eng_a": 0.9, "eng_b": 0.2}
    contradiction, resolution = await belief_check(
        checker=checker,
        commitments=[_c("c1", "soft compound now", agent="eng_a")],
        new_claim="hard compound now",
        new_topic="tyres",
        new_agent_id="eng_b",
        new_trust=trust["eng_b"],
        merge_strategy="highest_trust",
        existing_trust_for=lambda agent_id: trust[agent_id],
    )
    assert contradiction is not None
    # eng_a (0.9) outranks eng_b (0.2) on tyres → keep existing.
    assert resolution.decision == "keep_existing"


@pytest.mark.skipif(
    not os.getenv("EZRA_RUN_NLI_TESTS"),
    reason="set EZRA_RUN_NLI_TESTS=1 (and `uv sync --group ml`) to run the real DeBERTa model",
)
def test_real_nli_known_pairs():
    from ezra_core.belief.checker import LocalNliClassifier

    nli = LocalNliClassifier()
    # Embedding-distant but topically contradictory:
    assert nli.classify(
        premise="recommend supplier A", hypothesis="recommend supplier B"
    ).label == "contradiction"
    # Same meaning, different surface form — must NOT be a contradiction:
    assert (
        nli.classify(premise="prices will increase", hypothesis="prices will rise").label
        != "contradiction"
    )
