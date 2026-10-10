"""Registry -> view models for the admin dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from mcp_gway.models import MCPServerConfig
from mcp_gway.registry import Registry


@dataclass(frozen=True)
class ServerRow:
    name: str
    type: str
    tool_count: int
    enabled: bool
    detail: str
    has_oauth: bool
    is_code_mode: bool
    description: str = ""


def _tool_count(registry: Registry, name: str) -> int:
    try:
        return len(registry.get_pyi_tools(name))
    except Exception:
        try:
            return registry.read_pyi(name).count("def ")
        except Exception:
            return 0


def _detail(config: MCPServerConfig | None) -> str:
    if config is None:
        return "config unreadable"
    if config.type == "local":
        return " ".join(config.command or [])
    return config.url or ""


def _description(config: MCPServerConfig | None) -> str:
    if config is None:
        return ""
    return str(getattr(config, "description", "") or "")


def server_rows(registry: Registry) -> list[ServerRow]:
    """One row per registry entry; unreadable configs degrade, never raise.
    Order: enabled (active) servers first, then name — stable sort keeps the
    registry's alphabetical order inside each group."""
    rows: list[ServerRow] = []
    for name in registry.list():
        try:
            config: MCPServerConfig | None = registry.get_config(name)
        except Exception:
            config = None
        rows.append(
            ServerRow(
                name=name,
                type=config.type if config else "unknown",
                tool_count=_tool_count(registry, name),
                enabled=bool(getattr(config, "enabled", True)) if config else True,
                detail=_detail(config),
                has_oauth=bool(config.oauth)
                if config and config.oauth is not None
                else False,
                is_code_mode=bool(getattr(config, "is_code_mode_client", True)),
                description=_description(config),
            )
        )
    rows.sort(key=lambda r: not r.enabled)
    return rows


def filter_rows(rows: list[ServerRow], q: str) -> list[ServerRow]:
    """Case-insensitive substring match on name, detail and description (search input)."""
    needle = q.strip().casefold()
    if not needle:
        return rows
    return [
        r
        for r in rows
        if needle in r.name.casefold()
        or needle in r.detail.casefold()
        or needle in r.description.casefold()
    ]
