"""Policy page — local command allow-list, break-glass panel and posture."""

from __future__ import annotations

import os

from htpy import Node, button, div, form, input, span

from mcp_gway.admin import theme
from mcp_gway.admin.components import (
    badge,
    card,
    feature_heading,
    kv_row,
    pill_button,
    section_title,
)
from mcp_gway.core.policy import UnrestrictedStatus

_LOOPBACK = ("127.0.0.1", "::1", "localhost")

_PILL_BASE = (
    "inline-flex items-center gap-2 rounded-[9999px] px-4 py-2 text-[14px] "
    "font-bold uppercase tracking-[1.4px] leading-none transition-colors "
    "cursor-pointer"
)

_DANGER_VARIANT = (
    f"bg-[{theme.NEGATIVE}]/15 text-[{theme.NEGATIVE}] hover:bg-[{theme.NEGATIVE}]/25"
)

_GRAY_STATES = frozenset({"disabled", "marker-missing", "expired"})


def _fmt_seconds(value: float) -> str:
    """Compact duration label (s / m / h) for age and expiry rows."""
    total = int(value)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _state_tone(state: str) -> str:
    """Badge tone by break-glass state; text always carries the state itself."""
    if state == "active":
        return "green"
    if state in _GRAY_STATES:
        return "gray"
    return "orange"


def unrestricted_panel(
    unrestricted: UnrestrictedStatus, *, env_set: bool, csrf_token: str = ""
) -> Node:
    """INNER content for #unrestricted-panel: state, kv rows and actions."""
    state = str(unrestricted.state)
    rows: list[Node] = [
        kv_row("State", badge(state, tone=_state_tone(state))),
        kv_row("Active", "Yes" if unrestricted.active else "No"),
        kv_row("TTL", span({"class": "tabular"})["72h"]),
    ]
    if unrestricted.age_seconds is not None:
        rows.append(
            kv_row(
                "Age",
                span({"class": "tabular"})[_fmt_seconds(unrestricted.age_seconds)],
            )
        )
    if unrestricted.expires_in_seconds is not None:
        rows.append(
            kv_row(
                "Expires in",
                span({"class": "tabular"})[
                    _fmt_seconds(unrestricted.expires_in_seconds)
                ],
            )
        )
    notes: list[Node] = []
    if not env_set:
        if unrestricted.marker_exists:
            text = (
                "MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL is not 1 — marker exists "
                "but is inactive."
            )
        else:
            text = "MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL is not 1 — break-glass inactive."
        notes.append(span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}]"})[text])
    enable = form(
        {
            "method": "post",
            "action": "/admin/partials/policy/unrestricted",
            "hx-post": "/admin/partials/policy/unrestricted",
            "hx-target": "#unrestricted-panel",
            "hx-swap": "innerHTML",
            "hx-confirm": (
                "Create the 72h break-glass marker? This lifts the local-command "
                "allow-list until it expires."
            ),
            "class": "inline-flex",
        }
    )[
        input(type="hidden", name="_csrf", value=csrf_token),
        button({"type": "submit", "class": _PILL_BASE + " " + _DANGER_VARIANT})[
            "Enable break-glass"
        ],
    ]
    disable = pill_button(
        "Disable",
        variant="dark",
        hx={
            "hx-delete": "/admin/partials/policy/unrestricted",
            "hx-target": "#unrestricted-panel",
            "hx-swap": "innerHTML",
            "hx-confirm": "Remove the break-glass marker?",
        },
    )
    return div[
        feature_heading("Break-glass (72h)"),
        div({"class": "mt-3 flex flex-col"})[rows],
        div({"class": "mt-3 flex flex-col gap-2"})[notes],
        div({"class": "mt-4 flex flex-wrap gap-2"})[enable, disable],
    ]


def policy_content(
    *,
    allow_env_value: str,
    allow_set: set[str],
    unrestricted: UnrestrictedStatus,
    serve_host: str,
    transport: str,
    remote_env: str,
    csrf_token: str,
) -> Node:
    """Full Policy body: allow-list card, break-glass panel and posture card."""
    env_set = os.environ.get("MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL") == "1"
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
    break_glass_card = card(
        div({"id": "unrestricted-panel"})[
            unrestricted_panel(unrestricted, env_set=env_set, csrf_token=csrf_token)
        ]
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
        section_title("Policy", sub="Local command allow-list and break-glass state"),
        div({"class": "grid lg:grid-cols-2 gap-4"})[
            allow_card,
            break_glass_card,
            posture,
        ],
    ]
