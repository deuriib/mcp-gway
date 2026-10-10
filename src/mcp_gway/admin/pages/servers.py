"""Servers pages — list, grid rows, add modal form, detail and tools panel."""

from __future__ import annotations

from htpy import Element, Node, a, button, div, form, input, label, p, span

from mcp_gway.admin import theme
from mcp_gway.admin.components import (
    badge,
    card,
    checkbox,
    circular_button,
    code_block,
    empty_state,
    feature_heading,
    kv_row,
    label_text,
    modal,
    modal_close_x,
    pill_button,
    search_input,
    section_title,
    select,
    text_input,
    textarea,
)
from mcp_gway.admin.data import ServerRow
from mcp_gway.admin.icons import (
    icon_chevron,
    icon_eye,
    icon_key,
    icon_refresh,
    icon_trash,
)
from mcp_gway.models import MCPServerConfig, ToolInfo

_ADD_HX: dict[str, str] = {
    "hx-post": "/admin/partials/servers",
    "hx-target": "#server-grid",
    "hx-swap": "innerHTML",
    "hx-disabled-elt": "this",
}

_PILL_BASE = (
    "inline-flex items-center gap-2 rounded-[9999px] px-4 py-2 text-[14px] "
    "font-bold uppercase tracking-[1.4px] leading-none transition-colors "
    "cursor-pointer disabled:opacity-50 disabled:pointer-events-none"
)

_DARK_VARIANT = (
    f"bg-[{theme.SURFACE_MID}] text-[{theme.TEXT}] hover:bg-[{theme.HOVER_SURFACE}]"
)

_DANGER_VARIANT = (
    f"bg-[{theme.NEGATIVE}]/15 text-[{theme.NEGATIVE}] hover:bg-[{theme.NEGATIVE}]/25"
)

_GREEN_VARIANT = f"bg-[{theme.GREEN}] text-black hover:bg-[{theme.HOVER_GREEN}]"

_CIRCULAR_BASE = (
    "grid place-items-center rounded-full w-9 h-9 transition-colors " + _DARK_VARIANT
)

_ROW_CLASSES = (
    "grid grid-cols-1 md:grid-cols-[minmax(0,2fr)_1fr_1fr_auto] items-center "
    "gap-3 px-4 py-3 rounded-[8px] "
    f"bg-[{theme.SURFACE}] hover:bg-[{theme.SURFACE_MID}] transition-colors"
)


def _submit_pill(text: str, *, variant: str = "dark") -> Element:
    """type=submit pill (pill_button hardcodes type=button, which never submits)."""
    variant_classes = {
        "danger": _DANGER_VARIANT,
        "green": _GREEN_VARIANT,
    }.get(variant, _DARK_VARIANT)
    return button({"type": "submit", "class": _PILL_BASE + " " + variant_classes})[text]


def _field(text: str, control: Node) -> Element:
    """Visible label wrapping its control (implicit label association)."""
    return label({"class": "flex flex-col gap-2"})[label_text(text), control]


def _type_badge(row_type: str) -> Node:
    """Type chip: local blue, remote white, unknown gray (always with text)."""
    if row_type == "local":
        return badge("local", tone="blue")
    if row_type == "remote":
        return badge("remote", tone="white")
    return badge("unknown", tone="gray")


def _tools_badge(count: int) -> Node:
    """Gray tool-count badge with tabular numerals."""
    return span({"class": "tabular inline-flex"})[badge(f"{count} tools", tone="gray")]


def _inspect_anchor(name: str) -> Element:
    """Circular inspect link (icon-only, titled)."""
    return a(
        {
            "href": f"/admin/servers/{name}",
            "class": _CIRCULAR_BASE,
            "title": "Inspect",
            "aria-label": "Inspect",
        }
    )[icon_eye()]


def server_grid(rows: list[ServerRow]) -> Node:
    """INNER content for #server-grid: row elements or an empty state."""
    if not rows:
        return empty_state(
            "No servers yet.",
            "Add your first MCP server — local commands respect the allow-list (Policy page).",
        )
    return div({"class": "flex flex-col gap-2"})[[server_row(row) for row in rows]]


