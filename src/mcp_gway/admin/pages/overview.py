"""Overview page — KPI tiles, gateway facts and a server preview."""

from __future__ import annotations

from htpy import Node, a, div, span

from mcp_gway.admin import theme
from mcp_gway.admin.components import (
    badge,
    card,
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


def overview_content(
    *,
    rows: list[ServerRow],
    stats: dict[str, str],
    health: str,
    transport: str,
    host: str,
) -> Node:
    """Full Overview body: KPI grid, gateway card and first-five servers card."""
    title = section_title("Overview", sub="Live state from this gateway process")
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
    ]
