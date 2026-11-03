"""Admin auto-refresh interval — one source of truth for every polling surface.

The dashboard polls itself with htmx. The cadence is a single integer number of
seconds resolved once at serve startup, so the status footer, the server list,
and the tools panel can never drift apart. ``0`` disables polling: the UI keeps
working, it just stops refreshing on its own.
"""

from __future__ import annotations

import os

ADMIN_REFRESH_ENV = "MCP_GWAY_ADMIN_REFRESH_SECONDS"
DEFAULT_ADMIN_REFRESH_SECONDS = 5


def resolve_refresh_seconds(raw: str | None = None) -> int:
    """Parse the refresh interval; blank means the default, invalid raises.

    The caller (serve startup) turns ``ValueError`` into exit code 2 so a typo
    never silently runs the dashboard on an unexpected cadence.
    """
    value = os.environ.get(ADMIN_REFRESH_ENV) if raw is None else raw
    if value is None or not str(value).strip():
        return DEFAULT_ADMIN_REFRESH_SECONDS
    try:
        seconds = int(str(value).strip())
    except ValueError:
        raise ValueError(
            f"{ADMIN_REFRESH_ENV} must be an integer number of seconds, got {value!r}"
        ) from None
    if seconds < 0:
        raise ValueError(f"{ADMIN_REFRESH_ENV} must be >= 0, got {seconds}")
    return seconds


def refresh_trigger(seconds: int) -> dict[str, str]:
    """htmx trigger attributes; empty when polling is disabled."""
    if seconds <= 0:
        return {}
    return {"hx-trigger": f"every {seconds}s"}


def format_interval(seconds: int) -> str:
    """Human interval for visible copy: 5 -> ``5s``, 600 -> ``10m``."""
    if seconds >= 60 and seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"


def refresh_caption(seconds: int) -> str:
    if seconds <= 0:
        return "auto-refresh off"
    return f"polls every {format_interval(seconds)}"
