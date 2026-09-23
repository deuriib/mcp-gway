"""Authored SVG icon system — one stroke (1.75), one grammar, currentColor.

Craft-floor mandate: icons are drawn, never glyph/emoji stand-ins. Every icon
is a 24x24 stroke path set using `stroke="currentColor"` so it inherits text
color from its container. `play` is a filled glyph (legacy mark, unused by the
shell); `hub` is the brand mark (gateway of connected servers).
"""

from __future__ import annotations

from markupsafe import Markup

_STROKE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
    'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" '
    'focusable="false">{body}</svg>'
)

_FILLED = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
    'viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" '
    'focusable="false">{body}</svg>'
)


def _stroke(body: str, size: int) -> Markup:
    return Markup(_STROKE.format(size=size, body=body))


def _filled(body: str, size: int) -> Markup:
    return Markup(_FILLED.format(size=size, body=body))


def icon_play(size: int = 16) -> Markup:
    return _filled('<path d="M7 4.5v15l13-7.5z"/>', size)


def icon_hub(size: int = 16) -> Markup:
    """Brand mark — center gateway hub linked to three satellite nodes."""
    return _stroke(
        '<circle cx="12" cy="12" r="3"/>'
        '<circle cx="12" cy="4.5" r="1.75"/>'
        '<circle cx="5" cy="16.5" r="1.75"/>'
        '<circle cx="19" cy="16.5" r="1.75"/>'
        '<path d="M12 6.4V8.6M9.6 13.5l-2.9 1.9M14.4 13.5l2.9 1.9"/>',
        size,
    )


def icon_pencil(size: int = 16) -> Markup:
    return _stroke(
        '<path d="M4 20h4L18.5 9.5a2.12 2.12 0 0 0-3-3L5 17v3z"/>'
        '<path d="M13.5 6.5l4 4"/>',
        size,
    )


def icon_menu(size: int = 16) -> Markup:
    return _stroke('<path d="M4 7h16M4 12h16M4 17h16"/>', size)


def icon_plus(size: int = 16) -> Markup:
    return _stroke('<path d="M12 5v14M5 12h14"/>', size)


def icon_refresh(size: int = 16) -> Markup:
    return _stroke(
        '<path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/>'
        '<path d="M21 3v5h-5"/>'
        '<path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/>'
        '<path d="M3 21v-5h5"/>',
        size,
    )


def icon_trash(size: int = 16) -> Markup:
    return _stroke(
        '<path d="M3 6h18"/>'
        '<path d="M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6"/>'
        '<path d="M19 6l-.9 13.1A2 2 0 0 1 16.1 21H7.9a2 2 0 0 1-2-1.9L5 6"/>'
        '<path d="M10 11v5M14 11v5"/>',
        size,
    )


def icon_search(size: int = 16) -> Markup:
    return _stroke('<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>', size)


def icon_check(size: int = 16) -> Markup:
    return _stroke('<path d="M20 6L9 17l-5-5"/>', size)


def icon_chevron(size: int = 16) -> Markup:
    return _stroke('<path d="M9 18l6-6-6-6"/>', size)


def icon_close(size: int = 16) -> Markup:
    return _stroke('<path d="M18 6L6 18M6 6l12 12"/>', size)


def icon_overview(size: int = 16) -> Markup:
    return _stroke(
        '<rect x="3" y="3" width="8" height="8" rx="1.5"/>'
        '<rect x="13" y="3" width="8" height="5" rx="1.5"/>'
        '<rect x="13" y="10" width="8" height="11" rx="1.5"/>'
        '<rect x="3" y="13" width="8" height="8" rx="1.5"/>',
        size,
    )


def icon_server(size: int = 16) -> Markup:
    return _stroke(
        '<rect x="3" y="4" width="18" height="7" rx="1.5"/>'
        '<rect x="3" y="13" width="18" height="7" rx="1.5"/>'
        '<path d="M7 7.5h.01M7 16.5h.01"/>',
        size,
    )


def icon_terminal(size: int = 16) -> Markup:
    return _stroke('<path d="M5 7l5 5-5 5"/><path d="M13 17h6"/>', size)


def icon_activity(size: int = 16) -> Markup:
    return _stroke('<path d="M22 12h-4l-3 8L9 4l-3 8H2"/>', size)


def icon_shield(size: int = 16) -> Markup:
    return _stroke(
        '<path d="M12 3l7 3v5c0 4.5-3 8.4-7 10-4-1.6-7-5.5-7-10V6l7-3z"/>',
        size,
    )


def icon_eye(size: int = 16) -> Markup:
    return _stroke(
        '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/>'
        '<circle cx="12" cy="12" r="3"/>',
        size,
    )


def icon_key(size: int = 16) -> Markup:
    return _stroke(
        '<circle cx="8" cy="15" r="4"/>'
        '<path d="M11 12l9-9M17 6l2.5 2.5M14.5 8.5L17 11"/>',
        size,
    )


def icon_code(size: int = 16) -> Markup:
    return _stroke('<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M13.5 5l-3 14"/>', size)


def icon_dot(size: int = 16) -> Markup:
    return _filled('<circle cx="12" cy="12" r="5"/>', size)