def server_row(row: ServerRow) -> Element:
    """One id-bearing row element (outerHTML swap target for row actions)."""
    row_classes = _ROW_CLASSES + (" opacity-60" if not row.enabled else "")
    actions = div({"class": "flex items-center gap-2 justify-end"})[
        pill_button(
            "Disable" if row.enabled else "Enable",
            variant="dark" if row.enabled else "outline",
            hx={
                "hx-patch": f"/admin/partials/servers/{row.name}/enabled",
                "hx-target": f"#row-{row.name}",
                "hx-swap": "outerHTML",
            },
        ),
        _inspect_anchor(row.name),
        circular_button(
            icon_refresh(),
            title="Refresh",
            hx={
                "hx-post": f"/admin/partials/servers/{row.name}/refresh",
                "hx-target": f"#row-{row.name}",
                "hx-swap": "outerHTML",
            },
        ),
        circular_button(
            icon_key(),
            title="Authenticate",
            hx={
                "hx-post": f"/admin/partials/servers/{row.name}/auth",
                "hx-target": f"#row-{row.name}",
                "hx-swap": "outerHTML",
            },
        )
        if row.has_oauth
        else None,
        circular_button(
            icon_trash(),
            variant="danger",
            title="Remove",
            hx={
                "hx-delete": f"/admin/partials/servers/{row.name}",
                "hx-target": "#server-grid",
                "hx-swap": "innerHTML",
                "hx-confirm": f"Remove {row.name} and its stored OAuth tokens?",
            },
        ),
    ]
    return div({"id": f"row-{row.name}", "class": row_classes})[
        div({"class": "flex flex-col min-w-0"})[
            div({"class": "flex items-center gap-2 min-w-0"})[
                a(
                    {
                        "href": f"/admin/servers/{row.name}",
                        "class": (
                            f"text-[16px] font-bold text-[{theme.TEXT}] truncate hover:underline"
                        ),
                    }
                )[row.name],
                badge("disabled", tone="gray") if not row.enabled else None,
                span({"class": (f"text-[12px] text-[{theme.TEXT_SILVER}] truncate")})[
                    row.detail
                ],
            ],
            span(
                {
                    "class": (f"text-[12px] text-[{theme.TEXT_SILVER}] truncate"),
                    "title": row.description.splitlines()[0].strip()
                    if row.description.strip()
                    else "",
                }
            )[
                row.description.splitlines()[0].strip()[:120]
                if row.description.strip()
                else ""
            ]
            if row.description.strip()
            else None,
        ],
        div({"class": "min-w-0"})[_type_badge(row.type)],
        div({"class": "min-w-0"})[_tools_badge(row.tool_count)],
        actions,
    ]


def servers_content(*, q: str, rows: list[ServerRow], allow_env_value: str) -> Node:
    """Full Servers page: header actions, add modal and the live grid."""
    header = div({"class": "flex flex-wrap items-end justify-between gap-4"})[
        section_title("Servers", sub=f"{len(rows)} connected"),
        div(
            {
                "class": (
                    "flex flex-col gap-3 w-full md:w-auto md:flex-row md:items-end "
                    "md:flex-wrap"
                )
            }
        )[
            label({"class": "flex flex-col gap-1 w-full md:w-[320px]"})[
                label_text("Search"),
                search_input(
                    hx={
                        "hx-get": "/admin/partials/servers",
                        "hx-trigger": "keyup changed delay:300ms, search",
                        "hx-target": "#server-grid",
                        "hx-swap": "innerHTML",
                    }
                ),
            ],
            div({"class": "flex gap-3 w-full md:w-auto shrink-0"})[
                div({"class": "flex flex-1 md:flex-none"})[
                    pill_button(
                        "Refresh all",
                        icon=icon_refresh(),
                        cls="flex-1 justify-center md:flex-none",
                        hx={
                            "hx-post": "/admin/partials/refresh",
                            "hx-target": "#server-grid",
                            "hx-swap": "innerHTML",
                        },
                    )
                ],
                modal(
                    "add-server-modal",
                    "Add server",
                    add_server_form(csrf_token="", allow_env_value=allow_env_value),
                    cls="flex-1 md:flex-none",
                    trigger_cls="w-full justify-center md:w-auto",
                ),
            ],
        ],
    ]
    if q.strip() and not rows:
        grid_inner: Node = empty_state(
            "No servers match.",
            "Clear the search or add a new MCP server.",
        )
    else:
        grid_inner = server_grid(rows)
    return div({"class": "flex flex-col gap-5"})[
        header,
        div({"id": "server-grid", "class": "flex flex-col gap-2"})[grid_inner],
    ]


