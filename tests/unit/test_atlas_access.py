"""Unit tests for the Atlas egress bootstrap — the no-network decision paths.

The live API call is covered by manual smoke (it needs real Atlas creds); here we
assert the function disables cleanly and never raises when it can't act.
"""

from ezra_core.atlas_access import ensure_egress_allowed
from ezra_core.config import EzraSettings


def _settings(**kw) -> EzraSettings:
    base = dict(
        mongodb_public_key="", mongodb_private_key="", atlas_auto_allow_egress=True
    )
    base.update(kw)
    return EzraSettings(**base)


def test_disabled_returns_none():
    assert ensure_egress_allowed(_settings(atlas_auto_allow_egress=False)) is None


def test_no_api_keys_returns_none():
    assert ensure_egress_allowed(_settings()) is None


def test_only_public_key_returns_none():
    assert ensure_egress_allowed(_settings(mongodb_public_key="pub")) is None
