"""Observability page — KPI panel, probe cards and Prometheus exposition."""

from __future__ import annotations

from htpy import Node, details, div, span, summary

from mcp_gway.admin import theme
from mcp_gway.admin.components import (
    badge,
    card,
    code_block,
    feature_heading,
    kv_row,
    pill_button,
    section_title,
    stat_card,
)
from mcp_gway.admin.icons import icon_chevron, icon_refresh

_LOOPBACK = ("127.0.0.1", "::1", "localhost")


def _probe_detail(text: str) -> Node:
    """Silver 12px probe detail line."""
    return span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}] truncate"})[text]


def _probe_row(label: str, status: str, ok: bool, detail: str) -> Node:
    """Probe kv row: status badge (green ok / red fail) plus silver detail.

    Empty details render as None — a lingering empty span plus the flex gap
    kept badge-only rows 8-14px short of the row's right edge."""
    tone = "green" if ok else "red"
    return kv_row(
        label,
        div({"class": "flex items-center justify-end gap-2"})[
            badge("ok" if ok else str(status), tone=tone),
            _probe_detail(detail) if detail else None,
        ],
    )


def _exposition_details(exposition: str) -> Node:
    """Native details/summary disclosure around the Prometheus exposition."""
    return details({"class": "group"})[
        summary(
            {
                "class": (
                    "list-none cursor-pointer flex items-center justify-between "
                    "gap-3 py-1"
                ),
                "style": "marker:none",
            }
        )[
            feature_heading("Prometheus exposition"),
            span(
                {
                    "class": (
                        f"text-[{theme.TEXT_SILVER}] rotate-90 transition-transform "
                        "duration-200 group-open:-rotate-90"
                    )
                }
            )[icon_chevron(14)],
        ],
        code_block(exposition, cls="max-h-[400px] overflow-y-auto mt-3"),
    ]


def metrics_fragment(*, stats: dict[str, str], exposition: str) -> Node:
    """INNER content for #metrics-panel: KPI tiles plus the exposition card."""
    kpis = div({"class": "grid grid-cols-2 xl:grid-cols-4 gap-4"})[
        stat_card("Uptime", stats["uptime"], tone="white"),
        stat_card("HTTP requests", stats["requests"], tone="white"),
        stat_card("Tool calls", stats["tool_calls"], tone="white"),
        stat_card("Sandbox runs", stats["sandbox_runs"], tone="white"),
    ]
    exposition_card = card(
        feature_heading("Exposition"),
        div({"class": "mt-3"})[_exposition_details(exposition)],
        div({"class": "mt-3"})[
            span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}]"})[
                "Recent spans: GET /admin/partials/traces?limit=50"
            ]
        ],
    )
    return div({"class": "flex flex-col gap-4"})[kpis, exposition_card]


def observability_content(
    *,
    health: dict[str, str],
    stats: dict[str, str],
    exposition: str,
    transport: str,
    host: str,
) -> Node:
    """Full Observability body: probes card plus the polled metrics panel."""
    overall = str(health.get("overall", "unknown"))
    overall_ok = overall == "ok"
    registry = str(health.get("registry", "fail"))
    routes = str(health.get("routes", "fail"))
    loopback = host in _LOOPBACK
    probes = card(
        feature_heading("Probes"),
        div({"class": "mt-3 flex flex-col"})[
            kv_row(
                "Overall",
                badge(
                    "ok" if overall_ok else overall,
                    tone="green" if overall_ok else "orange",
                ),
            ),
            _probe_row(
                "Registry",
                registry,
                registry == "ok",
                health.get("registry_detail", ""),
            ),
            _probe_row(
                "Routes",
                routes,
                routes == "ok",
                health.get("routes_detail", ""),
            ),
            kv_row("Transport", badge(str(transport), tone="blue")),
            kv_row(
                "Host",
                div({"class": "flex items-center justify-end gap-2"})[
                    span(
                        {"class": f"text-[14px] text-[{theme.TEXT_SILVER}] break-all"}
                    )[host],
                    badge("loopback", tone="green")
                    if loopback
                    else badge("exposed", tone="orange"),
                ],
            ),
        ],
        div({"class": "mt-4 flex justify-end"})[
            pill_button(
                "Refresh metrics",
                icon=icon_refresh(),
                hx={
                    "hx-get": "/admin/partials/metrics",
                    "hx-target": "#metrics-panel",
                    "hx-swap": "innerHTML",
                },
            )
        ],
    )
    return div({"class": "flex flex-col gap-5"})[
        section_title("Observability", sub="Probes and metrics from this process"),
        div({"id": "metrics-panel", "aria-live": "polite"})[
            metrics_fragment(stats=stats, exposition=exposition)
        ],
        probes,
    ]
