"""Core package — single source of truth for transport/discovery."""

from __future__ import annotations

from mcp_gway.core.client import (
    create_client_transport,
    discover_tools,
    fetch_server_description,
    refresh_server,
    resolve_server_description,
)
from mcp_gway.core.parsing import parse_envs, parse_headers
from mcp_gway.core.transport import detect_transport

__all__ = [
    "create_client_transport",
    "detect_transport",
    "discover_tools",
    "fetch_server_description",
    "parse_envs",
    "parse_headers",
    "refresh_server",
    "resolve_server_description",
]
