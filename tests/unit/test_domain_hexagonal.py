"""Unit tests verifying hexagonal domain and application use cases with in-memory ports.

Zero external I/O, zero network sockets, zero server startup.
Enforces Criterion 2 and Criterion 3.
"""

from __future__ import annotations

from typing import Any

import pytest

from mcp_gway.application.use_cases import (
    ExecuteCodeUseCase,
    GatewayStatusUseCase,
    ManageServersUseCase,
    ProxyToolCallUseCase,
)
from mcp_gway.domain.models import MCPServerConfig, ToolInfo
from mcp_gway.domain.policy import PolicyDecision
from mcp_gway.domain.ports import (
    ExecutionSandboxPort,
    McpProxyPort,
    PolicyEnforcerPort,
    ServerRegistryPort,
    TokenStoragePort,
)
from mcp_gway.infrastructure.container import GatewayContainer


class InMemoryRegistry(ServerRegistryPort):
    def __init__(self) -> None:
        self.configs: dict[str, MCPServerConfig] = {}
        self.tools: dict[str, list[ToolInfo]] = {}

    def list_servers(self) -> list[str]:
        return sorted(self.configs.keys())

    def list_enabled_servers(self) -> list[str]:
        return sorted(k for k, v in self.configs.items() if getattr(v, "enabled", True))

    def get_server_config(self, name: str) -> MCPServerConfig:
        if name not in self.configs:
            raise KeyError(f"Server not found: {name}")
        return self.configs[name]

    def save_server(
        self, config: MCPServerConfig, tools: list[ToolInfo] | None = None
    ) -> None:
        self.configs[config.name] = config
        if tools is not None:
            self.tools[config.name] = list(tools)

    def remove_server(self, name: str) -> bool:
        if name in self.configs:
            del self.configs[name]
            self.tools.pop(name, None)
            return True
        return False

    def patch_server_enabled(self, name: str, enabled: bool) -> None:
        if name in self.configs:
            self.configs[name].enabled = enabled

    def get_server_tools(self, name: str) -> list[ToolInfo]:
        return self.tools.get(name, [])


