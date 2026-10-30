"""Application use cases orchestrating domain entities and ports.

These use cases contain the core business orchestration and do not know
about specific transports (HTTP/SSE/CLI) or concrete storage mechanisms.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_gway.domain.models import MCPServerConfig, ToolInfo
from mcp_gway.domain.ports import (
    ExecutionSandboxPort,
    McpProxyPort,
    PolicyEnforcerPort,
    ServerRegistryPort,
)

logger = logging.getLogger(__name__)


class ManageServersUseCase:
    """Use case for managing MCP server registrations and life cycle."""

    def __init__(
        self,
        registry: ServerRegistryPort,
        policy: PolicyEnforcerPort | None = None,
    ) -> None:
        self._registry = registry
        self._policy = policy

    def list_servers(self, *, enabled_only: bool = False) -> list[str]:
        """List registered server names, optionally filtering by enabled status."""
        if enabled_only:
            return self._registry.list_enabled_servers()
        return self._registry.list_servers()

    def get_server(self, name: str) -> MCPServerConfig:
        """Get server configuration by name."""
        return self._registry.get_server_config(name)

    def register_server(
        self,
        config: MCPServerConfig,
        tools: list[ToolInfo] | None = None,
    ) -> None:
        """Validate policy and register a server configuration."""
        if config.type == "local" and config.command and self._policy is not None:
            decision = self._policy.check_command(config.command)
            if not decision.allowed:
                raise PermissionError(decision.message)

        self._registry.save_server(config, tools=tools)
        logger.info("Registered server: %s (type=%s)", config.name, config.type)

    def unregister_server(self, name: str) -> bool:
        """Remove a registered server."""
        removed = self._registry.remove_server(name)
        if removed:
            logger.info("Unregistered server: %s", name)
        return removed

    def toggle_server(self, name: str, enabled: bool) -> None:
        """Toggle a server's enabled state."""
        self._registry.patch_server_enabled(name, enabled)
        logger.info("Toggled server %s: enabled=%s", name, enabled)

    def get_server_tools(self, name: str) -> list[ToolInfo]:
        """Get tools for a given server."""
        return self._registry.get_server_tools(name)


class ExecuteCodeUseCase:
    """Use case for executing sandboxed code."""

    def __init__(self, sandbox: ExecutionSandboxPort) -> None:
        self._sandbox = sandbox

    def execute(
        self,
        code: str,
        *,
        timeout: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute sandboxed code with optional timeout and context."""
        return self._sandbox.execute_code(code, timeout=timeout, context=context)


class ProxyToolCallUseCase:
    """Use case for dispatching tool calls to upstream MCP servers."""

    def __init__(
        self,
        proxy: McpProxyPort,
        registry: ServerRegistryPort,
    ) -> None:
        self._proxy = proxy
        self._registry = registry

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Call a tool on an enabled server."""
        cfg = self._registry.get_server_config(server_name)
        if not getattr(cfg, "enabled", True):
            raise ValueError(f"Server '{server_name}' is disabled")

        return await self._proxy.call_tool(server_name, tool_name, arguments)

    async def list_tools(self, server_name: str) -> list[ToolInfo]:
        """List available tools for a server."""
        return await self._proxy.list_tools(server_name)


class GatewayStatusUseCase:
    """Use case for querying overall gateway state and statistics."""

    def __init__(self, registry: ServerRegistryPort) -> None:
        self._registry = registry

    def get_status(self) -> dict[str, Any]:
        """Return gateway status summary."""
        all_servers = self._registry.list_servers()
        enabled_servers = self._registry.list_enabled_servers()
        return {
            "status": "healthy",
            "total_servers": len(all_servers),
            "enabled_servers": len(enabled_servers),
            "server_names": all_servers,
        }
