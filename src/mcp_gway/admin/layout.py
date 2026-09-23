"""Base layout for the admin dashboard — Spotify-style shell.

Fixed dark sidebar + scrollable main + now-playing-style status footer.
`hx-boost` on `<body>` gives full-page progressive enhancement: plain links
work without JS, htmx swaps the body with JS. CSRF rides as `hx-headers`.
The <style> layer themes browser surfaces (selection, caret, scrollbars,
focus rings, tabular numerals, reduced motion) from the DESIGN.md palette.
"""

from __future__ import annotations

from htpy import (
    Node,
    aside,
    body,
    div,
    head,
    html,
    input,
    label,
    main,
    meta,
    nav,
    p,
    script,
    span,
    style,
    title,
)
from markupsafe import Markup

from mcp_gway.admin import theme
from mcp_gway.admin.components import nav_item, status_bar_footer, toast
from mcp_gway.admin.icons import icon_close, icon_hub, icon_menu

HTMX_SRC = "https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js"
HTMX_INTEGRITY = (
    "sha384-H5SrcfygHmAuTDZphMHqBJLc3FhssKjG7w/CeCpFReSfwBWDTKpkzPP8c+cLsK+V"
)
TAILWIND_SRC = "https://cdn.tailwindcss.com"

STYLE_CSS = f"""
html {{ color-scheme: dark; }}
::selection {{ background: {theme.GREEN}; color: #000000; }}
*:focus-visible {{ outline: 2px solid {theme.GREEN}; outline-offset: 2px; }}
input, textarea, select, button {{ font-family: inherit; caret-color: {theme.GREEN}; }}
:where(td, th, .tabular) {{ font-variant-numeric: tabular-nums; }}
* {{ scrollbar-width: thin; scrollbar-color: {theme.SCROLLBAR_THUMB} {theme.BG}; }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: {theme.BG}; }}
::-webkit-scrollbar-thumb {{
  background: {theme.SCROLLBAR_THUMB};
  border-radius: 9999px;
  border: 2px solid {theme.BG};
}}
::-webkit-scrollbar-thumb:hover {{ background: {theme.BORDER}; }}
summary::-webkit-details-marker {{ display: none; }}
form:has(select[name="type"] > option[value="remote"]:checked) [data-type-section="local"] {{
  display: none !important;
}}
form:has(select[name="type"] > option[value="local"]:checked) [data-type-section="remote"] {{
  display: none !important;
}}
.htmx-indicator {{ opacity: 0; transition: opacity 150ms ease-out; }}
.htmx-request .htmx-indicator, .htmx-request.htmx-indicator {{ opacity: 1; }}
.htmx-request {{ opacity: 0.65; transition: opacity 150ms ease-out; }}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }}
}}
"""

NAV_ITEMS: list[tuple[str, str, str]] = [
    ("overview", "Overview", "/"),
    ("servers", "Servers", "/admin/servers"),
    ("tools", "Tools", "/admin/tools"),
    ("observability", "Observability", "/admin/observability"),
    ("policy", "Policy", "/admin/policy"),
]


def _brand(*, cls: str = "", icon_size: int = 15) -> Node:
    """Logo block: green circle + hub mark + wordmark (shared by both shells)."""
    return div({"class": ("flex items-center gap-3 px-2 py-3 " + cls).strip()})[
        span(
            {
                "class": (
                    f"grid place-items-center w-8 h-8 rounded-full shrink-0 "
                    f"bg-[{theme.GREEN}] text-black"
                )
            }
        )[icon_hub(icon_size)],
        span(
            {
                "class": (
                    f"text-[14px] font-bold uppercase tracking-[1.4px] text-[{theme.TEXT}]"
                )
            }
        )["MCP Gateway"],
    ]


def _nav_links(active: str, *, cls: str = "") -> list[Node]:
    return [
        nav_item(href, text, active=(key == active)) for key, text, href in NAV_ITEMS
    ]


