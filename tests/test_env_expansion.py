"""Spawn-time and persistence tests for per-server ``{env:NAME}`` expansion."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from mcp_gway.core.client import create_client_transport
from mcp_gway.core.parsing import parse_envs
from mcp_gway.models import MCPServerConfig
from mcp_gway.registry import Registry


def _stub_spawn(monkeypatch, capture: SimpleNamespace) -> None:
    monkeypatch.setenv("MCP_GWAY_ALLOW_LOCAL_COMMANDS", "fakeserver")
    monkeypatch.setattr(
        "mcp_gway.core.policy.resolve_binary", lambda b: "/usr/bin/fakeserver"
    )
    monkeypatch.setattr(
        "mcp_gway.stdio_transport.resolve_windows_command",
        lambda c: "/usr/bin/fakeserver",
    )

    @asynccontextmanager
    async def _client(*, server, on_noise=None):
        capture.params = server
        yield AsyncMock(), AsyncMock()

    monkeypatch.setattr("mcp_gway.stdio_transport.filtered_stdio_client", _client)


async def test_spawn_expands_placeholder_from_process_env(monkeypatch) -> None:
    capture = SimpleNamespace()
    _stub_spawn(monkeypatch, capture)
    monkeypatch.setenv("TEST_PROVIDER_KEY", "synthetic-secret-abc")
    cfg = MCPServerConfig(
        name="envx",
        type="local",
        command=["fakeserver"],
        environment={"API_KEY": "{env:TEST_PROVIDER_KEY}"},
    )

    async with create_client_transport(cfg):
        pass

    assert capture.params.env["API_KEY"] == "synthetic-secret-abc"
    assert cfg.environment["API_KEY"] == "{env:TEST_PROVIDER_KEY}"


def test_parse_envs_stores_placeholder_raw() -> None:
    assert parse_envs(["API_KEY={env:PROVIDER_API_KEY}"]) == {
        "API_KEY": "{env:PROVIDER_API_KEY}"
    }


def test_registry_persists_placeholder_only(tmp_path) -> None:
    cfg = MCPServerConfig(
        name="envx",
        type="local",
        command=["fakeserver"],
        environment={"API_KEY": "{env:PROVIDER_API_KEY}"},
    )
    reg = Registry(servers_dir=tmp_path / "r")

    reg.add(cfg, tools=[])

    stored = (tmp_path / "r" / "envx.json").read_text()
    assert "{env:PROVIDER_API_KEY}" in stored
    assert "synthetic-secret-abc" not in stored
