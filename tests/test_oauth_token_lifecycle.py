"""R4: persisted expiry, refresh, carry-forward, and code-flow fallback."""

from __future__ import annotations

import json
import os
import stat
import time
from typing import Any
from unittest.mock import AsyncMock

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from mcp_gway import oauth as O
from tests.helpers.oauth_flow_harness import install_flow

_MCP = "https://mcp.test/mcp"
_AUTH = "https://auth.test"
_CALLBACK = "http://127.0.0.1:8989/callback"


def _metadata(
    *, registration: bool = False, resource: str | None = _MCP
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "authorization_endpoint": f"{_AUTH}/oauth/auth",
        "token_endpoint": f"{_AUTH}/oauth/token",
        "scopes_supported": ["workspace:member", "offline_access"],
    }
    if resource is not None:
        metadata["resource"] = resource
    if registration:
        metadata["registration_endpoint"] = f"{_AUTH}/oauth/register"
    return metadata


def _token_payload(access: str = "NEW-AT") -> dict[str, Any]:
    return {"access_token": access, "token_type": "Bearer", "expires_in": 3600}


async def _seed(
    storage: O.FileTokenStorage,
    *,
    access_token: str = "OLD-AT",
    refresh_token: str | None = None,
    scope: str | None = None,
    expires_in: int | None = None,
    expires_at: int | None = None,
) -> None:
    await storage.set_tokens(
        OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            refresh_token=refresh_token,
            scope=scope,
            expires_in=expires_in,
        ),
        expires_at=expires_at,
    )


async def test_expires_at_persisted_with_token(tmp_path):
    storage = O.FileTokenStorage("expiry", storage_dir=tmp_path)
    expires_at = int(time.time()) + 3600
    await _seed(storage, expires_at=expires_at)
    data = json.loads(storage._token_file.read_text(encoding="utf-8"))
    assert data["expires_at"] == expires_at
    assert await storage.get_expires_at() == expires_at
    if os.name != "nt":
        assert stat.S_IMODE(storage._token_file.stat().st_mode) == 0o600


async def test_expires_at_survives_new_storage_instance(tmp_path):
    await _seed(
        O.FileTokenStorage("restart", storage_dir=tmp_path),
        expires_at=int(time.time()) + 3600,
    )
    reopened = O.FileTokenStorage("restart", storage_dir=tmp_path)
    assert await reopened.get_expires_at() is not None


async def test_set_tokens_without_expiry_removes_old_key(tmp_path):
    storage = O.FileTokenStorage("clearexp", storage_dir=tmp_path)
    await _seed(storage, expires_at=int(time.time()) + 60)
    await storage.set_tokens(OAuthToken(access_token="NEW", token_type="Bearer"))
    data = json.loads(storage._token_file.read_text(encoding="utf-8"))
    assert "expires_at" not in data
    assert await storage.get_expires_at() is None


async def test_get_expires_at_corrupt_file_returns_none(tmp_path):
    storage = O.FileTokenStorage("corrupt", storage_dir=tmp_path)
    storage._token_file.write_text("not-json", encoding="utf-8")
    assert await storage.get_expires_at() is None


async def test_valid_stored_token_reused_without_network(tmp_path, monkeypatch):
    storage, captured = install_flow(
        monkeypatch, tmp_path, "validtok", metadata=_metadata()
    )
    await _seed(storage, expires_at=int(time.time()) + 3600)
    discover = AsyncMock(return_value=_metadata())
    monkeypatch.setattr(O, "discover_oauth_metadata", discover)
    out = await O.run_oauth_flow(_MCP, "validtok", output_callback=lambda _m: None)
    assert out is not None
    await out.aclose()
    assert discover.await_count == 0
    assert captured["posts"] == []


async def test_legacy_token_without_expires_at_reused(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch, tmp_path, "legacytok", metadata=_metadata()
    )
    storage._token_file.write_text(
        json.dumps({"access_token": "LEGACY"}), encoding="utf-8"
    )
    discover = AsyncMock(return_value=_metadata())
    monkeypatch.setattr(O, "discover_oauth_metadata", discover)
    out = await O.run_oauth_flow(_MCP, "legacytok", output_callback=lambda _m: None)
    assert out is not None
    await out.aclose()
    assert discover.await_count == 0


