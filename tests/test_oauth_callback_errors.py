"""R5: callback error/error_description surfaced, escaped, never reflected raw."""

from __future__ import annotations

from typing import Any

from mcp_gway import oauth as O
from tests.helpers.oauth_flow_harness import install_flow

_MCP = "https://mcp.test/mcp"
_AUTH = "https://auth.test"


class _MemWriter:
    def __init__(self) -> None:
        self.data = b""

    def write(self, chunk: bytes) -> None:
        self.data += chunk

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        return None


class _MemReader:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    async def read(self, _n: int) -> bytes:
        return self._raw


async def _handle(query: str) -> tuple[dict[str, str] | None, bytes]:
    server = O.OAuthCallbackServer()
    writer = _MemWriter()
    raw = f"GET /callback?{query} HTTP/1.1\r\nHost: x\r\n\r\n".encode()
    await server._handle_request(_MemReader(raw), writer)
    return server._result, writer.data


def _metadata() -> dict[str, Any]:
    return {
        "authorization_endpoint": f"{_AUTH}/oauth/auth",
        "token_endpoint": f"{_AUTH}/oauth/token",
    }


async def test_callback_error_sets_result():
    result, response = await _handle(
        "error=invalid_request&error_description=missing+required+parameter&state=S1"
    )
    assert result is not None
    assert result["error"] == "invalid_request"
    assert result["error_description"] == "missing required parameter"
    assert result["state"] == "S1"
    assert b"400" in response


async def test_callback_error_html_is_escaped_truncated_and_control_stripped():
    payload = "<script>alert(1)</script>" + "\x07" + "A" * 400
    result, response = await _handle(f"error=bad&error_description={payload}&state=S")
    assert result is not None
    body = response.decode()
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
    assert "\x07" not in body
    assert len(result["error_description"]) <= 200


async def test_callback_error_does_not_reflect_code():
    result, response = await _handle("error=access_denied&code=SECRET-CODE")
    assert result is not None
    assert "SECRET-CODE" not in response.decode()


async def test_callback_error_surfaced_through_output_callback(tmp_path, monkeypatch):
    _storage, captured = install_flow(
        monkeypatch,
        tmp_path,
        "cberror",
        metadata=_metadata(),
        deliver=lambda _url: {
            "error": "invalid_request",
            "error_description": "missing required parameter 'response_type'",
            "state": "S",
        },
    )
    messages: list[str] = []
    out = await O.run_oauth_flow(
        _MCP,
        "cberror",
        oauth_config={"clientId": "cfg-client"},
        output_callback=messages.append,
    )
    assert out is None
    assert captured["posts"] == []
    joined = "\n".join(messages)
    assert "invalid_request" in joined
    assert "missing required parameter 'response_type'" in joined


async def test_callback_error_does_not_time_out(tmp_path, monkeypatch):
    _storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "cbfast",
        metadata=_metadata(),
        deliver=lambda _url: {"error": "access_denied", "error_description": "denied"},
    )
    messages: list[str] = []
    out = await O.run_oauth_flow(
        _MCP,
        "cbfast",
        oauth_config={"clientId": "cfg-client"},
        output_callback=messages.append,
    )
    assert out is None
    assert any("authorization failed" in m for m in messages)
    assert not any("timed out" in m for m in messages)


async def test_callback_without_code_or_error_still_reports_timeout(
    tmp_path, monkeypatch
):
    _storage, _captured = install_flow(
        monkeypatch,
        tmp_path,
        "cbempty",
        metadata=_metadata(),
        deliver=lambda _url: {"state": "S"},
    )
    messages: list[str] = []
    out = await O.run_oauth_flow(
        _MCP,
        "cbempty",
        oauth_config={"clientId": "cfg-client"},
        output_callback=messages.append,
    )
    assert out is None
    assert any("timed out or no code" in m for m in messages)
