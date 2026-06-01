"""Two-pass contradiction detection — embedding similarity first, NLI second.

NON-NEGOTIABLE ARCHITECTURE (HANDOFF / final_report): detection is never
embedding-only.

  1. First pass — cheap embedding cosine similarity filters candidate pairs
     (only commitments on the same topic, similarity > threshold).
  2. Second pass — a local NLI classifier (DeBERTa-v3-base by default) labels
     each candidate pair entailment | neutral | contradiction. Only
     ``contradiction`` (at/above the confidence threshold) surfaces.

Embedding-only fails both ways: "the tyre is soft" vs "the tyre is firm" are
embedding-close but NOT contradictory; "recommend supplier A" vs "recommend
supplier B" are embedding-distant but ARE contradictory (caught because they
share a topic, then confirmed by NLI).

Both the embedder and the NLI classifier are injected (Protocols) so unit tests
use deterministic fakes; the real local-model implementations live at the bottom
and lazily import ``sentence_transformers`` (the optional ``ml`` dependency).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Literal, NamedTuple, Optional, Protocol, Sequence

from ezra_core.schemas.belief import Commitment, Contradiction

NliLabel = Literal["entailment", "neutral", "contradiction"]


class NliResult(NamedTuple):
    label: NliLabel
    confidence: float


class Embedder(Protocol):
    def encode(self, text: str) -> Sequence[float]: ...


class NliClassifier(Protocol):
    def classify(self, *, premise: str, hypothesis: str) -> NliResult: ...


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class ContradictionChecker:
    def __init__(
        self,
        embedder: Embedder,
        nli: NliClassifier,
        *,
        similarity_threshold: float = 0.85,
        nli_confidence_threshold: float = 0.7,
    ) -> None:
        self._embedder = embedder
        self._nli = nli
        self._sim_threshold = similarity_threshold
        self._nli_threshold = nli_confidence_threshold

    def check(
        self,
        *,
        new_claim: str,
        new_topic: str,
        new_agent_id: str,
        commitments: Sequence[Commitment],
    ) -> Optional[Contradiction]:
        """Return the first contradicting active commitment, or None."""
        new_vec = self._embedder.encode(new_claim)
        for c in commitments:
            if c.superseded or c.redacted or c.topic != new_topic:
                continue

            similarity = cosine_similarity(new_vec, self._embedder.encode(c.claim))
            if similarity <= self._sim_threshold:  # first pass
                continue

            result = self._nli.classify(premise=c.claim, hypothesis=new_claim)  # second pass
            if result.label != "contradiction" or result.confidence < self._nli_threshold:
                continue

            return Contradiction(
                existing_commitment_id=c.id,
                existing_agent_id=c.agent_id,
                new_input_claim=new_claim,
                new_agent_id=new_agent_id,
                topic=new_topic,
                similarity_score=similarity,
                nli_confidence=result.confidence,
                detected_at=datetime.now(timezone.utc),
            )
        return None


# --------------------------------------------------------------------------- #
# Real local-model implementations (optional `ml` group: sentence-transformers)
# --------------------------------------------------------------------------- #
class SentenceTransformerEmbedder:
    """Local embedder. Default model is small + fast (~384-dim MiniLM)."""

    def __init__(self, model: str = "all-MiniLM-L6-v2", device: str = "auto") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(
            model, device=None if device == "auto" else device
        )

    def encode(self, text: str) -> Sequence[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()


# nli-deberta-v3-base label order (per the model card).
_DEBERTA_LABELS: tuple[NliLabel, ...] = ("contradiction", "entailment", "neutral")


class LocalNliClassifier:
    """Local NLI via sentence-transformers ``CrossEncoder`` (DeBERTa by default)."""

    def __init__(
        self,
        model: str = "cross-encoder/nli-deberta-v3-base",
        device: str = "auto",
        labels: tuple[NliLabel, ...] = _DEBERTA_LABELS,
    ) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model, device=None if device == "auto" else device)
        self._labels = labels

    def classify(self, *, premise: str, hypothesis: str) -> NliResult:
        import numpy as np

        scores = np.asarray(self._model.predict([(premise, hypothesis)])[0], dtype=float)
        exp = np.exp(scores - scores.max())
        probs = exp / exp.sum()
        idx = int(probs.argmax())
        return NliResult(label=self._labels[idx], confidence=float(probs[idx]))