def add_server_form(
    *,
    csrf_token: str,
    allow_env_value: str,
    modal_id: str = "add-server-modal",
    oob_reset: bool = False,
) -> Node:
    """Modal add form: shared fields plus Remote and Local sections that
    show/hide off `select[name=type]` via the `:has()` rules in layout.

    The form owns `id="add-server-form"` so a successful add can OOB-swap a
    fresh copy (clearing user input) while error responses leave the typed
    values untouched."""
    hx = dict(_ADD_HX)
    if oob_reset:
        hx["hx-swap-oob"] = "true"
    return form({"id": "add-server-form", "class": "flex flex-col gap-5", **hx})[
        input(type="hidden", name="_csrf", value=csrf_token),
        div({"class": "flex items-center justify-between gap-3"})[
            feature_heading("Add MCP server"),
            modal_close_x(modal_id),
        ],
        div({"class": "grid md:grid-cols-2 gap-4"})[
            _field("Name", text_input("name", required=True, placeholder="my-server")),
            _field(
                "Type",
                select(
                    "type",
                    [("Local", "local"), ("Remote", "remote")],
                    selected="local",
                ),
            ),
        ],
        _field(
            "Description",
            text_input("description", placeholder="What this server is for"),
        ),
        p({"class": (f"text-[12px] text-[{theme.TEXT_SILVER}]")})[
            "Fill the section matching the type."
        ],
        div({"class": "flex flex-col gap-4", "data-type-section": "remote"})[
            feature_heading("Remote"),
            _field("URL", text_input("url", placeholder="https://api.example.com/mcp")),
            _field(
                "Headers",
                textarea("headers", placeholder="KEY=VALUE per line", rows=3),
            ),
            div({"class": "grid md:grid-cols-2 gap-4"})[
                _field("OAuth client ID", text_input("oauth_client_id")),
                _field(
                    "OAuth client secret",
                    text_input("oauth_client_secret", input_type="password"),
                ),
            ],
            div({"class": "grid md:grid-cols-2 gap-4"})[
                _field("OAuth scope", text_input("oauth_scope")),
                _field("OAuth port", text_input("oauth_port", value="8989")),
            ],
        ],
        div({"class": "flex flex-col gap-4", "data-type-section": "local"})[
            feature_heading("Local"),
            div({"class": "flex flex-col gap-2"})[
                _field(
                    "Command",
                    text_input("command", placeholder="npx -y my-mcp"),
                ),
                span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}]"})[
                    f"Allowed binaries: {allow_env_value}"
                ],
            ],
            _field(
                "Working directory", text_input("cwd", placeholder="/absolute/path")
            ),
            _field(
                "Environment", textarea("env", placeholder="KEY=VALUE per line", rows=3)
            ),
        ],
        div({"class": "grid md:grid-cols-2 gap-4"})[
            _field("Tools", text_input("tools", value="*")),
            _field("Timeout (ms)", text_input("timeout", value="5000")),
        ],
        div({"class": "flex flex-wrap gap-6"})[
            checkbox("enabled", checked=True, text="Enabled"),
            checkbox("retry_on_transport_error", text="Retry once on transport error"),
        ],
        div({"class": "flex items-center justify-end gap-3"})[
            pill_button("Add server", variant="green", hx=_ADD_HX),
        ],
    ]


def server_detail_content(
    *,
    row: ServerRow,
    config: MCPServerConfig,
    pyi: str,
    tools: list[ToolInfo],
    csrf_token: str,
    name: str,
    allow_env_value: str = "",
) -> Node:
    """Full detail page: header, config card (masked headers) and tools column."""
    header = div({"class": "flex flex-col gap-2"})[
        a(
            {
                "href": "/admin/servers",
                "class": (
                    f"inline-flex items-center gap-1.5 text-[12px] text-[{theme.TEXT_SILVER}] "
                    f"hover:text-[{theme.TEXT}] transition-colors"
                ),
            }
        )[span({"class": "inline-flex rotate-180"})[icon_chevron(14)], "Servers"],
        div({"class": "flex flex-wrap items-center gap-3"})[
            section_title(row.name, sub=f"{row.type} · {row.tool_count} tools"),
            badge(
                "enabled" if row.enabled else "disabled",
                tone="green" if row.enabled else "gray",
            ),
        ],
    ]
    left = card(
        feature_heading("Config"),
        div({"id": "detail-config"})[
            detail_config_inner(
                row=row,
                config=config,
                name=name,
                csrf_token=csrf_token,
                allow_env_value=allow_env_value,
            )
        ],
    )
    right = div({"class": "flex flex-col gap-4"})[
        card(
            div({"id": "detail-tools"})[tools_panel(tools, name=row.name)],
        ),
        card(
            feature_heading("Signatures"),
            div({"class": "mt-3"})[
                code_block(pyi, cls="max-h-[300px] overflow-y-auto")
            ],
        ),
    ]
    return div({"class": "flex flex-col gap-5"})[
        header,
        div({"class": "grid lg:grid-cols-[320px_minmax(0,1fr)] gap-4"})[left, right],
    ]


