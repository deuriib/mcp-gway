"""R2: PRM resource/scopes discovery, scope precedence, resource consistency."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from mcp_gway import models as M
from mcp_gway import oauth as O
from mcp_gway.oauth import resolve_scope
from tests.helpers.oauth_flow_harness import FakeResponse, install_flow

_MCP = "https://mcp.test/mcp"
_AUTH = "https://auth.test"


def _query(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).query)


def _discovery_docs(
    *, prm_resource: str | None, prm_scopes: list[str], as_scopes: list[str]
) -> dict[str, FakeResponse]:
    prm: dict[str, Any] = {"authorization_servers": [_AUTH]}
    if prm_resource is not None:
        prm["resource"] = prm_resource
    if prm_scopes:
        prm["scopes_supported"] = prm_scopes
    return {
        _MCP: FakeResponse(
            401,
            {},
            {"www-authenticate": f'Bearer resource_metadata="{_AUTH}/prm"'},
        ),
        f"{_AUTH}/prm": FakeResponse(200, prm),
        f"{_AUTH}/.well-known/oauth-authorization-server": FakeResponse(
            200,
            {
                "authorization_endpoint": f"{_AUTH}/oauth/auth",
                "token_endpoint": f"{_AUTH}/oauth/token",
                "scopes_supported": as_scopes,
            },
        ),
    }


async def test_discovery_returns_prm_resource_and_scopes(monkeypatch):
    docs = _discovery_docs(
        prm_resource=_MCP,
        prm_scopes=["workspace:member"],
        as_scopes=["workspace:member", "offline_access"],
    )

    async def fake_get(url, *, headers=None):
        return docs.get(url, FakeResponse(404))

    monkeypatch.setattr(M, "ssrf_get", fake_get)
    metadata = await O.discover_oauth_metadata(_MCP)
    assert metadata is not None
    assert metadata["resource"] == _MCP
    assert metadata["prm_scopes_supported"] == ["workspace:member"]


async def test_discovery_keeps_as_scopes_separate_from_prm(monkeypatch):
    docs = _discovery_docs(
        prm_resource=_MCP,
        prm_scopes=["workspace:member"],
        as_scopes=["workspace:member", "offline_access"],
    )

    async def fake_get(url, *, headers=None):
        return docs.get(url, FakeResponse(404))

    monkeypatch.setattr(M, "ssrf_get", fake_get)
    metadata = await O.discover_oauth_metadata(_MCP)
    assert metadata is not None
    assert metadata["scopes_supported"] == ["workspace:member", "offline_access"]
    assert metadata["prm_scopes_supported"] == ["workspace:member"]


def test_offline_access_membership_is_token_exact():
    scope = resolve_scope(
        configured=None,
        client_metadata_scope=None,
        prm_scopes=["not_offline_access"],
        as_scopes=["offline_access"],
    )
    assert scope == "not_offline_access offline_access"
    assert "not_offline_access" in scope.split()


def test_scope_precedence_configured_then_metadata_then_prm():
    assert (
        resolve_scope(
            configured="openid profile",
            client_metadata_scope="meta",
            prm_scopes=["prm"],
            as_scopes=None,
        )
        == "openid profile"
    )
    assert (
        resolve_scope(
            configured="   ",
            client_metadata_scope="meta",
            prm_scopes=["prm"],
            as_scopes=None,
        )
        == "meta"
    )
    assert (
        resolve_scope(
            configured=None,
            client_metadata_scope=None,
            prm_scopes=["workspace:member", "other"],
            as_scopes=None,
        )
        == "workspace:member other"
    )
    assert (
        resolve_scope(
            configured=None,
            client_metadata_scope=None,
            prm_scopes=None,
            as_scopes=None,
        )
        == "openid profile email"
    )


def _metadata(
    *, auth_endpoint: str = f"{_AUTH}/oauth/auth", resource: str = _MCP
) -> dict[str, Any]:
    return {
        "authorization_endpoint": auth_endpoint,
        "token_endpoint": f"{_AUTH}/oauth/token",
        "scopes_supported": ["workspace:member", "offline_access"],
        "resource": resource,
        "prm_scopes_supported": ["workspace:member"],
    }


def _token_payload() -> dict[str, Any]:
    return {"access_token": "AT", "token_type": "Bearer", "expires_in": 3600}


async def test_prm_scopes_requested(tmp_path, monkeypatch):
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "scope_prm",
        metadata=_metadata(),
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP,
        "scope_prm",
        oauth_config={"clientId": "test-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert "workspace:member" in _query(captured["auth_url"])["scope"][0]


async def test_offline_access_added_when_advertised(tmp_path, monkeypatch):
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "scope_offline",
        metadata=_metadata(),
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP,
        "scope_offline",
        oauth_config={"clientId": "test-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert _query(captured["auth_url"])["scope"] == ["workspace:member offline_access"]


async def test_offline_access_not_added_when_not_advertised(tmp_path, monkeypatch):
    metadata = _metadata()
    metadata["scopes_supported"] = ["workspace:member"]
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "scope_no_offline",
        metadata=metadata,
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP,
        "scope_no_offline",
        oauth_config={"clientId": "test-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert _query(captured["auth_url"])["scope"] == ["workspace:member"]


async def test_configured_scope_wins_over_prm(tmp_path, monkeypatch):
    metadata = _metadata()
    metadata["scopes_supported"] = ["workspace:member"]
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "scope_cfg",
        metadata=metadata,
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP,
        "scope_cfg",
        oauth_config={"clientId": "test-client", "scope": "openid profile"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert _query(captured["auth_url"])["scope"] == ["openid profile"]


async def test_resource_sent_in_authorize_and_token_requests(tmp_path, monkeypatch):
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "resource_both",
        metadata=_metadata(),
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP,
        "resource_both",
        oauth_config={"clientId": "test-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert _query(captured["auth_url"])["resource"] == [_MCP]
    exchange = captured["posts"][0]["data"]
    assert exchange["resource"] == _MCP


async def test_resource_not_duplicated_when_endpoint_has_it(tmp_path, monkeypatch):
    endpoint_resource = "https://mcp.test/other"
    endpoint = f"{_AUTH}/oauth/auth?{urlencode({'resource': endpoint_resource})}"
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "resource_endpoint",
        metadata=_metadata(auth_endpoint=endpoint, resource=_MCP),
        token_payload=_token_payload(),
    )
    out = await O.run_oauth_flow(
        _MCP,
        "resource_endpoint",
        oauth_config={"clientId": "test-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    query = _query(captured["auth_url"])
    assert query["resource"] == [endpoint_resource]
    assert captured["posts"][0]["data"]["resource"] == endpoint_resource
