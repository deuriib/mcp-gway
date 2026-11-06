"""R3: real (non-UUID) client IDs survive and DCR only runs when absent."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from mcp_gway import oauth as O
from mcp_gway.models import MCPServerConfig, OAuthConfig
from tests.helpers.oauth_flow_harness import install_flow

_MCP = "https://mcp.test/mcp"
_AUTH = "https://auth.test"


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


def _metadata(*, registration: bool) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "authorization_endpoint": f"{_AUTH}/oauth/auth",
        "token_endpoint": f"{_AUTH}/oauth/token",
    }
    if registration:
        metadata["registration_endpoint"] = f"{_AUTH}/oauth/register"
    return metadata


def _token_payload() -> dict[str, Any]:
    return {"access_token": "AT", "token_type": "Bearer", "expires_in": 3600}


def test_non_uuid_client_id_survives_oauth_config():
    assert OAuthConfig(clientId="rlwy_oaci_abc123").clientId == "rlwy_oaci_abc123"


def test_non_uuid_client_id_survives_server_config():
    cfg = MCPServerConfig(
        name="gh",
        type="remote",
        url="https://api.example.com/mcp",
        oauth={"clientId": "gh_abc", "scope": "repo"},
    )
    assert isinstance(cfg.oauth, OAuthConfig)
    assert cfg.oauth.clientId == "gh_abc"


def test_oauth_true_has_no_fabricated_client_id():
    cfg = MCPServerConfig(
        name="dcr", type="remote", url="https://api.example.com/mcp", oauth=True
    )
    assert isinstance(cfg.oauth, OAuthConfig)
    assert cfg.oauth.clientId is None
    assert cfg.oauth.clientSecret is None


def test_dict_without_client_id_stays_none():
    cfg = MCPServerConfig(
        name="scopeonly",
        type="remote",
        url="https://api.example.com/mcp",
        oauth={"scope": "x"},
    )
    assert isinstance(cfg.oauth, OAuthConfig)
    assert cfg.oauth.clientId is None


async def test_oauth_true_runs_dynamic_registration(tmp_path, monkeypatch):
    cfg = MCPServerConfig(
        name="dcrflow",
        type="remote",
        url="https://api.example.com/mcp",
        oauth=True,
    )
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "dcrflow",
        metadata=_metadata(registration=True),
        reg_payload={"client_id": "dcr-client"},
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP, "dcrflow", oauth_config=cfg.oauth, output_callback=lambda _m: None
    )
    assert out is not None
    await out.aclose()
    registration = [p for p in captured["posts"] if p["url"].endswith("/register")]
    assert len(registration) == 1
    assert _query(captured["auth_url"])["client_id"] == ["dcr-client"]
    exchange = [
        p
        for p in captured["posts"]
        if p["data"] and p["data"].get("grant_type") == "authorization_code"
    ]
    assert exchange[0]["data"]["client_id"] == "dcr-client"


async def test_manual_mode_uses_configured_non_uuid_client_id_without_dcr(
    tmp_path, monkeypatch
):
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "manualflow",
        metadata=_metadata(registration=True),
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP,
        "manualflow",
        oauth_config={"clientId": "rlwy_oaci_abc123", "clientSecret": "s3cret"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert [p for p in captured["posts"] if p["url"].endswith("/register")] == []
    assert _query(captured["auth_url"])["client_id"] == ["rlwy_oaci_abc123"]
    exchange = captured["posts"][0]["data"]
    assert exchange["client_id"] == "rlwy_oaci_abc123"
    assert exchange["client_secret"] == "s3cret"


async def test_malformed_dcr_201_returns_none(tmp_path, monkeypatch):
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "baddcr",
        metadata=_metadata(registration=True),
        reg_payload={"client_id": "dcr-client", "redirect_uris": ["not a url"]},
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP, "baddcr", oauth_config=OAuthConfig(), output_callback=lambda _m: None
    )
    assert out is None
    assert captured["auth_url"] is None


async def test_no_client_id_and_no_dcr_fails_loudly(tmp_path, monkeypatch):
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "noclient",
        metadata=_metadata(registration=False),
        token_payload=_token_payload(),
    )
    messages: list[str] = []
    out = await O.run_oauth_flow(
        _MCP, "noclient", oauth_config=OAuthConfig(), output_callback=messages.append
    )
    assert out is None
    assert captured["auth_url"] is None
    assert captured["posts"] == []
    assert any("no client_id configured" in m for m in messages)
