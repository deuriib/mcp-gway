"""MCP Gateway CLI — manage MCP servers with Code Mode support."""

from __future__ import annotations

from typing import Any

__version__ = "4.8.1"


def call_many(
    registry: Any,
    tool_calls: list[dict[str, Any]],
    *,
    max_concurrency: int | None = None,
    concurrency: int | None = None,
) -> list[dict[str, Any]]:
    """Convenience wrapper for host-side fan-out across tool calls."""
    from mcp_gway.code_mode import CodeMode

    return CodeMode(registry).call_many(
        tool_calls,
        max_concurrency=max_concurrency,
        concurrency=concurrency,
    )


__all__ = ["__version__", "call_many"]