def _tool_lines(tools: list[ToolInfo]) -> Node:
    """Compact name/description lines for the tools panel list."""
    if not tools:
        return span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}]"})[
            "No tools yet — run Refresh to discover them."
        ]
    return div({"class": "flex flex-col"})[
        [
            div({"class": "flex justify-between gap-3 py-1"})[
                span({"class": f"text-[14px] font-bold text-[{theme.TEXT}] shrink-0"})[
                    tool.name
                ],
                span(
                    {
                        "class": (
                            f"text-[12px] text-[{theme.TEXT_SILVER}] truncate text-right"
                        )
                    }
                )[tool.description or "…"],
            ]
            for tool in tools
        ]
    ]


def detail_config_inner(
    *,
    row: ServerRow,
    config: MCPServerConfig,
    name: str,
    csrf_token: str,
    allow_env_value: str = "",
) -> list[Node]:
    """Inner content of #detail-config: facts, actions and the edit form.

    Re-rendered wholesale by `PUT /admin/partials/servers/{name}/config`
    (fresh HTML replaces the open edit form, closing it without JS)."""
    config_rows: list[Node] = [
        kv_row("Type", _type_badge(row.type)),
        kv_row(
            "Status",
            badge(
                "enabled" if row.enabled else "disabled",
                tone="green" if row.enabled else "gray",
            ),
        ),
        kv_row(
            "Description",
            span({"class": "truncate", "title": row.description or ""})[
                row.description.splitlines()[0].strip()[:200]
                if row.description.strip()
                else "—"
            ],
        ),
        kv_row("Timeout", span({"class": "tabular"})[f"{config.timeout} ms"]),
        kv_row("Tools filter", ", ".join(config.tools_to_execute) or "*"),
    ]
    if config.type == "local":
        config_rows.append(kv_row("Command", " ".join(config.command or [])))
        if config.cwd:
            config_rows.append(kv_row("Cwd", config.cwd))
    else:
        config_rows.append(kv_row("URL", config.url or ""))
        for header_key in sorted(config.headers or {}):
            config_rows.append(
                kv_row(header_key, "\u2022\u2022\u2022\u2022\u2022\u2022")
            )
    config_rows.append(
        kv_row(
            "OAuth",
            badge("configured", tone="green")
            if config.oauth not in (None, False)
            else badge("none", tone="gray"),
        )
    )
    if config.resolved_transport:
        config_rows.append(
            kv_row(
                "Resolved transport", badge(str(config.resolved_transport), tone="blue")
            )
        )
    edit = _edit_config_details(
        name=name,
        config=config,
        csrf_token=csrf_token,
        allow_env_value=allow_env_value,
    )
    actions = div({"class": "mt-4 flex flex-wrap gap-2"})[
        pill_button(
            "Refresh",
            icon=icon_refresh(),
            hx={
                "hx-post": f"/admin/partials/servers/{row.name}/refresh",
                "hx-swap": "none",
            },
        ),
        pill_button(
            "Authenticate",
            icon=icon_key(),
            hx={
                "hx-post": f"/admin/partials/servers/{row.name}/auth",
                "hx-swap": "none",
            },
        )
        if row.has_oauth
        else None,
        pill_button(
            "Remove",
            variant="danger",
            icon=icon_trash(),
            hx={
                "hx-delete": f"/admin/partials/servers/{row.name}",
                "hx-swap": "none",
                "hx-push-url": "/admin/servers",
                "hx-confirm": f"Remove {row.name} and its stored OAuth tokens?",
            },
        ),
        edit,
    ]
    return [div({"class": "mt-3 flex flex-col"})[config_rows], actions]


