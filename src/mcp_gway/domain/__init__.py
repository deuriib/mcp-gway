"""Domain layer — pure business entities, value objects, and port protocols.

Zero dependencies on web frameworks (Starlette, FastAPI) or transport libraries (MCP).
"""

from __future__ import annotations

from mcp_gway.domain.models import (
    MCPServerConfig,
    MCPServerState,
    OAuthConfig,
    ToolInfo,
)
from mcp_gway.domain.policy import (
    DEFAULT_ALLOW_LIST,
    PolicyDecision,
    check_environment,
    get_allow_list,
    validate_command_syntax,
)
from mcp_gway.domain.ports import (
    ExecutionSandboxPort,
    McpProxyPort,
    PolicyEnforcerPort,
    ServerRegistryPort,
    TokenStoragePort,
)

__all__ = [
    "DEFAULT_ALLOW_LIST",
    "ExecutionSandboxPort",
    "MCPServerConfig",
    "MCPServerState",
    "McpProxyPort",
    "OAuthConfig",
    "PolicyDecision",
    "PolicyEnforcerPort",
    "ServerRegistryPort",
    "TokenStoragePort",
    "ToolInfo",
    "check_environment",
    "get_allow_list",
    "validate_command_syntax",
]