class InMemorySandbox(ExecutionSandboxPort):
    def __init__(self) -> None:
        self.executed_snippets: list[str] = []

    def execute_code(
        self,
        code: str,
        *,
        timeout: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.executed_snippets.append(code)
        return {"result": 42, "logs": ["executed safely"]}


class InMemoryProxy(McpProxyPort):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        self.calls.append((server_name, tool_name, arguments))
        return {"output": f"called {tool_name} on {server_name}"}

    async def list_tools(self, server_name: str) -> list[ToolInfo]:
        return [ToolInfo(name="dummy_tool", description="A dummy tool")]


class InMemoryPolicy(PolicyEnforcerPort):
    def __init__(self, allowed_binaries: set[str] | None = None) -> None:
        self.allowed = allowed_binaries or {"npx", "uvx"}

    def is_command_allowed(self, command: list[str]) -> bool:
        return self.check_command(command).allowed

    def check_command(self, command: list[str]) -> PolicyDecision:
        binary = command[0] if command else ""
        if binary in self.allowed:
            return PolicyDecision(allowed=True, reason_code="allowed", message="OK")
        return PolicyDecision(
            allowed=False,
            reason_code="denied",
            message=f"Binary '{binary}' is not allowed",
        )


class InMemoryTokenStorage(TokenStoragePort):
    def __init__(self) -> None:
        self.tokens: dict[str, dict[str, Any]] = {}

    def get_token(self, server_name: str) -> dict[str, Any] | None:
        return self.tokens.get(server_name)

    def save_token(self, server_name: str, token: dict[str, Any]) -> None:
        self.tokens[server_name] = token

    def delete_token(self, server_name: str) -> bool:
        return self.tokens.pop(server_name, None) is not None


def test_manage_servers_use_case_lifecycle() -> None:
    registry = InMemoryRegistry()
    policy = InMemoryPolicy()
    use_case = ManageServersUseCase(registry=registry, policy=policy)

    # 1. Register valid local server
    cfg = MCPServerConfig(
        name="local_tools", type="local", command=["npx", "-y", "pkg"]
    )
    tool = ToolInfo(name="read_file", description="reads file")
    use_case.register_server(cfg, tools=[tool])

    assert use_case.list_servers() == ["local_tools"]
    assert use_case.list_servers(enabled_only=True) == ["local_tools"]
    assert use_case.get_server("local_tools").name == "local_tools"
    assert len(use_case.get_server_tools("local_tools")) == 1

    # 2. Toggle disabled
    use_case.toggle_server("local_tools", False)
    assert use_case.list_servers() == ["local_tools"]
    assert use_case.list_servers(enabled_only=True) == []

    # 3. Unregister
    assert use_case.unregister_server("local_tools") is True
    assert use_case.list_servers() == []


def test_manage_servers_policy_enforcement() -> None:
    registry = InMemoryRegistry()
    policy = InMemoryPolicy(allowed_binaries={"npx"})
    use_case = ManageServersUseCase(registry=registry, policy=policy)

    # Attempt to register server with forbidden command (syntactically valid tokens, but binary denied by policy)
    forbidden_cfg = MCPServerConfig(
        name="evil_server", type="local", command=["python", "-m", "evil"]
    )
    with pytest.raises(PermissionError, match="Binary 'python' is not allowed"):
        use_case.register_server(forbidden_cfg)

    assert use_case.list_servers() == []


def test_execute_code_use_case() -> None:
    sandbox = InMemorySandbox()
    use_case = ExecuteCodeUseCase(sandbox=sandbox)

    res = use_case.execute("result = 6 * 7")
    assert res["result"] == 42
    assert res["logs"] == ["executed safely"]
    assert len(sandbox.executed_snippets) == 1


@pytest.mark.asyncio
async def test_proxy_tool_call_use_case() -> None:
    registry = InMemoryRegistry()
    proxy = InMemoryProxy()
    use_case = ProxyToolCallUseCase(proxy=proxy, registry=registry)

    cfg = MCPServerConfig(
        name="remote_srv", type="remote", url="https://example.com/mcp"
    )
    registry.save_server(cfg)

    # Call tool when enabled
    result = await use_case.call_tool("remote_srv", "fetch", {"url": "https://test"})
    assert result == {"output": "called fetch on remote_srv"}

    # Call tool when server is disabled
    registry.patch_server_enabled("remote_srv", False)
    with pytest.raises(ValueError, match="Server 'remote_srv' is disabled"):
        await use_case.call_tool("remote_srv", "fetch")


def test_gateway_status_use_case() -> None:
    registry = InMemoryRegistry()
    status_use_case = GatewayStatusUseCase(registry=registry)

    cfg1 = MCPServerConfig(name="srv1", type="remote", url="https://example.com/1")
    cfg2 = MCPServerConfig(
        name="srv2", type="remote", url="https://example.com/2", enabled=False
    )
    registry.save_server(cfg1)
    registry.save_server(cfg2)

    status = status_use_case.get_status()
    assert status["status"] == "healthy"
    assert status["total_servers"] == 2
    assert status["enabled_servers"] == 1
    assert status["server_names"] == ["srv1", "srv2"]


def test_gateway_container_dependency_injection() -> None:
    registry = InMemoryRegistry()
    sandbox = InMemorySandbox()
    policy = InMemoryPolicy()
    tokens = InMemoryTokenStorage()

    container = GatewayContainer(
        registry=registry,
        sandbox=sandbox,
        policy=policy,
        tokens=tokens,
    )

    # Validate that use cases are properly wired with the injected ports
    assert container.manage_servers._registry is registry
    assert container.manage_servers._policy is policy
    assert container.execute_code._sandbox is sandbox
    assert container.gateway_status._registry is registry
