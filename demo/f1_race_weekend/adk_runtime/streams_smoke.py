"""Live smoke for spec-gap #3 (protocol layer): the ``AtlasStreamsConnector`` /
``McpHttpInvoker`` JSON-RPC ``tools/call`` handshake against a REAL MongoDB MCP
server.

Calls the read-only ``atlas-streams-discover`` (``list-workspaces``) — no Stream
Processing Instance required. The proof is a clean Streamable-HTTP round-trip:
``initialize`` -> ``Mcp-Session-Id`` -> ``notifications/initialized`` ->
``tools/call`` -> the Atlas API, all through the connector's real client. The
workspace list is expected to be empty (no SPI provisioned); a non-error JSON-RPC
result is the pass.
"""

from __future__ import annotations

import asyncio
import os

from ezra_core.mesh.atlas_streams import (
    AtlasStreamsConnector,
    McpHttpInvoker,
    _extract_docs,
)


async def _try(url: str, project_id: str | None):
    conn = AtlasStreamsConnector(
        McpHttpInvoker(url),
        workspace="(none)",
        processor="(none)",
        project_id=project_id,
        topics=["telemetry"],
    )
    return await conn.list_workspaces()


async def _main() -> None:  # pragma: no cover — GKE Job entrypoint
    base = os.environ.get("EZRA_MONGODB_MCP_URL", "http://ezra-mcp:3000").rstrip("/")
    project_id = os.environ.get("EZRA_MONGODB_ATLAS_PROJECT_ID") or None
    # mongodb-mcp-server's Streamable-HTTP endpoint path varies by version — try
    # both the conventional /mcp and the root.
    candidates = (
        [base, base[:-4].rstrip("/")] if base.endswith("/mcp") else [base + "/mcp", base]
    )
    print(f"=== gap #3 live (protocol): MCP tools/call handshake; base={base} ===")
    print(f"  project_id: {project_id}")

    last_err: Exception | None = None
    for url in candidates:
        print(f"  trying {url} ...")
        try:
            payload = await _try(url, project_id)
            docs = _extract_docs(payload)
            keys = list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__
            print(f"  OK via {url}")
            print(f"  result shape    : {keys}")
            print(f"  workspaces      : {docs}")
            print("  GAP #3 (protocol) PASSED — initialize + session + tools/call round-tripped")
            return
        except Exception as exc:  # noqa: BLE001 — try the next candidate path
            last_err = exc
            print(f"  failed on {url}: {type(exc).__name__}: {str(exc)[:240]}")

    raise SystemExit(f"all MCP endpoints failed; last error: {last_err}")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(_main())
