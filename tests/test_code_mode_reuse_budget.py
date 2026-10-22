"""Code Mode execution plumbing: per-script connection reuse and result budget."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar, Self

import pytest

from mcp_gway.code_mode import CodeMode
from mcp_gway.models import MCPServerConfig, ToolInfo
from mcp_gway.registry import Registry


class _FakeTransport:
    """Counts transport entries so reuse is observable."""

    def __init__(self) -> None:
        self.enters = 0

    def __call__(self, *_a: object, **_k: object) -> _FakeTransport:
        return self

    async def __aenter__(self) -> tuple[object, object]:
        self.enters += 1
        return SimpleNamespace(read=True), SimpleNamespace(write=True)

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    """One upstream session; records calls and can fail on a chosen index."""

    created: ClassVar[list[_FakeSession]] = []

    def __init__(self, *_a: object, **_k: object) -> None:
        self.calls: list[str] = []
        self.initialized = 0
        self.fail_on: int | None = None
        _FakeSession.created.append(self)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def initialize(self) -> None:
        self.initialized += 1

    async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
        self.calls.append(name)
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            raise ConnectionError("upstream dropped")
        return SimpleNamespace(
            content=[
                SimpleNamespace(text=json.dumps({"ok": True, "n": len(self.calls)}))
            ]
        )


def _code_mode(tmp_path: Path) -> CodeMode:
    registry = Registry(servers_dir=tmp_path / "servers")
    registry.add(
        MCPServerConfig(name="srv", type="remote", url="https://api.example.com/mcp"),
        [
            ToolInfo(
                name="echo",
                description="Echo a value",
                input_schema={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                },
            )
        ],
    )
    return CodeMode(registry)


def _wire(monkeypatch: pytest.MonkeyPatch) -> _FakeTransport:
    transport = _FakeTransport()
    monkeypatch.setattr("mcp_gway.core.create_client_transport", transport)
    monkeypatch.setattr("mcp.ClientSession", _FakeSession)
    _FakeSession.created = []
    return transport


def _envelope(raw: str) -> dict[str, object]:
    return json.loads(raw)


def test_one_script_reuses_one_connection_per_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cm = _code_mode(tmp_path)
    transport = _wire(monkeypatch)

    raw = cm.execute_tool_code(
        "a = Srv.echo(x=1)\nb = Srv.echo(x=2)\nc = Srv.echo(x=3)\nresult = [a, b, c]"
    )
    envelope = _envelope(raw)

    assert transport.enters == 1, "one script must spawn one upstream connection"
    assert len(_FakeSession.created) == 1
    assert _FakeSession.created[0].initialized == 1
    assert _FakeSession.created[0].calls == ["echo", "echo", "echo"]

    calls = envelope["calls"]
    assert isinstance(calls, list)
    assert [c["status"] for c in calls] == ["ok", "ok", "ok"]
    assert [c["reused"] for c in calls] == [False, True, True]
    assert envelope["usage"]["call_count"] == 3
    assert envelope["usage"]["truncated"] is False


def test_connections_do_not_leak_between_scripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cm = _code_mode(tmp_path)
    transport = _wire(monkeypatch)

    cm.execute_tool_code("result = Srv.echo(x=1)")
    cm.execute_tool_code("result = Srv.echo(x=2)")

    assert transport.enters == 2, "each execution gets a fresh connection"
    assert len(_FakeSession.created) == 2


def test_failed_call_evicts_the_session_without_retrying(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cm = _code_mode(tmp_path)
    transport = _wire(monkeypatch)

    original = _FakeSession.__init__

    def _fail_second(self: _FakeSession, *a: object, **k: object) -> None:
        original(self, *a, **k)
        self.fail_on = 2

    monkeypatch.setattr(_FakeSession, "__init__", _fail_second)

    with pytest.raises(Exception, match="upstream dropped"):
        cm.execute_tool_code("a = Srv.echo(x=1)\nb = Srv.echo(x=2)")

    assert transport.enters == 1
    assert _FakeSession.created[0].calls == ["echo", "echo"], "no silent retry"

    monkeypatch.setattr(_FakeSession, "__init__", original)
    cm.execute_tool_code("result = Srv.echo(x=3)")
    assert transport.enters == 2, "a dead session must be replaced next run"


def test_result_budget_truncates_and_stays_valid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cm = _code_mode(tmp_path)
    _wire(monkeypatch)
    monkeypatch.setenv("MCP_GWAY_MAX_RESULT_BYTES", "1024")

    raw = cm.execute_tool_code('result = "x" * 50000')
    envelope = _envelope(raw)

    assert len(raw.encode("utf-8")) <= 1024
    assert envelope["usage"]["truncated"] is True
    assert "truncated" in envelope["result"]


def test_budget_keeps_small_results_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cm = _code_mode(tmp_path)
    _wire(monkeypatch)

    envelope = _envelope(cm.execute_tool_code('result = {"a": 1, "b": [1, 2, 3]}'))

    assert envelope["result"] == {"a": 1, "b": [1, 2, 3]}
    assert envelope["usage"]["truncated"] is False
    assert envelope["logs"] == []
    assert envelope["calls"] == []


def test_logs_are_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cm = _code_mode(tmp_path)
    _wire(monkeypatch)

    envelope = _envelope(cm.execute_tool_code("result = 1" + "\nprint('x')" * 400))
    logs = envelope["logs"]

    assert isinstance(logs, list)
    assert len(logs) <= 201
    assert logs[0].startswith("…["), "dropped log lines must be labelled"
    assert envelope["usage"]["truncated"] is True
