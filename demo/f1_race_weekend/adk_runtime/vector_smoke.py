"""Live smoke for spec-gap #2: per-turn archival semantic recall by vector
similarity, backed by **Atlas Vector Search**.

Runs in-cluster as a Job (Vertex keyless via WIF) against live Atlas. It:

  1. builds the Mongo semantic store with a real Vertex embedder,
  2. creates the ``$vectorSearch`` index sized to the embedder's *actual*
     dimension (probed live — text-embedding-005 = 768, gemini-embedding-001 =
     3072), via ``MongoSemanticStore.ensure_vector_index``,
  3. writes a few archival facts (embedded on ``add``),
  4. waits for the index to become queryable (Atlas builds it asynchronously),
  5. proves ``recall_archival`` returns the semantically-closest fact for two
     different queries — i.e. real vector ranking, not topic/scope order.

This is the live half of gap #2 (the in-memory cosine path is unit-proven). The
test facts are written under a unique ``user_id`` and deleted at the end; the
production index is left in place.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime, timezone

from ezra_core.config import EzraSettings
from ezra_core.llm.adapter import GeminiEmbedder, is_vertex_model
from ezra_core.schemas.memory import SemanticFact
from ezra_core.secret_files import load_secret_files
from ezra_core.tiers.cold import cold_tier_from_settings

USER = f"vec-user-{uuid.uuid4().hex[:8]}"
GRAPH = f"vec-smoke-{uuid.uuid4().hex[:8]}"


def _fact(subject: str, predicate: str, obj: str, topics: list[str]) -> SemanticFact:
    now = datetime.now(timezone.utc)
    return SemanticFact(
        id=str(uuid.uuid4()),
        user_id=USER,
        subject=subject,
        predicate=predicate,
        object=obj,
        tier="archival",
        topics=topics,
        confidence=0.9,
        source_session_graph_ids=[GRAPH],
        created_at=now,
        updated_at=now,
    )


FACTS = [
    _fact("medium tyres", "last", "about 25 laps before the cliff", ["tyres"]),
    _fact("the safety car", "bunches", "the field and erases pit-stop gaps", ["strategy"]),
    _fact("fuel load", "costs", "roughly 0.03s per lap per kilogram", ["fuel"]),
]
SCOPE = {"tyres", "strategy", "fuel"}


async def _wait_queryable(collection, name: str, timeout: int = 240) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            async for ix in await collection.list_search_indexes():
                if ix.get("name") == name and ix.get("queryable"):
                    return True
        except Exception as exc:  # noqa: BLE001 — index may not be listable yet
            print(f"  (list_search_indexes: {type(exc).__name__}: {str(exc)[:120]})")
        await asyncio.sleep(8)
    return False


async def _main() -> None:  # pragma: no cover — GKE Job entrypoint
    load_secret_files()
    settings = EzraSettings()
    # We connect to Atlas directly (not via Ezra.from_settings), so allow this
    # pod's egress IP on the Atlas access list first (Admin API, idempotent).
    from ezra_core.atlas_access import ensure_egress_allowed

    ensure_egress_allowed(settings)
    print(f"=== gap #2 live: Atlas Vector Search archival recall (user={USER}) ===")
    print(f"  embedding model: {settings.embedding_model}")
    print(f"  vector index   : {settings.semantic_vector_index}")

    embed_key = None if is_vertex_model(settings.embedding_model) else (settings.llm_api_key or None)
    embedder = GeminiEmbedder(settings.embedding_model, api_key=embed_key)
    dim = len(embedder.encode("dimension probe"))
    print(f"  embedding dim  : {dim}")

    cold = cold_tier_from_settings(settings, embedder=embedder)
    store = cold.semantic
    collection = store._c  # noqa: SLF001 — smoke script, direct collection access
    ok = False
    try:
        # 1. index (idempotent) — sized to the live embedder dimension.
        await store.ensure_vector_index(dim)
        print("  ensure_vector_index: requested")

        # 2. write embedded archival facts.
        for f in FACTS:
            await store.add(f)
        print(f"  wrote {len(FACTS)} archival facts (embedded on add)")

        # 3. wait for Atlas to build + make the index queryable.
        queryable = await _wait_queryable(collection, settings.semantic_vector_index)
        print(f"  index queryable: {queryable}")
        if not queryable:
            raise SystemExit("vector index did not become queryable in time")

        # 4. recall by similarity — two different intents, expect different top hits.
        q1 = "how long do the medium compound tyres last before dropping off?"
        hits1 = await store.recall_archival(q1, user_id=USER, scope_topics=SCOPE, limit=3)
        top1 = hits1[0].subject if hits1 else None
        print(f"  query 1: {q1!r}")
        print(f"    -> {[h.subject for h in hits1]}  (top={top1})")

        q2 = "what happens to the race order when the safety car comes out?"
        hits2 = await store.recall_archival(q2, user_id=USER, scope_topics=SCOPE, limit=3)
        top2 = hits2[0].subject if hits2 else None
        print(f"  query 2: {q2!r}")
        print(f"    -> {[h.subject for h in hits2]}  (top={top2})")

        ok = top1 == "medium tyres" and top2 == "the safety car"
        print(f"  GAP #2 {'PASSED' if ok else 'FAILED'} "
              f"(vector ranking distinguishes intents: {ok})")
    finally:
        deleted = await collection.delete_many({"user_id": USER})
        print(f"  cleanup: deleted {deleted.deleted_count} test facts")
        await cold.close()

    if not ok:
        raise SystemExit("gap #2 live verification failed")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
