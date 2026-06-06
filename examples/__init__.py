"""Runnable SDK examples for the Ezra platform.

Each module exposes ``async def run(ezra: Ezra) -> dict`` — the example logic,
written against the public SDK and agnostic to how ``Ezra`` was built — plus a
``__main__`` that runs it against an offline in-memory runtime so the example
works with no infrastructure:

    uv run python -m examples.basic_chat

To run an example against real backends (Atlas / Redis / Qdrant / Gemini),
build the runtime with ``Ezra.from_env()`` instead of the offline harness — the
``run(ezra)`` body is identical. See ``examples/_harness.py`` and the README.
"""
