"""Overview page — KPI tiles, gateway facts, a server preview and Connect card."""

from __future__ import annotations

import json

from htpy import Node, a, div, span

from mcp_gway.admin import theme
from mcp_gway.admin.components import (
    badge,
    card,
    code_block,
    empty_state,
    feature_heading,
    kv_row,
    section_title,
    stat_card,
)
from mcp_gway.admin.data import ServerRow

_DARK_PILL = (
    "inline-flex items-center gap-2 rounded-[9999px] px-4 py-2 text-[14px] "
    "font-bold uppercase tracking-[1.4px] leading-none transition-colors "
    f"bg-[{theme.SURFACE_MID}] text-[{theme.TEXT}] hover:bg-[{theme.HOVER_SURFACE}]"
)

_GREEN_PILL = (
    "inline-flex items-center rounded-[9999px] px-4 py-2 text-[14px] "
    f"font-bold uppercase tracking-[1.4px] bg-[{theme.GREEN}] text-black "
    f"hover:bg-[{theme.HOVER_GREEN}] transition-colors"
)

_LINE = (
    "flex flex-wrap items-center justify-between gap-3 py-3 border-b "
    f"border-[{theme.BORDER}] last:border-0 min-w-0"
)


def _type_badge(row_type: str) -> Node:
    """Type chip: local blue, remote white, unknown gray (always with text)."""
    if row_type == "local":
        return badge("local", tone="blue")
    if row_type == "remote":
        return badge("remote", tone="white")
    return badge("unknown", tone="gray")


def _preview_line(row: ServerRow) -> Node:
    """First-five list item: linked name, type, detail and tool count."""
    return a(
        {
            "href": f"/admin/servers/{row.name}",
            "class": _LINE + " hover:opacity-80 transition-opacity",
        }
    )[
        div({"class": "flex items-center gap-2 min-w-0"})[
            span(
                {
                    "class": (
                        f"text-[14px] font-bold text-[{theme.TEXT}] truncate hover:underline"
                    )
                }
            )[row.name],
            _type_badge(row.type),
            badge("disabled", tone="gray") if not row.enabled else None,
        ],
        div({"class": "flex items-center gap-3 shrink-0"})[
            span(
                {
                    "class": (
                        f"text-[12px] text-[{theme.TEXT_SILVER}] truncate max-w-[22ch]"
                    )
                }
            )[row.detail],
            span({"class": f"tabular text-[12px] text-[{theme.TEXT_SILVER}]"})[
                f"{row.tool_count} tools"
            ],
        ],
    ]


def _connect_block(title: str, caption: str, snippet: str) -> Node:
    """One client recipe: name, where it lives, copy-paste content."""
    return div({"class": "flex flex-col gap-1.5 min-w-0"})[
        span({"class": f"text-[13px] font-bold text-[{theme.TEXT}]"})[title],
        span({"class": f"text-[11px] text-[{theme.TEXT_SILVER}]"})[caption],
        code_block(snippet, cls="mt-1"),
    ]


def _connect_card(*, endpoint_url: str, messages_url: str, transport: str) -> Node:
    """Live endpoint plus copy-paste recipes, with no JS (CSP-safe).

    OpenCode and Antigravity document the plugins this repo ships: both
    register the gateway themselves, so a raw remote-server block would
    duplicate the registration (and Antigravity's remote transport is not
    verified in this repo).
    """
    endpoint = (
        f"GET {endpoint_url} + POST {messages_url}"
        if transport == "sse"
        else f"POST {endpoint_url}"
    )
    claude = json.dumps(
        {"mcpServers": {"gateway": {"type": "http", "url": endpoint_url}}},
        indent=2,
    )
    opencode = json.dumps(
        {"mcp": {"servers": {"gateway": {"type": "remote", "url": endpoint_url}}}}
    )
    antigravity = json.dumps({"mcpServers": {"gateway": {"serverUrl": endpoint_url}}})

    return card(
        div({"class": "flex flex-wrap items-baseline justify-between gap-2"})[
            feature_heading("Connect"),
            span({"class": f"text-[11px] text-[{theme.TEXT_SILVER}]"})[endpoint],
        ],
        div({"class": "mt-3 grid lg:grid-cols-3 gap-4"})[
            _connect_block("Claude Code", "mcp.json (global)", claude),
            _connect_block(
                "OpenCode V2",
                "~/.config/opencode/opencode.jsonc (global)",
                opencode,
            ),
            _connect_block(
                "Antigravity",
                "~/.gemini/config/mcp_config.json (global)",
                antigravity,
            ),
        ],
    )


def overview_content(
    *,
    rows: list[ServerRow],
    stats: dict[str, str],
    health: str,
    transport: str,
    host: str,
    endpoint_url: str,
    messages_url: str,
) -> Node:
    """Full Overview body: KPI grid, gateway card, first-five servers and Connect."""
    title = section_title("Overview", sub="Live state from this gateway process")
    connect = _connect_card(
        endpoint_url=endpoint_url,
        messages_url=messages_url,
        transport=transport,
    )
    if not rows:
        return div({"class": "flex flex-col gap-5"})[
            title,
            empty_state(
                "No servers yet.",
                "Add your first MCP server to aggregate its tools behind one endpoint.",
                action=a({"href": "/admin/servers", "class": _GREEN_PILL})[
                    "Add server"
                ],
            ),
            connect,
        ]
    healthy = health == "ok"
    kpis = div({"class": "grid grid-cols-2 xl:grid-cols-4 gap-4"})[
        stat_card("Servers", stats["servers"]),
        stat_card("Total tools", stats["tools"]),
        stat_card("Uptime", stats["uptime"]),
        stat_card("Active sessions", stats["sessions"]),
    ]
    gateway = card(
        feature_heading("Gateway"),
        div({"class": "mt-3 flex flex-col"})[
            kv_row("Transport", badge(str(transport), tone="blue")),
            kv_row("Host", str(host)),
            kv_row(
                "Health",
                badge(
                    "healthy" if healthy else str(health),
                    tone="green" if healthy else "orange",
                ),
            ),
        ],
    )
    preview = card(
        div({"class": "flex items-center justify-between gap-3"})[
            feature_heading("Servers"),
            a({"href": "/admin/servers", "class": _DARK_PILL})["View all"],
        ],
        div({"class": "mt-2 flex flex-col"})[[_preview_line(r) for r in rows[:5]]],
    )
    return div({"class": "flex flex-col gap-5"})[
        title,
        kpis,
        div({"class": "grid lg:grid-cols-2 gap-4"})[gateway, preview],
        connect,
    ]