def mobile_nav(active: str, *, version: str) -> Node:
    """<md top bar + slide-in drawer. One peer checkbox drives it: the
    hamburger opens, the backdrop label and the X label both close — labels
    all toggle the same input (a second <summary> never would)."""
    close_label_cls = (
        "grid place-items-center w-9 h-9 rounded-full cursor-pointer "
        f"bg-[{theme.SURFACE_MID}] text-[{theme.TEXT_SILVER}] "
        f"hover:text-[{theme.TEXT}] hover:bg-[{theme.HOVER_SURFACE}] transition-colors"
    )
    burger_cls = (
        "grid place-items-center w-10 h-10 rounded-full cursor-pointer shrink-0 "
        f"bg-[{theme.SURFACE_MID}] text-[{theme.TEXT}] "
        f"hover:bg-[{theme.HOVER_SURFACE}] transition-colors "
        "peer-focus-visible/nav:outline peer-focus-visible/nav:outline-2 "
        f"peer-focus-visible/nav:outline-offset-2 peer-focus-visible/nav:outline-[{theme.GREEN}]"
    )
    return div(
        {
            "class": (
                f"md:hidden shrink-0 relative bg-[{theme.BG}] "
                f"border-b border-[{theme.BORDER}] px-3 py-2"
            )
        }
    )[
        input(type="checkbox", id="nav-drawer", class_="peer/nav sr-only"),
        div({"class": "flex items-center justify-between gap-3"})[
            _brand(cls="px-1 py-1"),
            label(
                {
                    "for": "nav-drawer",
                    "class": burger_cls,
                    "aria-label": "Open navigation",
                    "title": "Menu",
                }
            )[icon_menu()],
        ],
        div({"class": "hidden peer-checked/nav:block fixed inset-0 z-50"})[
            label(
                {
                    "for": "nav-drawer",
                    "class": "absolute inset-0 bg-black/60 cursor-pointer",
                    "aria-label": "Close navigation",
                }
            ),
            div(
                {
                    "class": (
                        f"absolute left-0 top-0 h-full w-72 max-w-[85vw] flex flex-col "
                        f"bg-[{theme.BG}] border-r border-[{theme.BORDER}] p-4 "
                        f"shadow-[{theme.SHADOW_HEAVY}] overflow-y-auto"
                    )
                }
            )[
                div({"class": "flex items-center justify-between gap-2"})[
                    _brand(cls="px-1 py-1"),
                    label(
                        {
                            "for": "nav-drawer",
                            "class": close_label_cls,
                            "aria-label": "Close navigation",
                            "title": "Close",
                        }
                    )[icon_close()],
                ],
                nav({"class": "flex flex-col gap-1 mt-3"})[_nav_links(active)],
                div({"class": "mt-auto flex flex-col gap-1 px-3 pt-6"})[
                    p(
                        {
                            "class": (
                                f"text-[10px] uppercase tracking-[2px] text-[{theme.TEXT_SILVER}]"
                            )
                        }
                    )["local-first"],
                    p({"class": f"text-[12px] font-bold text-[{theme.TEXT_SILVER}]"})[
                        f"v{version}"
                    ],
                ],
            ],
        ],
    ]


def sidebar(active: str, *, version: str) -> Node:
    """Desktop (md+) rail — mobile uses `mobile_nav`'s drawer instead."""
    return aside(
        {
            "class": (
                f"hidden shrink-0 md:flex md:w-60 md:flex-col md:items-stretch "
                f"md:overflow-y-auto bg-[{theme.BG}] "
                f"md:border-r md:border-[{theme.BORDER}] md:p-4"
            )
        }
    )[
        _brand(),
        nav({"class": "flex flex-col gap-1 mt-3 min-w-0"})[_nav_links(active)],
        div(
            {"class": "hidden md:mt-auto md:flex md:flex-col md:gap-1 md:px-3 md:pt-6"}
        )[
            p(
                {
                    "class": (
                        f"text-[10px] uppercase tracking-[2px] text-[{theme.TEXT_SILVER}]"
                    )
                }
            )["local-first"],
            p({"class": f"text-[12px] font-bold text-[{theme.TEXT_SILVER}]"})[
                f"v{version}"
            ],
        ],
    ]


def base_layout(
    *,
    page_title: str,
    active: str,
    csrf_token: str,
    content: Node,
    status_content: Node,
    version: str,
    notice: str = "",
) -> Node:
    """Full HTML document. `content` is page body; `status_content` seeds the
    polled footer (partial replaces it via innerHTML every 5s); `notice` seeds
    a server-rendered toast for no-JS redirect flows."""
    return html[
        head[
            meta(charset="utf-8"),
            meta(name="viewport", content="width=device-width, initial-scale=1"),
            title[f"MCP Gateway — {page_title}"],
            style[Markup(STYLE_CSS)],
            script(src=TAILWIND_SRC),
            script(
                src=HTMX_SRC,
                integrity=HTMX_INTEGRITY,
                crossorigin="anonymous",
                defer=True,
            ),
        ],
        body(
            {
                "class": f"h-screen flex flex-col bg-[{theme.BG}] text-[{theme.TEXT}] antialiased",
                "style": f"font-family: {theme.FONT_STACK}",
                "hx-boost": "true",
                "hx-headers": f'{{"X-CSRF-Token": "{csrf_token}"}}',
            }
        )[
            div({"class": "flex flex-col md:flex-row flex-1 overflow-hidden"})[
                mobile_nav(active, version=version),
                sidebar(active, version=version),
                main(
                    {"id": "main", "class": "flex-1 min-w-0 overflow-y-auto p-6 pb-8"}
                )[content],
            ],
            status_bar_footer(
                hx={
                    "hx-get": "/admin/partials/status",
                    "hx-trigger": "every 5s",
                    "hx-swap": "innerHTML",
                }
            )[status_content],
            div(id="toast")[toast(notice) if notice else None],
        ],
    ]
