"""Hermetic harness for `run_oauth_flow` tests (no network, no browser)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlparse

from mcp_gway import models as M
from mcp_gway import oauth as O


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


def echo_state(auth_url: str) -> dict[str, str]:
    query = parse_qs(urlparse(auth_url).query)
    return {"code": "authcode123", "state": query.get("state", [""])[0]}


def install_flow(
    monkeypatch,
    tmp_path,
    name: str,
    *,
    metadata: dict[str, Any],
    token_payload: dict[str, Any] | None = None,
    token_status: int = 200,
    refresh_payload: dict[str, Any] | None = None,
    refresh_status: int = 200,
    reg_payload: dict[str, Any] | None = None,
    reg_status: int = 201,
    deliver=None,
):
    """Patch the flow's collaborators and return (storage, captured)."""
    storage = O.FileTokenStorage(name, storage_dir=tmp_path)
    monkeypatch.setattr(O, "FileTokenStorage", lambda _name: storage)
    monkeypatch.setattr(O, "discover_oauth_metadata", AsyncMock(return_value=metadata))
    captured: dict[str, Any] = {
        "auth_url": None,
        "posts": [],
        "started": False,
        "closed": False,
        "callback_url": None,
        "token_file_at_open": None,
    }

    def fake_open(url: str) -> bool:
        captured["auth_url"] = url
        captured["token_file_at_open"] = storage._token_file.exists()
        return True

    monkeypatch.setattr(O.webbrowser, "open", fake_open)

    class FakeCallbackServer:
        def __init__(self, port: int = 8989) -> None:
            self._port = port
            self.callback_url = f"http://127.0.0.1:{port}/callback"
            captured["callback_url"] = self.callback_url

        async def start(self) -> None:
            captured["started"] = True

        async def wait_for_callback(self, timeout: float = 300.0):
            if deliver is not None:
                return deliver(captured["auth_url"])
            return echo_state(captured["auth_url"])

        async def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(O, "OAuthCallbackServer", FakeCallbackServer)

    async def fake_post(url, *, headers=None, json=None, data=None):
        captured["posts"].append(
            {"url": url, "headers": headers, "json": json, "data": data}
        )
        if url == metadata.get("registration_endpoint"):
            return FakeResponse(reg_status, reg_payload or {})
        if data and data.get("grant_type") == "refresh_token":
            return FakeResponse(refresh_status, refresh_payload or {})
        return FakeResponse(token_status, token_payload or {})

    monkeypatch.setattr(M, "ssrf_post", fake_post)
    return storage, captured
