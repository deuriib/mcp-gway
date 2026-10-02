"""Tests for the `tools` CLI group (Code Mode in the terminal)."""

import json

import pytest
from click.testing import CliRunner

from mcp_gway.cli import main
from mcp_gway.models import MCPServerConfig, ToolInfo
from mcp_gway.registry import Registry


@pytest.fixture
def seeded_runner(tmp_path, monkeypatch):
    servers_dir = tmp_path / "servers"
    servers_dir.mkdir()

    def mock_get_registry():
        return Registry(servers_dir=servers_dir)

    monkeypatch.setattr("mcp_gway.cli._get_registry", mock_get_registry)
    registry = Registry(servers_dir=servers_dir)
    registry.add(
        MCPServerConfig(name="Demo", type="remote", url="https://api.example.com/mcp"),
        [ToolInfo(name="ping", description="Ping it")],
    )
    return CliRunner(), registry


def test_tools_group_help_lists_subcommands():
    result = CliRunner().invoke(main, ["tools", "--help"])
    assert result.exit_code == 0
    for sub in ("list", "read", "docs", "exec"):
        assert sub in result.output


def test_tools_list_empty(tmp_path, monkeypatch):
    servers_dir = tmp_path / "servers"
    servers_dir.mkdir()
    monkeypatch.setattr(
        "mcp_gway.cli._get_registry", lambda: Registry(servers_dir=servers_dir)
    )
    result = CliRunner().invoke(main, ["tools", "list"])
    assert result.exit_code == 0
    assert "No servers" in result.output


def test_tools_list_shows_stubs(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(main, ["tools", "list"])
    assert result.exit_code == 0
    assert "Demo.pyi" in result.output


def test_tools_list_tool_binding(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(main, ["tools", "list", "--binding", "tool"])
    assert result.exit_code == 0
    assert "ping.pyi" in result.output


def test_tools_list_rejects_bad_binding(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(main, ["tools", "list", "--binding", "bogus"])
    assert result.exit_code == 2


def test_tools_read_server_stub(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(main, ["tools", "read", "--server", "Demo"])
    assert result.exit_code == 0
    assert "def ping" in result.output


def test_tools_read_requires_server(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(main, ["tools", "read"])
    assert result.exit_code == 2


def test_tools_read_missing_server(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(main, ["tools", "read", "--server", "Ghost"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_tools_read_tool_stub(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(
        main, ["tools", "read", "--server", "Demo", "--tool", "ping"]
    )
    assert result.exit_code == 0
    assert "def ping" in result.output


def test_tools_docs(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(
        main, ["tools", "docs", "--server", "Demo", "--tool", "ping"]
    )
    assert result.exit_code == 0
    assert "ping" in result.output


def test_tools_exec_inline_code(seeded_runner, monkeypatch):
    runner, _registry = seeded_runner
    monkeypatch.setattr(
        "mcp_gway.code_mode.CodeMode.execute_tool_code",
        lambda self, code, timeout=None: json.dumps(
            {"result": {"ok": True}, "logs": []}
        ),
    )
    result = runner.invoke(main, ["tools", "exec", "--code", "result = Demo.ping()"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["result"] == {"ok": True}


def test_tools_exec_missing_code_and_file(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(main, ["tools", "exec"])
    assert result.exit_code == 2


def test_tools_exec_rejects_both_code_and_file(seeded_runner, tmp_path):
    runner, _registry = seeded_runner
    snippet = tmp_path / "run.star"
    snippet.write_text("result = Demo.ping()", encoding="utf-8")
    result = runner.invoke(
        main,
        ["tools", "exec", "--code", "result = 1", "--file", str(snippet)],
    )
    assert result.exit_code == 2


def test_tools_exec_reads_file(seeded_runner, tmp_path, monkeypatch):
    runner, _registry = seeded_runner
    snippet = tmp_path / "run.star"
    snippet.write_text("result = Demo.ping()", encoding="utf-8")
    seen: dict[str, str] = {}
    real = None

    from mcp_gway.code_mode import CodeMode

    real = CodeMode.execute_tool_code

    def _fake(self, code, timeout=None):
        seen["code"] = code
        return json.dumps({"result": 1, "logs": []})

    monkeypatch.setattr(CodeMode, "execute_tool_code", _fake)
    result = runner.invoke(main, ["tools", "exec", "--file", str(snippet)])
    assert result.exit_code == 0, result.output
    assert "Demo.ping" in seen["code"]
    assert real is not None


def test_tools_exec_missing_file(seeded_runner):
    runner, _registry = seeded_runner
    result = runner.invoke(main, ["tools", "exec", "--file", "does-not-exist.star"])
    assert result.exit_code == 2


def test_tools_exec_denied_local_policy(tmp_path, monkeypatch):
    from mcp_gway.core.policy import PolicyDecision

    servers_dir = tmp_path / "servers"
    servers_dir.mkdir()
    monkeypatch.setattr(
        "mcp_gway.cli._get_registry", lambda: Registry(servers_dir=servers_dir)
    )
    registry = Registry(servers_dir=servers_dir)
    registry.add(
        MCPServerConfig(name="Local", type="local", command=["node", "server.js"]),
        [ToolInfo(name="ping", description="Ping")],
    )
    monkeypatch.setattr(
        "mcp_gway.core.policy.check_local_command",
        lambda cmd, require_binary=True: PolicyDecision(
            allowed=False,
            message="denied by policy",
            reason_code="denied",
        ),
    )
    result = CliRunner().invoke(
        main, ["tools", "exec", "--code", "result = Local.ping()"]
    )
    assert result.exit_code == 1
    assert "denied" in result.output.lower()
