"""Programmatic Atlas Network Access — allow the runtime's egress IP automatically.

Atlas rejects connections from IPs not on the project access list. On GCP (and any
dynamic-IP host) we can't hand-whitelist, so this calls the Atlas Admin API with the
project's API key pair to add the runtime's *current egress IP* (only that IP — not
``0.0.0.0/0``) to the access list before we connect. Idempotent: re-adding an
existing IP is treated as success.

Disabled cleanly when the API keys aren't configured, so local/dev (where the IP is
already whitelisted) and unit tests pay nothing.
"""

from __future__ import annotations

from typing import Optional

import httpx

from ezra_core.config import EzraSettings

_ATLAS_API = "https://cloud.mongodb.com/api/atlas/v2"
_ATLAS_ACCEPT = "application/vnd.atlas.2023-11-15+json"


def _detect_egress_ip(client: httpx.Client) -> str:
    return client.get("https://api.ipify.org", timeout=15).text.strip()


def _discover_project_id(client: httpx.Client, auth: httpx.DigestAuth) -> Optional[str]:
    resp = client.get(
        f"{_ATLAS_API}/groups", headers={"Accept": _ATLAS_ACCEPT}, auth=auth, timeout=30
    )
    if resp.status_code != 200:
        return None
    results = resp.json().get("results", [])
    return results[0]["id"] if results else None


def ensure_egress_allowed(settings: EzraSettings) -> Optional[str]:
    """Add the current egress IP to the Atlas access list. Returns the IP allowed,
    or ``None`` when disabled / not configured / unable to act (never raises —
    connectivity failures surface later at connect time with a clearer error)."""
    if not settings.atlas_auto_allow_egress:
        return None
    if not (settings.mongodb_public_key and settings.mongodb_private_key):
        return None

    auth = httpx.DigestAuth(settings.mongodb_public_key, settings.mongodb_private_key)
    try:
        with httpx.Client() as client:
            project_id = settings.mongodb_atlas_project_id or _discover_project_id(
                client, auth
            )
            if not project_id:
                return None
            ip = _detect_egress_ip(client)
            resp = client.post(
                f"{_ATLAS_API}/groups/{project_id}/accessList",
                headers={"Accept": _ATLAS_ACCEPT, "Content-Type": _ATLAS_ACCEPT},
                auth=auth,
                json=[{"ipAddress": ip, "comment": "ezra-auto-egress"}],
                timeout=30,
            )
            # 201 created; 409/duplicate means it's already allowed — both are fine.
            if resp.status_code < 400 or resp.status_code == 409:
                return ip
            if "DUPLICATE" in resp.text or "already" in resp.text.lower():
                return ip
            return None
    except Exception:
        # Best-effort: if the allowlist call fails, let the Mongo connect attempt
        # produce the actionable error instead of masking it here.
        return None
