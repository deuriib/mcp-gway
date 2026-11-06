"""Hermetic end-to-end OAuth flow against a stateful fake authorization server."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import socket
import stat
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from mcp.shared.auth import OAuthToken

from mcp_gway import models as M
from mcp_gway import oauth as O

_MCP = "https://mcp.test/mcp"
_PRM = "https://auth.test/prm"
_AUTH = "https://auth.test"
_RESOURCE = "https://mcp.test/mcp"
_AUTH_ENDPOINT = f"{_AUTH}/oauth/auth?{urlencode({'resource': _RESOURCE})}"
_CLIENT_ID = "rlwy_oaci_integration"
_CLIENT_SECRET = "integration-secret"
_FLOW_TIMEOUT = 5

_TOKEN_PAYLOAD = {
    "access_token": "access-token-123",
    "token_type": "Bearer",
    "expires_in": 3600,
    "refresh_token": "refresh-token-123",
    "scope": "workspace:member offline_access",
}


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = str(self._payload)

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeAuthorizationServer:
    def __init__(self) -> None:
        prm = {
            "resource": _RESOURCE,
            "authorization_servers": [_AUTH],
            "scopes_supported": ["workspace:member"],
        }
        self.docs = {
            _MCP: FakeResponse(
                401, {}, {"www-authenticate": f'Bearer resource_metadata="{_PRM}"'}
            ),
            _PRM: FakeResponse(200, prm),
            "https://mcp.test/.well-known/oauth-protected-resource/mcp": FakeResponse(
                200, prm
            ),
            "https://mcp.test/.well-known/oauth-protected-resource": FakeResponse(
                200, prm
            ),
            f"{_AUTH}/.well-known/oauth-authorization-server": FakeResponse(
                200,
                {
                    "authorization_endpoint": _AUTH_ENDPOINT,
                    "token_endpoint": f"{_AUTH}/oauth/token",
                    "scopes_supported": ["workspace:member", "offline_access"],
                },
            ),
        }
        self.get_calls: list[str] = []
        self.token_calls: list[dict[str, str]] = []
        self.refresh_calls: list[dict[str, str]] = []
        self.registration_calls: list[dict[str, Any]] = []
        self.messages: list[str] = []
        self.authorize_url: str | None = None
        self.authorize_challenge: str | None = None
        self.delivery_tasks: list[asyncio.Task[None]] = []
        self.delivery_errors: list[Exception] = []
        self.token_file_at_open: bool | None = None
        self.token_payload = dict(_TOKEN_PAYLOAD)
        self.refresh_payload = {
            "access_token": "refreshed-token-123",
            "token_type": "Bearer",
            "expires_in": 7200,
            "refresh_token": "refresh-token-2",
            "scope": "workspace:member offline_access",
        }
        self.refresh_status = 200

    async def get(self, url: str, *, headers: dict[str, str] | None = None):
        self.get_calls.append(url)
        return self.docs.get(url, FakeResponse(404))

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
    ):
        if url == f"{_AUTH}/oauth/register":
            self.registration_calls.append(json or {})
            return FakeResponse(201, {"client_id": "should-not-be-used"})
        if url != f"{_AUTH}/oauth/token":
            return FakeResponse(404)
        form = data or {}
        if form.get("grant_type") == "refresh_token":
            self.refresh_calls.append(form)
            if self.refresh_status != 200:
                return FakeResponse(
                    self.refresh_status,
                    {"error": "invalid_grant", "error_description": "refresh expired"},
                )
            return FakeResponse(200, dict(self.refresh_payload))
        self.token_calls.append(form)
        self._verify_pkce(form)
        return FakeResponse(200, dict(self.token_payload))

    def _verify_pkce(self, form: dict[str, str]) -> None:
        digest = hashlib.sha256(form["code_verifier"].encode()).digest()
        challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
        assert challenge == self.authorize_challenge


async def _deliver_callback(url: str, server: FakeAuthorizationServer) -> None:
    parsed = urlparse(url)
    target = f"{parsed.path}?{parsed.query}"

    def _get() -> None:
        # Raw socket: the hermetic DNS stub rewrites getaddrinfo, which would
        # send http.client to port 0 instead of the loopback callback port.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(2)
            sock.connect((parsed.hostname, parsed.port))
            request = (
                f"GET {target} HTTP/1.1\r\n"
                f"Host: {parsed.hostname}:{parsed.port}\r\n"
                "Connection: close\r\n\r\n"
            )
            sock.sendall(request.encode())
            while sock.recv(65536):
                pass
        finally:
            sock.close()

    try:
        await asyncio.to_thread(_get)
    except Exception as exc:  # pragma: no cover - surfaced by the flow timeout
        server.delivery_errors.append(exc)


def _install(
    monkeypatch,
    tmp_path,
    server: FakeAuthorizationServer,
    *,
    callback_result: dict[str, str] | None = None,
) -> O.FileTokenStorage:
    storage = O.FileTokenStorage("integration", storage_dir=tmp_path)
    monkeypatch.setattr(O, "FileTokenStorage", lambda _name: storage)
    monkeypatch.setattr(M, "ssrf_get", server.get)
    monkeypatch.setattr(M, "ssrf_post", server.post)

    def open_browser(url: str) -> bool:
        server.authorize_url = url
        server.token_file_at_open = storage._token_file.exists()
        query = parse_qs(urlparse(url).query)
        server.authorize_challenge = query["code_challenge"][0]
        redirect_uri = query["redirect_uri"][0]
        if callback_result is None:
            callback_result_local = {
                "code": "auth-code-123",
                "state": query["state"][0],
            }
        else:
            callback_result_local = callback_result
        target = f"{redirect_uri}?{urlencode(callback_result_local)}"
        task = asyncio.get_running_loop().create_task(_deliver_callback(target, server))
        server.delivery_tasks.append(task)
        return True

    monkeypatch.setattr(O.webbrowser, "open", open_browser)
    return storage


async def _run(server: FakeAuthorizationServer, *, oauth_config: Any = None):
    return await asyncio.wait_for(
        O.run_oauth_flow(
            _MCP,
            "integration",
            callback_port=0,
            oauth_config=oauth_config,
            output_callback=server.messages.append,
        ),
        timeout=_FLOW_TIMEOUT,
    )


async def test_end_to_end_authorization_code_flow(tmp_path, monkeypatch):
    server = FakeAuthorizationServer()
    storage = _install(monkeypatch, tmp_path, server)
    client = await _run(server, oauth_config={"clientId": _CLIENT_ID})
    assert client is not None
    await client.aclose()

    query = parse_qs(urlparse(server.authorize_url).query)
    assert server.authorize_url.count("?") == 1
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["resource"] == [_RESOURCE]
    assert query["client_id"] == [_CLIENT_ID]
    assert query["scope"] == ["workspace:member offline_access"]

    assert len(server.token_calls) == 1
    exchange = server.token_calls[0]
    assert exchange["grant_type"] == "authorization_code"
    assert exchange["resource"] == _RESOURCE
    assert exchange["client_id"] == _CLIENT_ID
    assert server.registration_calls == []
    assert server.refresh_calls == []

    tokens = await storage.get_tokens()
    assert tokens is not None and tokens.access_token == "access-token-123"
    assert tokens.scope == "workspace:member offline_access"
    assert await storage.get_expires_at() is not None
    if os.name != "nt":
        assert stat.S_IMODE(storage._token_file.stat().st_mode) == 0o600


async def test_end_to_end_refresh_after_expiry(tmp_path, monkeypatch):
    server = FakeAuthorizationServer()
    storage = _install(monkeypatch, tmp_path, server)
    await storage.set_tokens(
        OAuthToken(
            access_token="old-token",
            token_type="Bearer",
            refresh_token="refresh-token-123",
            scope="workspace:member offline_access",
            expires_in=3600,
        ),
        expires_at=int(time.time()) - 10,
    )
    before = int(time.time())
    client = await _run(
        server,
        oauth_config={"clientId": _CLIENT_ID, "clientSecret": _CLIENT_SECRET},
    )
    assert client is not None
    await client.aclose()

    assert server.authorize_url is None
    assert server.token_calls == []
    assert len(server.refresh_calls) == 1
    refresh = server.refresh_calls[0]
    assert refresh["resource"] == _RESOURCE
    assert refresh["client_id"] == _CLIENT_ID
    assert refresh["client_secret"] == _CLIENT_SECRET

    tokens = await storage.get_tokens()
    assert tokens is not None and tokens.access_token == "refreshed-token-123"
    expires_at = await storage.get_expires_at()
    assert expires_at is not None and expires_at >= before + 7200


async def test_end_to_end_refresh_failure_falls_back(tmp_path, monkeypatch):
    server = FakeAuthorizationServer()
    server.refresh_status = 400
    storage = _install(monkeypatch, tmp_path, server)
    await storage.set_tokens(
        OAuthToken(
            access_token="old-token",
            token_type="Bearer",
            refresh_token="refresh-token-123",
            expires_in=3600,
        ),
        expires_at=int(time.time()) - 10,
    )
    client = await _run(server, oauth_config={"clientId": _CLIENT_ID})
    assert client is not None
    await client.aclose()

    assert len(server.refresh_calls) == 1
    assert server.authorize_url is not None
    assert server.token_file_at_open is False
    assert len(server.token_calls) == 1
    tokens = await storage.get_tokens()
    assert tokens is not None and tokens.access_token == "access-token-123"


async def test_end_to_end_callback_error_surfaced(tmp_path, monkeypatch):
    server = FakeAuthorizationServer()
    _install(
        monkeypatch,
        tmp_path,
        server,
        callback_result={
            "error": "invalid_request",
            "error_description": "missing required parameter 'response_type'",
        },
    )
    client = await _run(server, oauth_config={"clientId": _CLIENT_ID})
    assert client is None
    assert server.token_calls == []
    joined = "\n".join(server.messages)
    assert "invalid_request" in joined
    assert "missing required parameter 'response_type'" in joined


async def test_end_to_end_never_logs_secrets(tmp_path, monkeypatch):
    server = FakeAuthorizationServer()
    server.token_payload = {
        "access_token": "SECRET-ACCESS",
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": "SECRET-REFRESH",
        "scope": "workspace:member offline_access",
    }
    _install(monkeypatch, tmp_path, server)
    client = await _run(
        server,
        oauth_config={"clientId": _CLIENT_ID, "clientSecret": "SECRET-CLIENT"},
    )
    assert client is not None
    await client.aclose()
    joined = "\n".join(server.messages)
    assert "SECRET-ACCESS" not in joined
    assert "SECRET-REFRESH" not in joined
    assert "SECRET-CLIENT" not in joined
