"""Code Mode page — stub explorer, output surface and the three meta-tool forms."""

from __future__ import annotations

from htpy import Node, div, form, input, label, span

from mcp_gway.admin import theme
from mcp_gway.admin.components import (
    card,
    code_block,
    feature_heading,
    label_text,
    pill_button,
    section_title,
    text_input,
    textarea,
)
from mcp_gway.admin.icons import icon_refresh

_CM_HX: dict[str, str] = {
    "hx-post": "/admin/partials/codemode",
    "hx-target": "#cm-output",
    "hx-swap": "innerHTML",
}


def codemode_listing(listing: str) -> Node:
    """INNER content for #cm-list: the stub listing plus a reload pill."""
    return div({"class": "flex flex-col gap-3"})[
        code_block(listing),
        div({"class": "flex justify-end"})[
            pill_button(
                "Reload",
                icon=icon_refresh(),
                hx={
                    "hx-get": "/admin/partials/codemode/list",
                    "hx-target": "#cm-list",
                    "hx-swap": "innerHTML",
                },
            )
        ],
    ]


def codemode_output(text: str) -> Node:
    """INNER content for #cm-output: a single code block."""
    return code_block(text)


def _field(text: str, control: Node) -> Node:
    """Visible label wrapping its control (implicit label association)."""
    return label({"class": "flex flex-col gap-2"})[label_text(text), control]


def _meta_form(csrf_token: str, mode: str, *fields: Node, submit: Node) -> Node:
    """Shared Code Mode form: CSRF + mode, caller fields, submit row."""
    return form({"class": "flex flex-col gap-4", **_CM_HX})[
        input(type="hidden", name="_csrf", value=csrf_token),
        input(type="hidden", name="mode", value=mode),
        *fields,
        div({"class": "flex justify-end"})[submit],
    ]


def tools_content(*, listing: str, csrf_token: str) -> Node:
    """Full Code Mode page: explorer grid, output panel and the three forms."""
    explorer = card(
        feature_heading("Stub explorer"),
        div({"class": "mt-3", "id": "cm-list"})[codemode_listing(listing)],
    )
    output = card(
        div({"id": "cm-output", "role": "status", "aria-live": "polite"})[
            codemode_output("Run a snippet or open a stub to see output here.")
        ],
        cls="lg:col-span-2",
    )
    read_card = card(
        feature_heading("Read stub"),
        div({"class": "mt-3"})[
            _meta_form(
                csrf_token,
                "read",
                _field(
                    "File name",
                    text_input("fileName", placeholder="servers/filesystem.pyi"),
                ),
                submit=pill_button("Open", hx=_CM_HX),
            )
        ],
    )
    docs_card = card(
        feature_heading("Tool docs"),
        div({"class": "mt-3"})[
            _meta_form(
                csrf_token,
                "docs",
                _field("Server", text_input("server", placeholder="Filesystem")),
                _field("Tool", text_input("tool", placeholder="read_file")),
                submit=pill_button("Docs", hx=_CM_HX),
            )
        ],
    )
    execute_card = card(
        feature_heading("Execute"),
        div({"class": "mt-3 flex flex-col gap-3"})[
            _meta_form(
                csrf_token,
                "execute",
                _field(
                    "Starlark code",
                    textarea(
                        "code",
                        placeholder='result = Filesystem.read_file(path=".")',
                        rows=5,
                    ),
                ),
                submit=pill_button("Run", variant="green", hx=_CM_HX),
            ),
            span({"class": f"text-[12px] text-[{theme.TEXT_SILVER}]"})[
                "Starlark: no imports, no try/except, fresh scope per call."
            ],
        ],
    )
    return div({"class": "flex flex-col gap-5"})[
        section_title("Code Mode", sub="list → read → docs → execute, in-process"),
        div({"class": "grid lg:grid-cols-2 gap-4"})[explorer, output],
        div({"class": "grid md:grid-cols-2 lg:grid-cols-3 gap-4"})[
            read_card,
            docs_card,
            execute_card,
        ],
    ]
