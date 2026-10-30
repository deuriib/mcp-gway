"""Domain port interfaces (Protocols) for hexagonal architecture.

All external I/O (filesystem, process execution, network proxies, token stores)
must pass through these port protocols.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from mcp_gway.domain.models import MCPServerConfig, ToolInfo
    from mcp_gway.domain.policy import PolicyDecision


@runtime_checkable
class ServerRegistryPort(Protocol):
    """Port for server configuration and tool metadata persistence."""

    def list_servers(self) -> list[str]:
        """List all registered server names."""
        ...

    def list_enabled_servers(self) -> list[str]:
        """List only enabled server names."""
        ...

    def get_server_config(self, name: str) -> MCPServerConfig:
        """Retrieve server configuration by name."""
        ...

    def save_server(
        self, config: MCPServerConfig, tools: list[ToolInfo] | None = None
    ) -> None:
        """Save server configuration and optional tool definitions."""
        ...

    def remove_server(self, name: str) -> bool:
        """Remove a registered server by name. Returns True if removed."""
        ...

    def patch_server_enabled(self, name: str, enabled: bool) -> None:
        """Update enabled flag for a server."""
        ...

    def get_server_tools(self, name: str) -> list[ToolInfo]:
        """Retrieve parsed tool definitions for a registered server."""
        ...


@runtime_checkable
class ExecutionSandboxPort(Protocol):
    """Port for executing sandboxed Starlark / code mode scripts."""

    def execute_code(
        self,
        code: str,
        *,
        timeout: float | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute sandboxed code and return the result dictionary."""
        ...


@runtime_checkable
class McpProxyPort(Protocol):
    """Port for dispatching tool calls to upstream MCP servers."""

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Call a tool on an upstream MCP server asynchronously."""
        ...

    async def list_tools(self, server_name: str) -> list[ToolInfo]:
        """List available tools for an upstream server asynchronously."""
        ...


@runtime_checkable
class TokenStoragePort(Protocol):
    """Port for secure OAuth / credentials storage."""

    def get_token(self, server_name: str) -> dict[str, Any] | None:
        """Retrieve stored credential token dictionary or None."""
        ...

    def save_token(self, server_name: str, token: dict[str, Any]) -> None:
        """Save credential token dictionary."""
        ...

    def delete_token(self, server_name: str) -> bool:
        """Delete stored credential token. Returns True if deleted."""
        ...


@runtime_checkable
class PolicyEnforcerPort(Protocol):
    """Port for validating local command execution policies."""

    def is_command_allowed(self, command: list[str]) -> bool:
        """Return True if command is permitted by current policy."""
        ...

    def check_command(self, command: list[str]) -> PolicyDecision:
        """Evaluate command and return policy decision with code and reason."""
        ...
