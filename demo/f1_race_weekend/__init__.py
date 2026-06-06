"""Formula 1 race-weekend reference demo (Monaco GP, fictional "Team Ezra").

A fleet of agents spawns dynamically across a race weekend and exercises every
Ezra differentiator in ten minutes: federation + dynamic spawn, permission
denial, single- and multi-agent contradiction (highest_trust + custom),
branching replay, and a flat-latency scaling proof.

The build uses a single parameterised prompt template with role-fill per agent
(``prompts/``) and data-driven role definitions (``agents/roles.py``) instead of
nine hand-written agent modules. ``race_weekend_demo.py`` is the deterministic
offline walkthrough (in-memory stores); ``adk_runtime/`` runs the real
``google.adk`` fleet against live backends, and ``data_ingestion.py`` pulls real
Jolpica/OpenF1/FastF1 data plus synthesised enterprise datasets.
"""
