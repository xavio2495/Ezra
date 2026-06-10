"""Run the conductor: ``python -m demo.conductor`` (offline by default).

Set ``EZRA_CONDUCTOR_LIVE=1`` to wire the real runtime (``Ezra.from_env`` —
Atlas/Redis/Qdrant/Vertex; the GKE deployment path).
"""

import os

import uvicorn

from demo.conductor.app import create_app


def main() -> None:
    if os.getenv("EZRA_CONDUCTOR_LIVE", "").lower() in ("1", "true", "yes"):
        from ezra_core.runtime import Ezra, gemini_checker

        ezra = Ezra.from_env(build_checker=False)
        ezra.checker = gemini_checker(ezra.settings)
        app = create_app(ezra, offline=False)
    else:
        app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8090")))


if __name__ == "__main__":
    main()
