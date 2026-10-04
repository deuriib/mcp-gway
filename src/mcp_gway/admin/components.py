"""Reusable htpy components for the admin dashboard.

Every component is a plain function returning an htpy element, styled with
Tailwind (CDN) utility classes composed from `theme.py` tokens. htmx
attributes pass through the `hx` dict so partials stay declarative.
"""

from __future__ import annotations

from typing import Any

from htpy import (
    Element,
    Node,
    a,
    button,
    div,
    footer,
    input,
    label,
    p,
    pre,
    span,
)

from mcp_gway.admin import theme
from mcp_gway.admin.icons import icon_close, icon_plus, icon_search

HxAttrs = dict[str, str]

_VARIANTS: dict[str, str] = {
    "dark": f"bg-[{theme.SURFACE_MID}] text-[{theme.TEXT}] hover:bg-[{theme.HOVER_SURFACE}]",
    "green": f"bg-[{theme.GREEN}] text-black hover:bg-[{theme.HOVER_GREEN}] font-bold",
    "outline": (
        f"bg-transparent text-[{theme.TEXT}] border border-[{theme.BORDER_LIGHT}] "
        "hover:bg-white/10 hover:border-white"
    ),
    "light": f"bg-[{theme.LIGHT_SURFACE}] text-[{theme.SURFACE}] hover:bg-white",
    "danger": f"bg-[{theme.NEGATIVE}]/15 text-[{theme.NEGATIVE}] hover:bg-[{theme.NEGATIVE}]/25",
}

_TONES: dict[str, str] = {
    "green": f"bg-[{theme.GREEN}]/15 text-[{theme.GREEN}]",
    "red": f"bg-[{theme.NEGATIVE}]/15 text-[{theme.NEGATIVE}]",
    "orange": f"bg-[{theme.WARNING}]/15 text-[{theme.WARNING}]",
    "blue": f"bg-[{theme.ANNOUNCEMENT}]/15 text-[{theme.ANNOUNCEMENT}]",
    "gray": f"bg-[{theme.CARD}] text-[{theme.TEXT_SILVER}]",
    "white": f"bg-white/10 text-[{theme.TEXT}]",
}

_TONE_TEXT: dict[str, str] = {
    "white": theme.TEXT,
    "green": theme.GREEN,
    "orange": theme.WARNING,
    "red": theme.NEGATIVE,
    "blue": theme.ANNOUNCEMENT,
    "silver": theme.TEXT_SILVER,
}


