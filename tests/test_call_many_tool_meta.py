"""callManyTool: the fifth MCP meta-tool over the existing host-side fan-out."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_gway.code_mode import CodeMode
from mcp_gway.gateway import CODE_MODE_TOOLS, Gateway, InvalidParamsError
from mcp_gway.models import MCPServerConfig, ToolInfo
from mcp_gway.registry import Registry


def _code_mode(tmp_path: Path) -> CodeMode:
    registry = Registry(servers_dir=tmp_path / "servers")
    for name in ("alpha", "beta"):
        registry.add(
            MCPServerConfig(
                name=name, type="remote", url=f"https://{name}.example.com/mcp"
            ),
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


def _stub(monkeypatch: pytest.MonkeyPatch, code_mode: CodeMode, *, fail_on: str = ""):
    """Replace the upstream call with a deterministic, countable stub."""
    seen: list[str] = []

    async def fake(config, tool_name, arguments):
        seen.append(getattr(config, "name", ""))
        if fail_on and getattr(config, "name", "") == fail_on:
            raise RuntimeError(f"{fail_on} exploded")
        return {"server": getattr(config, "name", ""), "tool": tool_name}

    monkeypatch.setattr(code_mode.server_factory, "_call_tool_async", fake)
    return seen


def test_tools_list_exposes_call_many_tool():
    names = [tool["name"] for tool in CODE_MODE_TOOLS]

    assert set(names) == {
        "listToolFiles",
        "readToolFile",
        "getToolDocs",
        "executeTool",
        "callManyTool",
    }
    entry = next(tool for tool in CODE_MODE_TOOLS if tool["name"] == "callManyTool")
    assert entry["inputSchema"]["required"] == ["calls"]
    assert entry["inputSchema"]["properties"]["calls"]["maxItems"] == 50


def test_call_many_keeps_input_order_across_servers(tmp_path, monkeypatch):
    code_mode = _code_mode(tmp_path)
    _stub(monkeypatch, code_mode)

    raw = code_mode.call_many_envelope(
        [
            {"server": "alpha", "tool": "echo", "arguments": {"x": 1}},
            {"server": "beta", "tool": "echo", "arguments": {"x": 2}},
        ]
    )
    envelope = json.loads(raw)

    assert [item["server"] for item in envelope["result"]] == ["alpha", "beta"]
    assert [item["ok"] for item in envelope["result"]] == [True, True]
    assert envelope["logs"] == []
    assert envelope["calls"] == []
    assert envelope["usage"]["truncated"] is False


def test_call_many_isolates_a_failed_call(tmp_path, monkeypatch):
    code_mode = _code_mode(tmp_path)
    _stub(monkeypatch, code_mode, fail_on="beta")

    envelope = json.loads(
        code_mode.call_many_envelope(
            [
                {"server": "alpha", "tool": "echo", "arguments": {"x": 1}},
                {"server": "beta", "tool": "echo", "arguments": {"x": 2}},
            ]
        )
    )

    first, second = envelope["result"]
    assert first["ok"] is True
    assert second["ok"] is False
    assert second["error"]["type"] == "RuntimeError"


def test_unknown_server_is_reported_per_item(tmp_path, monkeypatch):
    code_mode = _code_mode(tmp_path)
    _stub(monkeypatch, code_mode)

    envelope = json.loads(
        code_mode.call_many_envelope(
            [
                {"server": "ghost", "tool": "echo"},
                {"server": "alpha", "tool": "echo", "arguments": {"x": 1}},
            ]
        )
    )

    assert envelope["result"][0]["ok"] is False
    assert envelope["result"][1]["ok"] is True


def test_malformed_item_becomes_data_not_an_exception(tmp_path, monkeypatch):
    code_mode = _code_mode(tmp_path)
    seen = _stub(monkeypatch, code_mode)

    envelope = json.loads(
        code_mode.call_many_envelope(
            [
                {"server": "alpha"},
                {"server": "alpha", "tool": "echo", "arguments": {"x": 1}},
            ]
        )
    )

    first, second = envelope["result"]
    assert first["ok"] is False
    assert "tool" in first["error"]["message"]
    assert second["ok"] is True
    assert seen == ["alpha"], "malformed items are never dispatched"


@pytest.mark.parametrize("calls", [[], [{"server": "alpha", "tool": "echo"}] * 51])
def test_batch_size_errors_are_caller_errors(calls):
    code_mode = CodeMode(Registry(servers_dir=Path("unused-servers")))

    with pytest.raises(InvalidParamsError):
        code_mode.call_many_envelope(calls)


def test_missing_calls_argument_is_rejected(tmp_path):
    gateway = Gateway(_code_mode(tmp_path).registry)

    with pytest.raises(InvalidParamsError):
        gateway._handle_tool_call({"name": "callManyTool", "arguments": {}})


def test_gateway_dispatches_call_many(tmp_path, monkeypatch):
    code_mode = _code_mode(tmp_path)
    _stub(monkeypatch, code_mode)
    gateway = Gateway(code_mode.registry)
    gateway.code_mode = code_mode

    response = gateway._handle_tool_call(
        {
            "name": "callManyTool",
            "arguments": {
                "calls": [{"server": "alpha", "tool": "echo", "arguments": {"x": 1}}]
            },
        }
    )
    payload = json.loads(response["content"][0]["text"])

    assert payload["result"][0]["ok"] is True


def test_oversized_batch_result_is_truncated(tmp_path, monkeypatch):
    code_mode = _code_mode(tmp_path)
    monkeypatch.setenv("MCP_GWAY_MAX_RESULT_BYTES", "1024")

    async def huge(config, tool_name, arguments):
        return "x" * 50_000

    monkeypatch.setattr(code_mode.server_factory, "_call_tool_async", huge)

    raw = code_mode.call_many_envelope(
        [{"server": "alpha", "tool": "echo", "arguments": {}}]
    )
    envelope = json.loads(raw)

    assert len(raw.encode("utf-8")) <= 1024
    assert envelope["usage"]["truncated"] is True
