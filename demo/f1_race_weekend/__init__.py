"""Formula 1 race-weekend reference demo (Monaco GP, fictional "Team Ezra").

A fleet of agents spawns dynamically across a race weekend and exercises every
Ezra differentiator in ten minutes: federation + dynamic spawn, permission
denial, single- and multi-agent contradiction (highest_trust + custom),
branching replay, and a flat-latency scaling proof.

Compressed-scope build (HANDOFF Session 5, 1.5-day cap): a single parameterised
prompt template with role-fill per agent (``prompts/``), data-driven role
definitions (``agents/roles.py``) instead of nine hand-written agent modules,
synthesised datasets + fixtures (live Jolpica/OpenF1/FastF1 ingestion deferred),
and fast-forward orchestration that runs fully offline on in-memory stores.
"""
