"""Now-playing footer content — inner fragment polled every 5s by the shell."""

from __future__ import annotations

from htpy import Node, div, span

from mcp_gway.admin import theme
from mcp_gway.admin.components import badge
from mcp_gway.admin.icons import icon_dot


def status_fragment(
    *,
    version: str,
    transport: str,
    host: str,
    sessions: int,
    uptime: str,
    health: str,
    exposed: bool,
) -> Node:
    """Inner footer content: LIVE badge, transport facts, health and version."""
    healthy = health == "ok"
    health_badge = badge(
        "healthy" if healthy else str(health),
        tone="green" if healthy else "orange",
    )
    return div(
        {
            "class": "w-full flex flex-wrap items-center gap-x-6 gap-y-1 text-[12px]",
            "aria-live": "polite",
        }
    )[
        div({"class": "flex items-center gap-2 shrink-0"})[
            span(
                {
                    "class": (
                        f"flex items-center gap-1.5 text-[{theme.GREEN}] "
                        "font-bold uppercase tracking-[1.4px]"
                    )
                }
            )[icon_dot(9), "LIVE"],
            span({"class": f"text-[{theme.TEXT_SILVER}] text-[10px]"})[
                "polls every 5s"
            ],
        ],
        div(
            {
                "class": ("hidden sm:flex flex-1 min-w-0 flex-wrap items-center gap-4"),
            }
        )[
            badge(str(transport), tone="blue"),
            span({"class": "truncate"})[str(host)],
            span({"class": "tabular whitespace-nowrap"})[f"{sessions} sessions"],
            span({"class": "tabular whitespace-nowrap"})[str(uptime)],
        ],
        div({"class": "flex items-center gap-3 shrink-0"})[
            health_badge,
            badge("exposed", tone="orange") if exposed else None,
            span({"class": f"tabular text-[{theme.TEXT_SILVER}]"})[f"v{version}"],
        ],
    ]
