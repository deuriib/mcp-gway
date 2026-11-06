"""R8: tool calls authenticate when a stored token exists."""

from __future__ import annotations

from types import SimpleNamespace

from mcp.shared.auth import OAuthToken

from mcp_gway import core
from mcp_gway.models import MCPServerConfig
from mcp_gway.oauth import FileTokenStorage, has_stored_tokens
from mcp_gway.registry import Registry
from mcp_gway.server_factory import ServerFactory


class _Transport:
    async def __aenter__(self):
        return SimpleNamespace(read=True), SimpleNamespace(write=True)

    async def __aexit__(self, *exc):
        return False


def _install_transport(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    def fake_transport(config, **kwargs):
        calls.append({"config": config, **kwargs})
        return _Transport()

    monkeypatch.setattr(core, "create_client_transport", fake_transport)
    return calls


class _Session:
    def __init__(self, *_a, **_k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def initialize(self) -> None:
        return None

    async def call_tool(self, name: str, arguments: object) -> object:
        return SimpleNamespace(content=[SimpleNamespace(text='"ok"')])


def _install_session(monkeypatch) -> None:
    monkeypatch.setattr("mcp.ClientSession", _Session)


async def test_has_stored_tokens_unwritable_home_returns_false(tmp_path, monkeypatch):
    blocked = tmp_path / "blocked-home"
    blocked.write_text("not a directory", encoding="utf-8")
    monkeypatch.setenv("HOME", str(blocked))
    assert await has_stored_tokens("srv") is False


async def _seed_token(name: str, access_token: str = "stored-token") -> None:
    await FileTokenStorage(name).set_tokens(
        OAuthToken(access_token=access_token, token_type="Bearer")
    )


def _factory(tmp_path) -> ServerFactory:
    return ServerFactory(Registry(tmp_path / "servers"))


async def test_has_stored_tokens_requires_non_empty_access_token(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert await has_stored_tokens("srv") is False
    await _seed_token("srv", access_token="")
    assert await has_stored_tokens("srv") is False
    await _seed_token("srv")
    assert await has_stored_tokens("srv") is True


async def test_remote_with_stored_token_forces_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    await _seed_token("srv")
    calls = _install_transport(monkeypatch)
    _install_session(monkeypatch)
    cfg = MCPServerConfig(name="srv", type="remote", url="https://api.example.com/mcp")

    result = await _factory(tmp_path)._call_tool_async(cfg, "echo", {})

    assert result == "ok"
    assert calls[0]["force_auth"] is True


async def test_remote_without_token_does_not_force_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    calls = _install_transport(monkeypatch)
    _install_session(monkeypatch)
    cfg = MCPServerConfig(name="srv", type="remote", url="https://api.example.com/mcp")

    result = await _factory(tmp_path)._call_tool_async(cfg, "echo", {})

    assert result == "ok"
    assert calls[0]["force_auth"] is False


async def test_local_config_does_not_force_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    await _seed_token("loc1")
    calls = _install_transport(monkeypatch)
    _install_session(monkeypatch)
    cfg = MCPServerConfig(name="loc1", type="local", command=["python3", "-c", "pass"])

    result = await _factory(tmp_path)._call_tool_async(cfg, "echo", {})

    assert result == "ok"
    assert calls[0]["force_auth"] is False


async def test_oauth_false_with_stored_token_does_not_force_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    await _seed_token("anon")
    calls = _install_transport(monkeypatch)
    _install_session(monkeypatch)
    cfg = MCPServerConfig(
        name="anon",
        type="remote",
        url="https://api.example.com/mcp",
        oauth=False,
    )

    result = await _factory(tmp_path)._call_tool_async(cfg, "echo", {})

    assert result == "ok"
    assert calls[0]["force_auth"] is False
