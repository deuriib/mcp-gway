"""Filesystem adapter implementing the ServerRegistryPort.

Persists server configurations as JSON and .pyi stubs using atomic writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from mcp_gway.domain.ports import ServerRegistryPort
from mcp_gway.registry import Registry

if TYPE_CHECKING:
    from mcp_gway.domain.models import MCPServerConfig, ToolInfo


class FilesystemRegistryAdapter(ServerRegistryPort):
    """Adapter bridging ServerRegistryPort to the filesystem Registry."""

    def __init__(self, servers_dir: Path | str = "servers") -> None:
        self._registry = Registry(servers_dir=servers_dir)

    def list_servers(self) -> list[str]:
        return self._registry.list()

    def list_enabled_servers(self) -> list[str]:
        return self._registry.list_enabled()

    def get_server_config(self, name: str) -> MCPServerConfig:
        return self._registry.get_config(name)

    def save_server(
        self, config: MCPServerConfig, tools: list[ToolInfo] | None = None
    ) -> None:
        self._registry.add(config, tools or [])

    def remove_server(self, name: str) -> bool:
        return self._registry.remove(name)

    def patch_server_enabled(self, name: str, enabled: bool) -> None:
        self._registry.patch_enabled(name, enabled)

    def get_server_tools(self, name: str) -> list[ToolInfo]:
        return self._registry.get_tools(name)