def _edit_config_details(
    *,
    name: str,
    config: MCPServerConfig,
    csrf_token: str,
    allow_env_value: str = "",
) -> Element:
    """Zero-JS disclosure form for config properties (never the tool list \u2014
    tools sync only on add/refresh). Type is immutable; secret fields are
    write-only: blank keeps the stored value."""
    from mcp_gway.admin.icons import icon_pencil

    tools_filter = ", ".join(config.tools_to_execute) or "*"
    fields: list[Node] = [
        div({"class": "grid md:grid-cols-2 gap-4"})[
            _field("Timeout (ms)", text_input("timeout", value=str(config.timeout))),
            _field("Tools filter", text_input("tools_filter", value=tools_filter)),
        ],
        _field(
            "Description",
            text_input(
                "description",
                value=str(getattr(config, "description", "") or ""),
                placeholder="What this server is for — blank keeps current",
            ),
        ),
    ]
    if config.type == "local":
        fields.append(
            div({"class": "flex flex-col gap-4"})[
                _field(
                    "Command",
                    text_input("command", value=" ".join(config.command or [])),
                ),
                _field(
                    "Working directory",
                    text_input(
                        "cwd", value=config.cwd or "", placeholder="/absolute/path"
                    ),
                ),
                _field(
                    "Environment",
                    textarea(
                        "environment",
                        placeholder="KEY=VALUE per line \u2014 blank keeps current",
                        rows=3,
                    ),
                ),
                span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}]"})[
                    f"Allowed binaries: {allow_env_value}"
                ],
            ]
        )
    else:
        fields.append(
            div({"class": "flex flex-col gap-4"})[
                _field("URL", text_input("url", value=config.url or "")),
                _field(
                    "Headers",
                    textarea(
                        "headers",
                        placeholder="KEY=VALUE per line \u2014 blank keeps current",
                        rows=3,
                    ),
                ),
                div({"class": "grid md:grid-cols-2 gap-4"})[
                    _field(
                        "OAuth client ID",
                        text_input(
                            "oauth_client_id", placeholder="blank keeps current"
                        ),
                    ),
                    _field(
                        "OAuth client secret",
                        text_input(
                            "oauth_client_secret",
                            input_type="password",
                            placeholder="blank keeps current",
                        ),
                    ),
                ],
                _field(
                    "OAuth scope",
                    text_input("oauth_scope", placeholder="blank keeps current"),
                ),
            ]
        )
    return modal(
        "edit-config-modal",
        "Edit config",
        form(
            {
                "class": "flex flex-col gap-5",
                "method": "post",
                "action": f"/admin/partials/servers/{name}/config",
                "hx-put": f"/admin/partials/servers/{name}/config",
                "hx-target": "#detail-config",
                "hx-swap": "innerHTML",
                "hx-disabled-elt": "this",
            }
        )[
            input(type="hidden", name="_csrf", value=csrf_token),
            div({"class": "flex items-center justify-between gap-3"})[
                feature_heading("Edit config"),
                modal_close_x("edit-config-modal"),
            ],
            *fields,
            checkbox("enabled", checked=bool(config.enabled), text="Enabled"),
            span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}]"})[
                "Secrets (headers, OAuth) are write-only \u2014 blank fields keep "
                "current values. Tools sync on add/refresh only."
            ],
            div({"class": "flex justify-end"})[
                _submit_pill("Save config", variant="green")
            ],
        ],
        trigger_variant="dark",
        trigger_icon=icon_pencil(),
    )


def tools_panel(tools: list[ToolInfo], *, name: str = "") -> Node:
    """INNER content for #detail-tools (with name) or #detail-tools-list (without).

    Read-only: discovered tools sync exclusively when servers are added or
    refreshed (no web mutation path \u2014 CLI `update` stays canonical). With
    `name`, the list wrapper polls every 5s so background refreshes show up
    without a manual reload."""
    lines = _tool_lines(tools)
    if not name:
        return lines
    return div[
        div({"class": "flex items-baseline justify-between gap-3"})[
            feature_heading("Tools"),
            span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}]"})[
                "synced on add/refresh"
            ],
        ],
        div(
            {
                "id": "detail-tools-list",
                "hx-get": f"/admin/partials/servers/{name}/tools",
                "hx-trigger": "every 5s",
                "hx-swap": "innerHTML",
            }
        )[lines],
    ]