async def test_corrupt_expires_at_keeps_token_valid(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch, tmp_path, "corruptexp", metadata=_metadata()
    )
    storage._token_file.write_text(
        json.dumps({"access_token": "LEGACY", "expires_at": "not-a-number"}),
        encoding="utf-8",
    )
    discover = AsyncMock(return_value=_metadata())
    monkeypatch.setattr(O, "discover_oauth_metadata", discover)
    out = await O.run_oauth_flow(_MCP, "corruptexp", output_callback=lambda _m: None)
    assert out is not None
    await out.aclose()
    assert discover.await_count == 0


async def test_expired_token_not_reused(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch, tmp_path, "expiredtok", metadata=_metadata()
    )
    await _seed(storage, expires_at=int(time.time()) - 10)
    discover = AsyncMock(return_value=None)
    monkeypatch.setattr(O, "discover_oauth_metadata", discover)
    messages: list[str] = []
    out = await O.run_oauth_flow(_MCP, "expiredtok", output_callback=messages.append)
    assert out is None
    assert discover.await_count == 1
    assert any("Could not discover" in m for m in messages)


async def test_expired_token_with_refresh_token_refreshes_and_persists(
    tmp_path, monkeypatch
):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "refreshok",
        metadata=_metadata(),
        refresh_payload={
            "access_token": "NEW-AT",
            "token_type": "Bearer",
            "expires_in": 7200,
            "refresh_token": "RT2",
            "scope": "workspace:member",
        },
    )
    await _seed(
        storage,
        refresh_token="RT1",
        scope="workspace:member",
        expires_in=3600,
        expires_at=int(time.time()) - 10,
    )
    before = int(time.time())
    out = await O.run_oauth_flow(
        _MCP,
        "refreshok",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert captured["auth_url"] is None
    assert captured["started"] is False
    assert len(captured["posts"]) == 1
    assert captured["posts"][0]["data"]["grant_type"] == "refresh_token"
    tokens = await storage.get_tokens()
    assert tokens is not None and tokens.access_token == "NEW-AT"
    assert tokens.refresh_token == "RT2"
    expires_at = await storage.get_expires_at()
    assert expires_at is not None and expires_at >= before + 7200


async def test_refresh_sends_resource_and_client_auth(tmp_path, monkeypatch):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "refreshdata",
        metadata=_metadata(),
        refresh_payload=_token_payload(),
    )
    await _seed(storage, refresh_token="RT1", expires_at=int(time.time()) - 10)
    out = await O.run_oauth_flow(
        _MCP,
        "refreshdata",
        oauth_config={"clientId": "cfg-client", "clientSecret": "cfg-secret"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    data = captured["posts"][0]["data"]
    assert data["resource"] == _MCP
    assert data["client_id"] == "cfg-client"
    assert data["client_secret"] == "cfg-secret"
    assert "scope" not in data


async def test_refresh_public_client_sends_client_id_without_secret(
    tmp_path, monkeypatch
):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "refreshpublic",
        metadata=_metadata(),
        refresh_payload=_token_payload(),
    )
    await _seed(storage, refresh_token="RT1", expires_at=int(time.time()) - 10)
    out = await O.run_oauth_flow(
        _MCP,
        "refreshpublic",
        oauth_config={"clientId": "public-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    data = captured["posts"][0]["data"]
    assert data["client_id"] == "public-client"
    assert "client_secret" not in data


async def test_refresh_carries_forward_missing_refresh_token_and_scope(
    tmp_path, monkeypatch
):
    storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "refreshcarry",
        metadata=_metadata(),
        refresh_payload={
            "access_token": "NEW-AT",
            "token_type": "Bearer",
            "expires_in": 60,
        },
    )
    await _seed(
        storage,
        refresh_token="RT1",
        scope="workspace:member",
        expires_in=3600,
        expires_at=int(time.time()) - 10,
    )
    out = await O.run_oauth_flow(
        _MCP,
        "refreshcarry",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    tokens = await storage.get_tokens()
    assert tokens is not None
    assert tokens.refresh_token == "RT1"
    assert tokens.scope == "workspace:member"


async def test_refresh_omits_expires_in_uses_previous_lifetime(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "refreshlife",
        metadata=_metadata(),
        refresh_payload={"access_token": "NEW-AT", "token_type": "Bearer"},
    )
    await _seed(
        storage,
        refresh_token="RT1",
        expires_in=3600,
        expires_at=int(time.time()) - 10,
    )
    before = int(time.time())
    out = await O.run_oauth_flow(
        _MCP,
        "refreshlife",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    expires_at = await storage.get_expires_at()
    assert expires_at is not None and expires_at >= before + 3600


async def test_refresh_200_without_access_token_falls_back(tmp_path, monkeypatch):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "refreshnoat",
        metadata=_metadata(),
        refresh_payload={"token_type": "Bearer"},
        token_payload=_token_payload("CODE-AT"),
    )
    await _seed(storage, refresh_token="RT1", expires_at=int(time.time()) - 10)
    out = await O.run_oauth_flow(
        _MCP,
        "refreshnoat",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    grants = [p["data"]["grant_type"] for p in captured["posts"]]
    assert grants == ["refresh_token", "authorization_code"]
    assert captured["auth_url"] is not None
    tokens = await storage.get_tokens()
    assert tokens is not None and tokens.access_token == "CODE-AT"


async def test_refresh_failure_discards_token_and_runs_code_flow(tmp_path, monkeypatch):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "refreshfail",
        metadata=_metadata(),
        refresh_status=400,
        token_payload=_token_payload("CODE-AT"),
    )
    await _seed(storage, refresh_token="RT1", expires_at=int(time.time()) - 10)
    out = await O.run_oauth_flow(
        _MCP,
        "refreshfail",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert captured["posts"][0]["data"]["grant_type"] == "refresh_token"
    assert captured["auth_url"] is not None
    assert captured["token_file_at_open"] is False
    tokens = await storage.get_tokens()
    assert tokens is not None and tokens.access_token == "CODE-AT"


async def test_expired_token_without_refresh_token_uses_code_flow(
    tmp_path, monkeypatch
):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "norefresh",
        metadata=_metadata(),
        token_payload=_token_payload("CODE-AT"),
    )
    await _seed(storage, expires_at=int(time.time()) - 10)
    out = await O.run_oauth_flow(
        _MCP,
        "norefresh",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    assert [p["data"]["grant_type"] for p in captured["posts"]] == [
        "authorization_code"
    ]
    assert captured["auth_url"] is not None
    assert captured["token_file_at_open"] is False


async def test_persisted_client_info_reused_for_reauth(tmp_path, monkeypatch):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "reuseclient",
        metadata=_metadata(registration=True),
        token_payload=_token_payload(),
    )
    await storage.set_client_info(
        OAuthClientInformationFull(
            client_id="persisted-client",
            client_secret="persisted-secret",
            redirect_uris=[_CALLBACK],
        )
    )
    out = await O.run_oauth_flow(_MCP, "reuseclient", output_callback=lambda _m: None)
    assert out is not None
    await out.aclose()
    assert [p for p in captured["posts"] if p["url"].endswith("/register")] == []
    exchange = captured["posts"][0]["data"]
    assert exchange["client_id"] == "persisted-client"
    assert exchange["client_secret"] == "persisted-secret"


async def test_persisted_client_redirect_mismatch_runs_dcr(tmp_path, monkeypatch):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "staleclient",
        metadata=_metadata(registration=True),
        reg_payload={"client_id": "dcr-client"},
        token_payload=_token_payload(),
    )
    await storage.set_client_info(
        OAuthClientInformationFull(
            client_id="stale-client",
            redirect_uris=["http://127.0.0.1:1111/callback"],
        )
    )
    out = await O.run_oauth_flow(_MCP, "staleclient", output_callback=lambda _m: None)
    assert out is not None
    await out.aclose()
    assert len([p for p in captured["posts"] if p["url"].endswith("/register")]) == 1
    exchange = [
        p
        for p in captured["posts"]
        if p["data"] and p["data"].get("grant_type") == "authorization_code"
    ]
    assert exchange[0]["data"]["client_id"] == "dcr-client"


async def test_failed_fallback_leaves_no_stale_token(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "failall",
        metadata=_metadata(),
        token_status=400,
    )
    await _seed(storage, expires_at=int(time.time()) - 10)
    out = await O.run_oauth_flow(
        _MCP,
        "failall",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is None
    assert not storage._token_file.exists()


async def test_clear_tokens_keeps_client_info(tmp_path):
    storage = O.FileTokenStorage("clearonly", storage_dir=tmp_path)
    await storage.set_client_info(
        OAuthClientInformationFull(client_id="keep-me", redirect_uris=[_CALLBACK])
    )
    await _seed(storage, expires_at=int(time.time()) + 60)
    await storage.clear_tokens()
    assert await storage.get_tokens() is None
    info = await storage.get_client_info()
    assert info is not None and info.client_id == "keep-me"


async def test_code_exchange_200_without_access_token_is_failure(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "noatcode",
        metadata=_metadata(),
        token_payload={"token_type": "Bearer", "expires_in": 3600},
    )
    out = await O.run_oauth_flow(
        _MCP,
        "noatcode",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is None
    assert not storage._token_file.exists()


async def test_code_exchange_persists_expires_at_flow_level(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "flowexpiry",
        metadata=_metadata(),
        token_payload={
            "access_token": "AT",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    before = int(time.time())
    out = await O.run_oauth_flow(
        _MCP,
        "flowexpiry",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is not None
    await out.aclose()
    expires_at = await storage.get_expires_at()
    assert expires_at is not None and expires_at >= before + 3600
    if os.name != "nt":
        assert stat.S_IMODE(storage._token_file.stat().st_mode) == 0o600


async def test_code_exchange_malformed_200_returns_none(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "badcode200",
        metadata=_metadata(),
        token_payload={
            "access_token": "AT",
            "token_type": "Bearer",
            "expires_in": "not-a-number",
        },
    )
    out = await O.run_oauth_flow(
        _MCP,
        "badcode200",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is None
    assert not storage._token_file.exists()


async def test_refresh_malformed_200_returns_none(tmp_path, monkeypatch):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "badrefresh200",
        metadata=_metadata(),
        refresh_payload={
            "access_token": "NEW-AT",
            "token_type": "Bearer",
            "expires_in": "not-a-number",
        },
        token_status=400,
    )
    await _seed(storage, refresh_token="RT1", expires_at=int(time.time()) - 10)
    out = await O.run_oauth_flow(
        _MCP,
        "badrefresh200",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is None
    assert captured["posts"][0]["data"]["grant_type"] == "refresh_token"
    assert not storage._token_file.exists()


async def test_token_persistence_failure_returns_none(tmp_path, monkeypatch):
    storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "persistfail",
        metadata=_metadata(),
        token_payload=_token_payload("AT"),
    )

    async def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(storage, "set_tokens", boom)
    out = await O.run_oauth_flow(
        _MCP,
        "persistfail",
        oauth_config={"clientId": "cfg-client"},
        output_callback=lambda _m: None,
    )
    assert out is None


async def test_refresh_uses_persisted_client_info(tmp_path, monkeypatch):
    storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "persistrefresh",
        metadata=_metadata(registration=True),
        refresh_payload={
            "access_token": "NEW-AT",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )
    await storage.set_client_info(
        OAuthClientInformationFull(
            client_id="persisted-client",
            client_secret="persisted-secret",
            redirect_uris=[_CALLBACK],
        )
    )
    await _seed(storage, refresh_token="RT1", expires_at=int(time.time()) - 10)
    out = await O.run_oauth_flow(
        _MCP, "persistrefresh", output_callback=lambda _m: None
    )
    assert out is not None
    await out.aclose()
    assert captured["auth_url"] is None
    assert len(captured["posts"]) == 1
    data = captured["posts"][0]["data"]
    assert data["grant_type"] == "refresh_token"
    assert data["client_id"] == "persisted-client"
    assert data["client_secret"] == "persisted-secret"


async def test_token_value_never_logged(tmp_path, monkeypatch):
    _storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "nosecretlog",
        metadata=_metadata(),
        token_payload={
            "access_token": "SECRET-ACCESS",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "SECRET-REFRESH",
        },
    )
    messages: list[str] = []
    out = await O.run_oauth_flow(
        _MCP,
        "nosecretlog",
        oauth_config={"clientId": "cfg-client", "clientSecret": "SECRET-CLIENT"},
        output_callback=messages.append,
    )
    assert out is not None
    await out.aclose()
    joined = "\n".join(messages)
    assert "SECRET-ACCESS" not in joined
    assert "SECRET-REFRESH" not in joined
    assert "SECRET-CLIENT" not in joined