def _attrs(hx: HxAttrs | None, extra: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if hx:
        merged.update(hx)
    merged.update({k: v for k, v in extra.items() if v is not None})
    return merged


def pill_button(
    text: str,
    *,
    hx: HxAttrs | None = None,
    variant: str = "dark",
    icon: Node = None,
    disabled: bool = False,
    cls: str = "",
) -> Element:
    """Full-pill button (DESIGN.md section 4). Uppercase + tracking system."""
    classes = (
        "inline-flex items-center gap-2 rounded-[9999px] px-4 py-2 text-[14px] "
        "font-bold uppercase tracking-[1.4px] leading-none transition-colors "
        "disabled:opacity-50 disabled:pointer-events-none cursor-pointer "
        + _VARIANTS.get(variant, _VARIANTS["dark"])
        + (" " + cls if cls else "")
    )
    attrs = _attrs(hx, {"type": "button", "disabled": disabled})
    return button({"class": classes}, **attrs)[icon, span[text]]


def circular_button(
    content: Node,
    *,
    hx: HxAttrs | None = None,
    variant: str = "dark",
    title: str = "",
    cls: str = "",
) -> Element:
    """Circular control (50% radius) — row actions, icon-only (title = name)."""
    classes = (
        "grid place-items-center rounded-full w-9 h-9 transition-colors "
        "cursor-pointer disabled:opacity-50 "
        + _VARIANTS.get(variant, _VARIANTS["dark"])
        + (" " + cls if cls else "")
    )
    attrs = _attrs(hx, {"type": "button", "title": title, "aria-label": title})
    return button({"class": classes}, **attrs)[content]


def card(*children: Node, cls: str = "") -> Element:
    """Dark surface card: #181818, 8px radius, medium shadow on hover."""
    classes = (
        f"rounded-[8px] bg-[{theme.SURFACE}] p-5 transition-shadow "
        f"shadow-[{theme.SHADOW_MEDIUM}] " + cls
    )
    return div({"class": classes})[children]


def stat_card(
    label_text: str, value: str, *, tone: str = "white", hint: str = ""
) -> Element:
    """Overview metric tile — bold value, silver label, semantic tone."""
    tone_color = _TONE_TEXT.get(tone, theme.TEXT)
    return card(
        p(
            {
                "class": f"text-[12px] font-bold uppercase tracking-[1.4px] text-[{theme.TEXT_SILVER}]"
            }
        )[label_text],
        p(
            {
                "class": f"text-[24px] font-bold leading-none mt-2 tabular text-[{tone_color}]"
            }
        )[value],
        p({"class": f"text-[12px] text-[{theme.TEXT_SILVER}] mt-2"})[hint]
        if hint
        else None,
        cls="select-none",
    )


def badge(text: str, *, tone: str = "gray") -> Element:
    """Compact 10.5px badge — capitalize, minimal radius."""
    classes = (
        "inline-block rounded-[2px] px-2 py-0.5 text-[10.5px] font-semibold "
        "capitalize leading-[1.33] whitespace-nowrap "
        + _TONES.get(tone, _TONES["gray"])
    )
    return span({"class": classes})[text]


def section_title(text: str, *, sub: str = "") -> Element:
    """24px bold section title with optional silver subtitle."""
    return div({"class": "flex flex-col"})[
        p({"class": f"text-[24px] font-bold text-[{theme.TEXT}]"})[text],
        p({"class": f"text-[14px] text-[{theme.TEXT_SILVER}] mt-1"})[sub]
        if sub
        else None,
    ]


def feature_heading(text: str, *, cls: str = "") -> Element:
    """18px semibold feature heading (tight leading)."""
    return p(
        {"class": f"text-[18px] font-semibold leading-[1.3] text-[{theme.TEXT}] {cls}"}
    )[text]


def label_text(text: str) -> Element:
    return span(
        {
            "class": f"text-[12px] font-bold uppercase tracking-[1.4px] text-[{theme.TEXT_SILVER}]"
        }
    )[text]


_INPUT_BASE = (
    f"w-full rounded-[4px] bg-[{theme.SURFACE_MID}] px-4 py-3 text-[14px] text-[{theme.TEXT}] "
    f"placeholder-[{theme.TEXT_SILVER}] outline-none border-0"
)


def text_input(
    name: str,
    *,
    value: str = "",
    placeholder: str = "",
    input_type: str = "text",
    required: bool = False,
    hx: HxAttrs | None = None,
    cls: str = "",
) -> Element:
    """Inset-bordered text input (DESIGN.md inset border-shadow combo)."""
    attrs = _attrs(
        hx,
        {
            "type": input_type,
            "name": name,
            "value": value,
            "placeholder": placeholder,
            "required": required,
        },
    )
    return input(
        {
            "class": f"{_INPUT_BASE} {cls}",
            "style": f"box-shadow: {theme.INSET_BORDER};",
        },
        **attrs,
    )


def textarea(
    name: str,
    *,
    value: str = "",
    placeholder: str = "",
    rows: int = 6,
    cls: str = "",
) -> Element:
    from htpy import textarea as _textarea

    return _textarea(
        {
            "name": name,
            "rows": str(rows),
            "placeholder": placeholder,
            "class": f"{_INPUT_BASE} font-mono text-[12px] resize-y {cls}",
            "style": f"box-shadow: {theme.INSET_BORDER};",
        }
    )[value]


def select(name: str, options: list[tuple[str, str]], *, selected: str = "") -> Element:
    from htpy import option
    from htpy import select as _select

    return _select(
        {
            "name": name,
            "class": f"{_INPUT_BASE} cursor-pointer",
            "style": f"box-shadow: {theme.INSET_BORDER};",
        }
    )[[option(value=val, selected=(val == selected))[text] for text, val in options]]


def checkbox(name: str, *, checked: bool = False, text: str = "") -> Element:
    return label({"class": "flex items-center gap-3 cursor-pointer"})[
        input(
            type="checkbox",
            name=name,
            checked=checked,
            class_="w-4 h-4 accent-[#1ed760] cursor-pointer",
        ),
        span({"class": f"text-[14px] text-[{theme.TEXT}]"})[text or name],
    ]


def search_input(
    *,
    hx: HxAttrs | None = None,
    placeholder: str = "Search",
    name: str = "q",
) -> Element:
    """500px-radius pill search input, icon-aware padding (DESIGN.md section 4)."""
    attrs = _attrs(
        hx,
        {
            "type": "search",
            "name": name,
            "placeholder": placeholder,
            "aria-label": placeholder,
            "autocomplete": "off",
        },
    )
    return div({"class": "relative w-full"})[
        span(
            {
                "class": (
                    f"absolute left-4 top-1/2 -translate-y-1/2 text-[{theme.TEXT_SILVER}] "
                    "pointer-events-none"
                )
            }
        )[icon_search(16)],
        input(
            {
                "class": (
                    f"w-full rounded-[500px] bg-[{theme.SURFACE_MID}] text-[14px] "
                    f"text-[{theme.TEXT}] placeholder-[{theme.TEXT_SILVER}] pl-11 pr-6 py-3 "
                    "outline-none border-0"
                ),
                "style": f"box-shadow: {theme.INSET_BORDER};",
            },
            **attrs,
        ),
    ]


def code_block(text: str, *, cls: str = "") -> Element:
    """Monospace output surface for .pyi / metrics / Starlark results."""
    return pre(
        {
            "class": (
                f"rounded-[4px] bg-[{theme.CODE_BG}] text-[{theme.TEXT_SECONDARY}] text-[12px] "
                f"leading-[1.5] p-4 overflow-x-auto whitespace-pre-wrap break-words {cls}"
            )
        }
    )[text]


def empty_state(title: str, hint: str = "", *, action: Node = None) -> Element:
    """Empty state that teaches the interface and offers the next action."""
    return div({"class": "text-center py-12"})[
        p({"class": f"text-[16px] font-bold text-[{theme.TEXT}]"})[title],
        p(
            {
                "class": f"text-[14px] text-[{theme.TEXT_SILVER}] mt-2 max-w-[52ch] mx-auto leading-[1.5]"
            }
        )[hint]
        if hint
        else None,
        div({"class": "mt-5"})[action] if action else None,
    ]


def toast(message: str, *, tone: str = "white", oob: bool = True) -> Element:
    """Toast element. `oob=True` (default) — include alongside any swap; htmx
    routes it to #toast. `oob=False` — plain element for HX-Retarget responses
    targeting #toast, leaving the original swap target untouched.

    Success tones (green/blue/white) auto-dismiss after ~4s via an htmx
    `load delay` self-swap to the empty target — no inline script, so the
    strict CSP holds. Error tones (red/orange) persist until dismissed and
    carry a close control instead."""
    tone_class = _TONES.get(tone, _TONES["white"])
    persistent = tone in ("red", "orange")
    attrs: dict[str, str] = {
        "id": "toast",
        "role": "status",
        "class": (
            "fixed top-5 right-5 z-50 flex items-start gap-3 "
            "max-w-[min(420px,calc(100vw-2.5rem))] "
            "rounded-[8px] px-5 py-3 text-[14px] font-bold "
            f"shadow-[{theme.SHADOW_HEAVY}] {tone_class}"
        ),
    }
    if oob:
        attrs["hx-swap-oob"] = "true"
    if not persistent:
        attrs["hx-get"] = "/admin/partials/empty"
        attrs["hx-trigger"] = "load delay:4s"
        attrs["hx-swap"] = "outerHTML"
    close = button(
        {
            "type": "button",
            "class": (
                "grid shrink-0 place-items-center w-6 h-6 rounded-full "
                "cursor-pointer opacity-70 hover:opacity-100 transition-opacity"
            ),
            "hx-get": "/admin/partials/empty",
            "hx-target": "#toast",
            "hx-swap": "outerHTML",
            "aria-label": "Dismiss notification",
            "title": "Dismiss",
        }
    )[icon_close(14)]
    return div(attrs)[
        span({"class": "min-w-0 flex-1 break-words"})[message],
        close,
    ]


def toast_clear() -> Element:
    """Empty toast target — swapped in by /admin/partials/empty after the
    auto-dismiss delay or a manual dismiss."""
    return div({"id": "toast", "role": "status"})


def modal(
    modal_id: str,
    trigger_text: str,
    content: Node,
    *,
    trigger_variant: str = "green",
    trigger_cls: str = "",
    trigger_icon: Node = None,
    cls: str = "",
) -> Element:
    """Zero-JS dialog: a peer checkbox drives trigger, backdrop and close X —
    every `label[for=modal_id]` toggles the same input, so the X (and a
    backdrop click) close it. HTML only toggles <details> from its FIRST
    summary, which made summary-based X buttons inert. Closing after a
    mutation = OOB swap of the unchecked input (`modal_closed(modal_id)`).
    App code may open one modal per page (peer name is shared)."""
    trigger_classes = (
        "inline-flex items-center gap-2 rounded-[9999px] "
        "px-4 py-2 text-[14px] font-bold uppercase tracking-[1.4px] leading-none "
        "cursor-pointer "
        + _VARIANTS.get(trigger_variant, _VARIANTS["green"])
        + " peer-focus-visible/modal:outline peer-focus-visible/modal:outline-2 "
        + f"peer-focus-visible/modal:outline-offset-2 peer-focus-visible/modal:outline-[{theme.GREEN}] "
        + (" " + trigger_cls if trigger_cls else "")
    )
    return div({"class": ("relative " + cls).strip()})[
        input(type="checkbox", id=modal_id, class_="peer/modal sr-only"),
        label({"for": modal_id, "class": trigger_classes})[
            icon_plus() if trigger_icon is None else trigger_icon,
            span[trigger_text],
        ],
        div(
            {
                "class": (
                    "fixed inset-0 z-40 hidden peer-checked/modal:grid bg-black/70 "
                    "grid place-items-start justify-items-center pt-[8vh] px-4"
                )
            }
        )[
            label(
                {
                    "for": modal_id,
                    "class": "absolute inset-0 cursor-pointer",
                    "aria-label": "Close dialog",
                }
            ),
            div(
                {
                    "class": (
                        f"relative w-full max-w-[640px] max-h-[84vh] overflow-y-auto "
                        f"rounded-[8px] bg-[{theme.SURFACE}] p-6 shadow-[{theme.SHADOW_HEAVY}]"
                    )
                }
            )[content],
        ],
    ]


def modal_closed(modal_id: str) -> Element:
    """OOB element that replaces an open modal's checked peer input with an
    unchecked one (the swap closes the dialog)."""
    return input(
        {
            "type": "checkbox",
            "id": modal_id,
            "class": "peer/modal sr-only",
            "hx-swap-oob": "true",
        }
    )


def modal_close_x(modal_id: str, *, cls: str = "") -> Element:
    """Close button inside a modal body: `label[for=modal_id]` toggles the
    peer checkbox (a second <summary> never toggles — only the first does)."""
    return label(
        {
            "for": modal_id,
            "class": (
                "ml-auto grid place-items-center w-9 h-9 rounded-full cursor-pointer "
                f"bg-[{theme.SURFACE_MID}] text-[{theme.TEXT_SILVER}] "
                f"hover:text-[{theme.TEXT}] hover:bg-[{theme.HOVER_SURFACE}] transition-colors "
                + cls
            ),
            "aria-label": "Close dialog",
            "title": "Close",
        }
    )[icon_close()]


def nav_item(href: str, text: str, *, active: bool = False) -> Element:
    """Sidebar link — 14px, bold+white active / regular+silver inactive."""
    classes = "block rounded-[4px] px-3 py-2 text-[14px] transition-colors " + (
        f"font-bold text-[{theme.TEXT}] bg-[{theme.SURFACE_MID}]"
        if active
        else f"font-normal text-[{theme.TEXT_SILVER}] hover:text-[{theme.TEXT}] hover:bg-[{theme.SURFACE}]"
    )
    attrs: dict[str, Any] = {"href": href, "class": classes}
    if active:
        attrs["aria-current"] = "page"
    return a(attrs)[text]


def kv_row(key: str, value: Node) -> Element:
    """Detail list row — bold key left, value flush-right as a group.

    The value column is a right-justified flex row so badges, mono text and
    badge+detail combos all share one right edge (inline-block badges used
    to drift 8–14px short of the container edge)."""
    wrapped: Node = (
        span({"class": "min-w-0 break-all"})[value] if isinstance(value, str) else value
    )
    return div(
        {
            "class": (
                f"flex items-baseline justify-between gap-4 py-3 border-b "
                f"border-[{theme.BORDER}] last:border-0"
            )
        }
    )[
        span({"class": f"text-[14px] font-bold text-[{theme.TEXT}] shrink-0"})[key],
        span(
            {
                "class": (
                    "flex items-center justify-end gap-2 min-w-0 "
                    f"text-[14px] text-[{theme.TEXT_SILVER}]"
                )
            }
        )[wrapped],
    ]


def status_bar_footer(*children: Node, hx: HxAttrs | None = None) -> Element:
    """Now-playing-style fixed footer bar (polls via hx attrs)."""
    attrs = _attrs(hx, {})
    return footer(
        {
            "class": (
                f"shrink-0 min-h-14 flex flex-wrap items-center gap-x-6 gap-y-1 "
                f"px-5 py-1 bg-[{theme.SURFACE_MID}] "
                f"border-t border-[{theme.BORDER}] text-[12px] text-[{theme.TEXT_SILVER}]"
            ),
            **attrs,
        }
    )[children]
