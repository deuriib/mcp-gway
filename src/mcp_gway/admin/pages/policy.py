"""Policy page — local command allow-list and posture."""

from __future__ import annotations

from htpy import Node, div, span

from mcp_gway.admin import theme
from mcp_gway.admin.components import (
    badge,
    card,
    feature_heading,
    kv_row,
    section_title,
)

_LOOPBACK = ("127.0.0.1", "::1", "localhost")


def policy_content(
    *,
    allow_env_value: str,
    allow_set: set[str],
    serve_host: str,
    transport: str,
    remote_env: str,
) -> Node:
    """Full Policy body: allow-list card and posture card."""
    chips: list[Node] = [badge(name, tone="white") for name in sorted(allow_set)] or [
        badge("none", tone="gray")
    ]
    allow_card = card(
        feature_heading("Local command allow-list"),
        div({"class": "mt-3 flex flex-col"})[
            kv_row(
                "Environment",
                span({"class": "font-mono text-[12px] break-all"})[
                    "MCP_GWAY_ALLOW_LOCAL_COMMANDS"
                ],
            ),
            kv_row("Value", allow_env_value),
        ],
        div({"class": "mt-3 flex flex-wrap gap-2"})[chips],
        span({"class": f"mt-3 block text-[12px] text-[{theme.TEXT_SILVER}]"})[
            "Basename match, case-insensitive; `*` and paths are rejected."
        ],
    )
    loopback = serve_host in _LOOPBACK
    posture = card(
        feature_heading("Posture"),
        div({"class": "mt-3 flex flex-col"})[
            kv_row(
                "Bind host",
                div({"class": "flex items-center justify-end gap-2"})[
                    span(
                        {"class": f"text-[14px] text-[{theme.TEXT_SILVER}] break-all"}
                    )[serve_host],
                    badge("loopback", tone="green")
                    if loopback
                    else badge("exposed", tone="orange"),
                ],
            ),
            kv_row("Transport", badge(str(transport), tone="blue")),
            kv_row(
                "MCP_GWAY_ALLOW_REMOTE",
                badge(f"value {remote_env}", tone="orange")
                if remote_env
                else badge("unset", tone="gray"),
            ),
            kv_row("Admin surface", "loopback-only, CSRF on mutations"),
        ],
    )
    return div({"class": "flex flex-col gap-5"})[
        section_title("Policy", sub="Local command allow-list and posture"),
        div({"class": "grid lg:grid-cols-2 gap-4"})[
            allow_card,
            posture,
        ],
    ]
