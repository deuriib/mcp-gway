"""Starlette routes for the admin dashboard (HTML-first, htmx partials).

Full-page handlers return complete documents (hx-boost swaps the body);
partial handlers return inner HTML fragments. Mutations require a CSRF
token (body `hx-headers` or `_csrf` form field) and the admin surface is
loopback-only regardless of the gateway bind host (fail closed).
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import math
import os
import shlex
import sys
import time
from typing import Any

from markupsafe import Markup
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from mcp_gway import __version__
from mcp_gway.admin import data
from mcp_gway.admin.components import modal_closed, toast, toast_clear
from mcp_gway.admin.layout import base_layout
from mcp_gway.admin.pages.observability import metrics_fragment, observability_content
from mcp_gway.admin.pages.overview import overview_content
from mcp_gway.admin.pages.policy import policy_content, unrestricted_panel
from mcp_gway.admin.pages.servers import (
    detail_config_inner,
    server_detail_content,
    server_grid,
    server_row,
    servers_content,
    tools_panel,
)
from mcp_gway.admin.pages.status import status_fragment
from mcp_gway.admin.pages.tools import codemode_listing, codemode_output, tools_content
from mcp_gway.core.policy import home_dir
from mcp_gway.observability.health import check_registry, check_routes

CSRF_HEADER = "X-CSRF-Token"
_LOOPBACK = ("127.0.0.1", "::1", "localhost")
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_ADMIN_LOG = "mcp_gway.admin"

_EXEC_TIMEOUT_MIN = 0.1
_EXEC_TIMEOUT_MAX = 30.0
_EXEC_TIMEOUT_DEFAULT = 10.0

NOTICE_MESSAGES: dict[str, tuple[str, str]] = {
    "added": ("Server added.", "green"),
    "removed": ("Server removed.", "white"),
    "updated": ("Tools updated.", "green"),
    "refreshed": ("Refresh complete.", "green"),
    "policy-enabled": ("Break-glass marker created — active for 72h.", "orange"),
    "policy-disabled": ("Break-glass marker removed.", "white"),
    "auth-started": (
        "Authentication started — authorize in the opened browser window, then refresh.",
        "blue",
    ),
    "executed": ("Code executed.", "blue"),
    "exec-timeout": (
        "Code execution timed out — the snippet was abandoned.",
        "red",
    ),
    "config-unreadable": (
        "Config unreadable — a saved host may no longer resolve. Check the registry JSON.",
        "red",
    ),
    "config-saved": ("Config updated.", "green"),
    "config-not-saved": (
        "Config was not saved — the submitted values were rejected.",
        "red",
    ),
}


def _gateway(request: Request) -> Any:
    return request.app.state.gateway


def _registry(request: Request) -> Any:
    return request.app.state.registry


def _csrf_token(request: Request) -> str:
    return getattr(request.app.state, "csrf_token", "")


def _csrf_ok(request: Request, form_token: str) -> bool:
    expected = _csrf_token(request)
    if not expected:
        return False
    provided = request.headers.get(CSRF_HEADER) or form_token
    return bool(provided) and hmac.compare_digest(provided, expected)


def _normalize_host(host: str | None) -> str:
    """Normalize an incoming Host header for the loopback allow-list.

    Lowercase, strip an optional `:port`, collapse the IPv6 bracket form
    (`[::1]:8080` → `[::1]`, bare `::1` kept). Malformed or missing values
    normalize to a value that can never match the allow-list (fail closed).
    """
    if not host:
        return ""
    value = host.strip().lower()
    if not value:
        return ""
    if value.startswith("["):
        end = value.find("]")
        if end == -1:
            return ""
        rest = value[end + 1 :]
        if rest and not (rest.startswith(":") and rest[1:].isdigit()):
            return ""
        return value[: end + 1]
    if value.count(":") == 1:
        return value.rsplit(":", 1)[0]
    return value


async def _gate(request: Request) -> Response | None:
    """Loopback-only admin + Host validation + CSRF on mutations. None means pass.

    The Host header must be loopback (DNS-rebinding guard, fail closed) —
    checked before any body parsing so a forged origin never reaches CSRF or
    form handling. The same 403 surface answers both gate conditions.
    """
    if _normalize_host(request.headers.get("host")) not in _ALLOWED_HOSTS:
        return HTMLResponse(
            "<!doctype html><title>403</title><p>Admin is loopback-only.</p>",
            status_code=403,
        )
    host = getattr(request.app.state, "serve_host", "127.0.0.1")
    if host not in _LOOPBACK:
        return HTMLResponse(
            "<!doctype html><title>403</title><p>Admin is loopback-only.</p>",
            status_code=403,
        )
    if request.method in _MUTATING:
        form_token = ""
        if not request.headers.get(CSRF_HEADER):
            form = await request.form()
            form_token = str(form.get("_csrf", ""))
        if not _csrf_ok(request, form_token):
            return HTMLResponse("CSRF token mismatch", status_code=403)
    return None


def _fmt_uptime(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _status_node(request: Request) -> Any:
    gateway = _gateway(request)
    state = request.app.state
    sessions = len(getattr(gateway, "_sessions", {}))
    uptime = _fmt_uptime(
        time.monotonic() - getattr(state, "start_time", time.monotonic())
    )
    host = getattr(state, "serve_host", "127.0.0.1")
    try:
        health = "ok" if check_registry(_registry(request))[0] == "ok" else "degraded"
    except Exception:
        health = "degraded"
    return status_fragment(
        version=__version__,
        transport=getattr(state, "transport", "http"),
        host=host,
        sessions=sessions,
        uptime=uptime,
        health=health,
        exposed=host not in _LOOPBACK,
    )


def _page(
    request: Request,
    *,
    title: str,
    active: str,
    content: Any,
    notice_key: str = "",
) -> HTMLResponse:
    notice_text, _tone = NOTICE_MESSAGES.get(notice_key, ("", ""))
    return HTMLResponse(
        str(
            base_layout(
                page_title=title,
                active=active,
                csrf_token=_csrf_token(request),
                content=content,
                status_content=_status_node(request),
                version=__version__,
                notice=notice_text,
            )
        )
    )


def _render(node: Any) -> Markup:
    """HTML for a node that may be an Element or a child list (some panels
    return child lists); None children drop the way htpy drops them.

    Always returns markupsafe.Markup — `str(Element)` is Markup, and
    `plain_str + Markup` would escape the plain side via Markup.__radd__.
    """
    if isinstance(node, (list, tuple)):
        return Markup("".join(str(c) for c in node if c is not None))
    return Markup(str(node))


def _frag(node: Any) -> HTMLResponse:
    return HTMLResponse(_render(node))


def _notice_frag(node: Any, message: str, tone: str) -> HTMLResponse:
    return HTMLResponse(_render(node) + str(toast(message, tone=tone)))


def _form_token(request: Request) -> str:
    return _csrf_token(request)


def _sum_metric(request: Request, name: str) -> float:
    try:
        return float(_gateway(request).metrics.sum(name))
    except Exception:
        return 0.0


def _allow_env_display() -> str:
    value = os.environ.get("MCP_GWAY_ALLOW_LOCAL_COMMANDS", "").strip()
    return value if value else "(unset — built-in default allow-list)"


# --------------------------------------------------------------------------
# Full pages
# --------------------------------------------------------------------------


async def h_index(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    registry = _registry(request)
    rows = data.server_rows(registry)
    gateway = _gateway(request)
    stats = {
        "servers": str(len(rows)),
        "tools": str(sum(r.tool_count for r in rows)),
        "uptime": _fmt_uptime(
            time.monotonic()
            - getattr(request.app.state, "start_time", time.monotonic())
        ),
        "sessions": str(len(getattr(gateway, "_sessions", {}))),
    }
    try:
        health = "ok" if check_registry(registry)[0] == "ok" else "degraded"
    except Exception:
        health = "degraded"
    content = overview_content(
        rows=rows,
        stats=stats,
        health=health,
        transport=getattr(request.app.state, "transport", "http"),
        host=getattr(request.app.state, "serve_host", "127.0.0.1"),
    )
    return _page(
        request,
        title="Overview",
        active="overview",
        content=content,
        notice_key=request.query_params.get("notice", ""),
    )


async def h_servers(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    q = request.query_params.get("q", "")
    rows = data.filter_rows(data.server_rows(_registry(request)), q)
    content = servers_content(q=q, rows=rows, allow_env_value=_allow_env_display())
    return _page(
        request,
        title="Servers",
        active="servers",
        content=content,
        notice_key=request.query_params.get("notice", ""),
    )


async def h_server_detail(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    from mcp_gway.cli import _resolve_saved_name

    registry = _registry(request)
    name = _resolve_saved_name(registry, request.path_params["name"])
    try:
        config = registry.get_config(name)
    except FileNotFoundError:
        return HTMLResponse(
            "<!doctype html><title>404</title><p>Server not found.</p>",
            status_code=404,
        )
    except Exception as exc:
        logging.getLogger(_ADMIN_LOG).warning(
            "config unreadable", extra={"server": name, "reason": type(exc).__name__}
        )
        return RedirectResponse(
            "/admin/servers?notice=config-unreadable", status_code=303
        )
    try:
        pyi = registry.read_pyi(name)
        tools = registry.get_pyi_tools(name)
    except FileNotFoundError:
        return HTMLResponse(
            "<!doctype html><title>404</title><p>Server not found.</p>",
            status_code=404,
        )
    rows = {r.name: r for r in data.server_rows(registry)}
    row = rows.get(name)
    if row is None:
        return HTMLResponse(
            "<!doctype html><title>404</title><p>Server not found.</p>",
            status_code=404,
        )
    content = server_detail_content(
        row=row,
        config=config,
        pyi=pyi,
        tools=tools,
        csrf_token=_form_token(request),
        name=name,
        allow_env_value=_allow_env_display(),
    )
    return _page(
        request,
        title=name,
        active="servers",
        content=content,
        notice_key=request.query_params.get("notice", ""),
    )


async def h_tools(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    try:
        listing = _gateway(request).code_mode.list_tool_files()
    except Exception:
        listing = "No servers connected."
    content = tools_content(listing=listing, csrf_token=_form_token(request))
    return _page(
        request,
        title="Code Mode",
        active="tools",
        content=content,
        notice_key=request.query_params.get("notice", ""),
    )


async def h_observability(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    registry = _registry(request)
    gateway = _gateway(request)
    try:
        reg_status, reg_detail = check_registry(registry)
    except Exception as exc:
        reg_status, reg_detail = "fail", type(exc).__name__
    try:
        routes_status, routes_detail = check_routes(request.app)
    except Exception as exc:
        routes_status, routes_detail = "fail", type(exc).__name__
    overall = "ok" if reg_status == "ok" and routes_status == "ok" else "degraded"
    stats = {
        "uptime": _fmt_uptime(
            time.monotonic()
            - getattr(request.app.state, "start_time", time.monotonic())
        ),
        "requests": str(int(_sum_metric(request, "http_requests_total"))),
        "tool_calls": str(int(_sum_metric(request, "mcp_tool_calls_total"))),
        "sandbox_runs": str(int(_sum_metric(request, "sandbox_execute_total"))),
        "sessions": str(len(getattr(gateway, "_sessions", {}))),
        "version": __version__,
    }
    health = {
        "overall": overall,
        "registry": reg_status,
        "registry_detail": reg_detail,
        "routes": routes_status,
        "routes_detail": routes_detail,
    }
    try:
        exposition = gateway.metrics.exposition()
    except Exception:
        exposition = ""
    content = observability_content(
        health=health,
        stats=stats,
        exposition=exposition,
        transport=getattr(request.app.state, "transport", "http"),
        host=getattr(request.app.state, "serve_host", "127.0.0.1"),
    )
    return _page(
        request,
        title="Observability",
        active="observability",
        content=content,
        notice_key=request.query_params.get("notice", ""),
    )


async def h_policy(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    from mcp_gway.core.policy import get_allow_list, unrestricted_status

    status = unrestricted_status()
    content = policy_content(
        allow_env_value=_allow_env_display(),
        allow_set=get_allow_list(),
        unrestricted=status,
        serve_host=getattr(request.app.state, "serve_host", "127.0.0.1"),
        transport=getattr(request.app.state, "transport", "http"),
        remote_env=os.environ.get("MCP_GWAY_ALLOW_REMOTE", ""),
        csrf_token=_form_token(request),
    )
    return _page(
        request,
        title="Policy",
        active="policy",
        content=content,
        notice_key=request.query_params.get("notice", ""),
    )


# --------------------------------------------------------------------------
# Partials — status / servers
# --------------------------------------------------------------------------


async def p_status(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    return _frag(_status_node(request))


async def p_servers(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    q = request.query_params.get("q", "")
    rows = data.filter_rows(data.server_rows(_registry(request)), q)
    return _frag(server_grid(rows))


async def p_add_server(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    from mcp_gway.code_mode import to_pascal_case_identifier
    from mcp_gway.core import discover_tools, parse_envs, parse_headers
    from mcp_gway.core.policy import audit_local_action, check_cwd, check_local_command
    from mcp_gway.models import MCPServerConfig, OAuthConfig, ToolInfo

    registry = _registry(request)
    form = await request.form()

    def _error(message: str) -> Response:
        rows = data.server_rows(registry)
        grid = server_grid(data.filter_rows(rows, str(form.get("q", ""))))
        return HTMLResponse(str(grid) + str(toast(message, tone="red")))

    name_raw = str(form.get("name", "")).strip()
    conn_type = str(form.get("type", "local"))
    if not name_raw:
        return _error("Name is required.")
    try:
        name = to_pascal_case_identifier(name_raw)
    except Exception:
        return _error(f"Invalid server name '{name_raw}'.")
    existing = registry.list()
    if name in existing or name_raw in existing:
        return _error(f"Server '{name}' already exists.")

    timeout_raw = str(form.get("timeout", "5000")).strip() or "5000"
    try:
        timeout = int(timeout_raw)
    except ValueError:
        return _error("Timeout must be an integer (ms).")
    enabled = str(form.get("enabled", "")) in ("on", "true", "1")
    retry = str(form.get("retry_on_transport_error", "")) in ("on", "true", "1")
    tools_raw = str(form.get("tools", "*")).strip() or "*"
    tool_filter = (
        ["*"]
        if tools_raw == "*"
        else [t.strip() for t in tools_raw.split(",") if t.strip()]
    )

    if conn_type == "local":
        command = str(form.get("command", "")).strip()
        if not command:
            return _error("Command is required for local servers.")
        try:
            cmd_parts = shlex.split(command, posix=sys.platform != "win32")
        except Exception:
            return _error("Invalid command syntax.")
        cwd = str(form.get("cwd", "")).strip() or None
        resolved_cwd = None
        if cwd:
            try:
                resolved_cwd = check_cwd(cwd)
            except ValueError as exc:
                return _error(str(exc))
        env_lines = [ln for ln in str(form.get("env", "")).splitlines() if ln.strip()]
        try:
            environment = parse_envs(env_lines) if env_lines else None
        except ValueError as exc:
            return _error(str(exc))
        try:
            config = MCPServerConfig(
                name=name,
                type="local",
                command=cmd_parts,
                cwd=resolved_cwd,
                environment=environment,
                timeout=timeout,
                enabled=enabled,
                retry_on_transport_error=retry,
            )
        except Exception as exc:
            return _error(f"Invalid local config: {exc}")
        decision = check_local_command(list(cmd_parts), require_binary=True)
        audit_local_action(
            "admin_add", name, cmd_parts[0] if cmd_parts else None, decision
        )
        if not decision.allowed:
            return _error(decision.message)
    else:
        url = str(form.get("url", "")).strip()
        if not url:
            return _error("URL is required for remote servers.")
        header_lines = [
            ln for ln in str(form.get("headers", "")).splitlines() if ln.strip()
        ]
        try:
            headers = parse_headers(header_lines) if header_lines else None
        except ValueError as exc:
            return _error(str(exc))
        oauth_config = None
        client_id = str(form.get("oauth_client_id", "")).strip()
        client_secret = str(form.get("oauth_client_secret", "")).strip()
        client_scope = str(form.get("oauth_scope", "")).strip()
        if client_id or client_secret or client_scope:
            oauth_config = OAuthConfig(
                clientId=client_id or None,
                clientSecret=client_secret or None,
                scope=client_scope or None,
            )
        try:
            config = MCPServerConfig(
                name=name,
                type="remote",
                url=url,
                headers=headers,
                oauth=oauth_config,
                timeout=timeout,
                enabled=enabled,
                retry_on_transport_error=retry,
            )
        except Exception as exc:
            return _error(f"Invalid remote config: {exc}")
        try:
            from mcp_gway.core import detect_transport

            detected = await asyncio.wait_for(
                detect_transport(config), timeout=timeout / 1000 + 2
            )
            config.resolved_transport = detected  # type: ignore[assignment]
        except Exception:
            pass

    config.tools_to_execute = tool_filter
    try:
        discovered = await discover_tools(config)
    except Exception:
        discovered = []
    if tools_raw != "*":
        discovered = [t for t in discovered if t.name in set(tool_filter)]
    if config.type == "local":
        recheck = check_local_command(list(cmd_parts), require_binary=True)
        audit_local_action(
            "admin_add_regate", name, cmd_parts[0] if cmd_parts else None, recheck
        )
        if not recheck.allowed:
            return _error(recheck.message)
    registry.add(
        config, [ToolInfo(name=t.name, description=t.description) for t in discovered]
    )
    rows = data.server_rows(registry)
    grid = server_grid(rows)
    if not discovered:
        message = (
            f"Added {name} with 0 tools — run Refresh to discover "
            "(or authenticate first for OAuth servers)."
        )
        tone = "orange"
    else:
        message = f"Added {name} with {len(discovered)} tools."
        tone = "green"
    return HTMLResponse(
        str(grid)
        + str(toast(message, tone=tone))
        + str(modal_closed("add-server-modal"))
    )


def _resolve_name(registry: Any, wanted: str) -> str:
    from mcp_gway.cli import _resolve_saved_name

    return _resolve_saved_name(registry, wanted)


def _find_row(registry: Any, name: str) -> Any:
    for row in data.server_rows(registry):
        if row.name == name:
            return row
    return None


def _load_config(registry: Any, name: str) -> tuple[Any | None, str | None]:
    """Config or an honest message — read failures (unresolvable host, bad
    JSON) must degrade to UI states, never 500s."""
    try:
        return registry.get_config(name), None
    except FileNotFoundError:
        return None, f"Server '{name}' not found."
    except Exception as exc:
        logging.getLogger(_ADMIN_LOG).warning(
            "config unreadable", extra={"server": name, "reason": type(exc).__name__}
        )
        return None, f"Config for '{name}' is unreadable ({type(exc).__name__})."


def _policy_gate_local(
    request: Request, name: str, config: Any, action: str
) -> str | None:
    """Local policy check + audit for refresh paths. Returns error or None."""
    if getattr(config, "type", None) != "local":
        return None
    from mcp_gway.core.policy import audit_local_action, check_local_command

    command = list(config.command or [])
    decision = check_local_command(command, require_binary=True)
    audit_local_action(action, name, command[0] if command else None, decision)
    if not decision.allowed:
        return decision.message
    return None


async def _refresh_one(
    request: Request, name: str, auth: bool, oauth_port: int = 8989
) -> tuple[bool, str]:
    from mcp_gway.core import refresh_server

    registry = _registry(request)
    name = _resolve_name(registry, name)
    config, config_error = _load_config(registry, name)
    if config_error:
        return False, config_error
    if not getattr(config, "enabled", True):
        return False, f"{name} is disabled — enable it first."
    policy_error = _policy_gate_local(request, name, config, "admin_refresh")
    if policy_error:
        return False, policy_error
    try:
        discovered = await refresh_server(config, name, auth, oauth_port)
    except Exception as exc:
        logging.getLogger(_ADMIN_LOG).warning(
            "refresh failed", extra={"server": name, "reason": type(exc).__name__}
        )
        return False, f"Refresh failed for {name}: {type(exc).__name__}."
    if not discovered:
        return False, f"No tools discovered for {name} — try authentication."
    registry.update(name, discovered)
    return True, f"Refreshed {name} with {len(discovered)} tools."


async def p_refresh_all(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    registry = _registry(request)
    names = registry.list()
    if not names:
        return _notice_frag(server_grid([]), "No servers connected.", "white")
    failed = 0
    for name in names:
        success, _msg = await _refresh_one(request, name, auth=False)
        if not success:
            failed += 1
    succeeded = len(names) - failed
    rows = data.server_rows(registry)
    if failed:
        tone, message = "orange", f"Refreshed {succeeded}/{len(names)} servers."
    else:
        tone, message = "green", f"Refreshed all {len(names)} servers."
    return _notice_frag(server_grid(rows), message, tone)


async def p_refresh_one(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    registry = _registry(request)
    name = _resolve_name(registry, request.path_params["name"])
    success, message = await _refresh_one(request, name, auth=False)
    row = _find_row(registry, name)
    if row is None:
        return _notice_frag(toast_clear(), message, "red" if not success else "green")
    tone = "green" if success else "red"
    return HTMLResponse(_render(server_row(row)) + str(toast(message, tone=tone)))


async def p_auth(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    registry = _registry(request)
    name = _resolve_name(registry, request.path_params["name"])
    config, config_error = _load_config(registry, name)
    if config_error:
        row = _find_row(registry, name)
        node = server_row(row) if row is not None else toast_clear()
        return HTMLResponse(str(node) + str(toast(config_error, tone="red")))
    if config.type != "remote" or not getattr(config, "oauth", None):
        row = _find_row(registry, name)
        node = server_row(row) if row is not None else toast_clear()
        return HTMLResponse(
            str(node)
            + str(
                toast("Authentication requires a remote server with OAuth.", tone="red")
            )
        )

    async def _run() -> None:
        try:
            from mcp_gway.core import refresh_server

            discovered = await refresh_server(config, name, True, 8989)
            if discovered:
                registry.update(name, discovered)
                logging.getLogger(_ADMIN_LOG).info(
                    "background auth ok",
                    extra={"server": name, "tools": len(discovered)},
                )
            else:
                logging.getLogger(_ADMIN_LOG).warning(
                    "background auth discovered nothing", extra={"server": name}
                )
        except Exception as exc:
            logging.getLogger(_ADMIN_LOG).warning(
                "background auth failed",
                extra={"server": name, "reason": type(exc).__name__},
            )

    asyncio.create_task(_run())
    row = _find_row(registry, name)
    node = server_row(row) if row is not None else toast_clear()
    return HTMLResponse(
        str(node)
        + str(
            toast(
                "Authentication started — authorize in the opened browser window.",
                tone="blue",
            )
        )
    )


async def p_enabled(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    registry = _registry(request)
    name = _resolve_name(registry, request.path_params["name"])
    config, config_error = _load_config(registry, name)
    if config_error:
        return HTMLResponse(str(toast(config_error, tone="red")))
    registry.patch_enabled(name, not getattr(config, "enabled", True))
    row = _find_row(registry, name)
    if row is None:
        return _frag(toast_clear())
    return _frag(server_row(row))


async def p_tools_list(request: Request) -> Response:
    """Read-only discovered-tools fragment — polled by the detail page every
    5s. There is no web mutation path for tools (CLI `update` is canonical)."""
    denied = await _gate(request)
    if denied:
        return denied
    registry = _registry(request)
    name = _resolve_name(registry, request.path_params["name"])
    try:
        tools = registry.get_pyi_tools(name)
    except FileNotFoundError:
        return HTMLResponse("")
    except Exception:
        logging.getLogger(_ADMIN_LOG).warning(
            "tools partial failed", extra={"server": name}
        )
        return HTMLResponse("")
    return _frag(tools_panel(tools))


def _reject(request: Request, name: str, message: str) -> Response:
    """Config-save rejection. htmx keeps #detail-config — and the open edit
    modal with the user's typed input — untouched via HX-Retarget to the toast
    container; a non-htmx fallback redirects with a notice."""
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            str(toast(message, tone="red", oob=False)),
            headers={"HX-Retarget": "#toast", "HX-Reswap": "outerHTML"},
        )
    return RedirectResponse(
        f"/admin/servers/{name}?notice=config-not-saved", status_code=303
    )


def _oauth_field(raw: object) -> str:
    """Submitted OAuth edit field: trimmed; blank AND mask sentinels (bullet or
    asterisk runs, as rendered for secrets elsewhere) both mean keep stored —
    mask text must never be persisted as a secret."""
    value = str(raw or "").strip()
    if not value.strip("\u2022* \t"):
        return ""
    return value


async def p_set_config(request: Request) -> Response:
    """Config property update (never the tool list). Blank secret fields keep
    stored values — OAuth fields merge per field (blank keeps stored, non-blank
    replaces that field only, mask sentinels count as blank); the URL is
    revalidated through the SSRF guard (live DNS) on every save — fail closed
    with a toast, never a 500."""
    denied = await _gate(request)
    if denied:
        return denied
    from mcp_gway.core import parse_envs, parse_headers
    from mcp_gway.core.policy import (
        audit_local_action,
        check_cwd,
        check_local_command,
    )
    from mcp_gway.models import MCPServerConfig, OAuthConfig

    registry = _registry(request)
    name = _resolve_name(registry, request.path_params["name"])
    config, config_error = _load_config(registry, name)
    if config_error:
        return _reject(request, name, config_error)
    form = await request.form()

    def _error(message: str) -> Response:
        return _reject(request, name, message)

    timeout_raw = str(form.get("timeout", str(config.timeout))).strip()
    try:
        timeout = int(timeout_raw) if timeout_raw else int(config.timeout)
    except (TypeError, ValueError):
        return _error("Timeout must be an integer (ms).")
    enabled = str(form.get("enabled", "")) in ("on", "true", "1")
    tools_raw = str(form.get("tools_filter", "")).strip() or "*"
    tool_filter = (
        ["*"]
        if tools_raw == "*"
        else [t.strip() for t in tools_raw.split(",") if t.strip()]
    )
    data = config.model_dump()
    data["timeout"] = timeout
    data["enabled"] = enabled
    data["tools_to_execute"] = tool_filter
    if config.type == "local":
        command_raw = str(form.get("command", "")).strip()
        if not command_raw:
            return _error("Command is required for local servers.")
        try:
            cmd_parts = shlex.split(command_raw, posix=sys.platform != "win32")
        except Exception:
            return _error("Invalid command syntax.")
        data["command"] = cmd_parts
        cwd = str(form.get("cwd", "")).strip()
        if cwd:
            try:
                data["cwd"] = check_cwd(cwd)
            except ValueError as exc:
                return _error(str(exc))
        else:
            data["cwd"] = None
        env_raw = str(form.get("environment", ""))
        if env_raw.strip():
            env_lines = [ln for ln in env_raw.splitlines() if ln.strip()]
            try:
                data["environment"] = parse_envs(env_lines)
            except ValueError as exc:
                return _error(str(exc))
    else:
        url = str(form.get("url", "")).strip()
        if not url:
            return _error("URL is required for remote servers.")
        if url != config.url:
            data["resolved_transport"] = None
        data["url"] = url
        headers_raw = str(form.get("headers", ""))
        if headers_raw.strip():
            header_lines = [ln for ln in headers_raw.splitlines() if ln.strip()]
            try:
                data["headers"] = parse_headers(header_lines)
            except ValueError as exc:
                return _error(str(exc))
        client_id = _oauth_field(form.get("oauth_client_id"))
        client_secret = _oauth_field(form.get("oauth_client_secret"))
        client_scope = _oauth_field(form.get("oauth_scope"))
        if client_id or client_secret or client_scope:
            stored = config.oauth if isinstance(config.oauth, OAuthConfig) else None
            data["oauth"] = OAuthConfig(
                clientId=client_id or (stored.clientId if stored else None),
                clientSecret=client_secret or (stored.clientSecret if stored else None),
                scope=client_scope or (stored.scope if stored else None),
            )
    try:
        updated = MCPServerConfig(**data)
    except Exception as exc:
        return _error(f"Invalid config: {exc}")
    if updated.type == "local":
        command = list(updated.command or [])
        decision = check_local_command(command, require_binary=True)
        audit_local_action(
            "admin_update", name, command[0] if command else None, decision
        )
        if not decision.allowed:
            return _error(decision.message)
    try:
        registry.set_config(updated)
    except Exception as exc:
        return _error(f"Save failed: {exc}")
    if not request.headers.get("HX-Request"):
        return RedirectResponse(
            f"/admin/servers/{name}?notice=config-saved", status_code=303
        )
    row = _find_row(registry, name)
    if row is None:
        return _error(f"Server '{name}' not found.")
    inner = detail_config_inner(
        row=row,
        config=updated,
        name=name,
        csrf_token=_form_token(request),
        allow_env_value=_allow_env_display(),
    )
    return _notice_frag(inner, f"Config updated for {name}.", "green")


async def p_remove(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    registry = _registry(request)
    name = _resolve_name(registry, request.path_params["name"])
    try:
        registry.remove(name)
    except FileNotFoundError:
        return HTMLResponse(str(toast(f"Server '{name}' not found.", tone="red")))
    tokens_dir = home_dir() / ".config" / "mcp-gway" / "tokens"
    for suffix in ("", "_client"):
        token_file = tokens_dir / f"{name}{suffix}.json"
        try:
            if token_file.exists():
                token_file.unlink()
        except OSError:
            logging.getLogger(_ADMIN_LOG).warning(
                "token cleanup failed", extra={"server": name}
            )
    location = "/admin/servers?notice=removed"
    if request.headers.get("HX-Request"):
        return HTMLResponse("", headers={"HX-Redirect": location})
    return RedirectResponse(location, status_code=303)


# --------------------------------------------------------------------------
# Partials — policy
# --------------------------------------------------------------------------


async def p_policy_panel(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    from mcp_gway.core.policy import unrestricted_status

    env_set = os.environ.get("MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL") == "1"
    return _frag(unrestricted_panel(unrestricted_status(), env_set=env_set))


async def p_policy_enable(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    from mcp_gway.core.policy import create_unrestricted_marker, unrestricted_status

    try:
        create_unrestricted_marker()
    except OSError as exc:
        return _notice_frag(
            unrestricted_panel(unrestricted_status(), env_set=False),
            f"Marker create failed: {exc}",
            "red",
        )
    env_set = os.environ.get("MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL") == "1"
    node = unrestricted_panel(unrestricted_status(), env_set=env_set)
    message = "Break-glass marker created — active for 72h."
    if not env_set:
        message += " Set MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL=1 to activate."
    if request.headers.get("HX-Request"):
        return _notice_frag(node, message, "orange")
    return RedirectResponse("/admin/policy?notice=policy-enabled", status_code=303)


async def p_policy_disable(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    from mcp_gway.core.policy import remove_unrestricted_marker, unrestricted_status

    try:
        remove_unrestricted_marker()
    except OSError as exc:
        return _notice_frag(
            unrestricted_panel(unrestricted_status(), env_set=False),
            f"Marker remove failed: {exc}",
            "red",
        )
    env_set = os.environ.get("MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL") == "1"
    node = unrestricted_panel(unrestricted_status(), env_set=env_set)
    if request.headers.get("HX-Request"):
        return _notice_frag(node, "Break-glass marker removed.", "white")
    return RedirectResponse("/admin/policy?notice=policy-disabled", status_code=303)


# --------------------------------------------------------------------------
# Partials — Code Mode + metrics
# --------------------------------------------------------------------------


async def p_codemode_list(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    try:
        listing = _gateway(request).code_mode.list_tool_files()
    except Exception:
        listing = "No servers connected."
    return _frag(codemode_listing(listing))


def _exec_timeout(raw: object) -> float:
    """Clamped execute timeout (seconds) from the optional form field.

    Missing/blank/garbage/NaN → 10s default; bounded to [0.1, 30]s. The
    clamp bounds the deadline only: the response fires at eval completion,
    so a long CPU-bound Starlark eval (which holds the GIL) can still delay
    the response and briefly stall the event loop until the sandbox gains
    an interrupt/step-limit; on deadline the worker thread is abandoned
    (threads cannot be cancelled)."""
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return _EXEC_TIMEOUT_DEFAULT
    if not math.isfinite(value):
        return _EXEC_TIMEOUT_DEFAULT
    return max(_EXEC_TIMEOUT_MIN, min(_EXEC_TIMEOUT_MAX, value))


def _exec_timeout_response(request: Request, seconds: float) -> Response:
    """Execute-timeout surface, mirroring `_reject`: htmx gets a 200 toast
    retargeted to #toast (the #cm-output swap target stays untouched); a
    non-htmx caller gets the structured redirect-with-notice fallback."""
    message = f"Execution timed out after {seconds:g}s — the snippet was abandoned."
    if request.headers.get("HX-Request"):
        return HTMLResponse(
            str(toast(message, tone="red", oob=False)),
            headers={"HX-Retarget": "#toast", "HX-Reswap": "outerHTML"},
        )
    return RedirectResponse("/admin/tools?notice=exec-timeout", status_code=303)


async def p_codemode(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    form = await request.form()
    mode = str(form.get("mode", "list"))
    code_mode = _gateway(request).code_mode

    def _output(text: str, error: str = "") -> Response:
        node = codemode_output(text)
        if error:
            return HTMLResponse(str(node) + str(toast(error, tone="red")))
        return _frag(node)

    if mode == "read":
        file_name = str(form.get("fileName", "")).strip()
        if not file_name:
            return _output("", "fileName is required.")
        try:
            return _output(code_mode.read_tool_file(fileName=file_name))
        except Exception as exc:
            return _output("", f"Read failed: {type(exc).__name__}.")
    if mode == "docs":
        server = str(form.get("server", "")).strip()
        tool = str(form.get("tool", "")).strip()
        if not server or not tool:
            return _output("", "server and tool are required.")
        try:
            return _output(code_mode.get_tool_docs(server=server, tool=tool))
        except FileNotFoundError:
            return _output("", f"Server '{server}' not found.")
        except Exception as exc:
            return _output("", f"Docs failed: {type(exc).__name__}.")
    if mode == "execute":
        source = str(form.get("code", ""))
        if not source.strip():
            return _output("", "Code is required.")
        exec_timeout = _exec_timeout(form.get("timeout"))
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(code_mode.execute_tool_code, source),
                timeout=exec_timeout,
            )
        except TimeoutError:
            logging.getLogger(_ADMIN_LOG).warning(
                "admin execute timed out",
                extra={"timeout_s": exec_timeout},
            )
            return _exec_timeout_response(request, exec_timeout)
        except Exception as exc:
            return _output("", f"Execution failed: {type(exc).__name__}.")
        if request.headers.get("HX-Request"):
            return HTMLResponse(str(codemode_output(result)))
        return RedirectResponse("/admin/tools?notice=executed", status_code=303)
    return _frag(codemode_listing("No servers connected."))


async def p_metrics(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    gateway = _gateway(request)
    stats = {
        "uptime": _fmt_uptime(
            time.monotonic()
            - getattr(request.app.state, "start_time", time.monotonic())
        ),
        "requests": str(int(_sum_metric(request, "http_requests_total"))),
        "tool_calls": str(int(_sum_metric(request, "mcp_tool_calls_total"))),
        "sandbox_runs": str(int(_sum_metric(request, "sandbox_execute_total"))),
        "sessions": str(len(getattr(gateway, "_sessions", {}))),
        "version": __version__,
    }
    try:
        exposition = gateway.metrics.exposition()
    except Exception:
        exposition = ""
    return _frag(metrics_fragment(stats=stats, exposition=exposition))


async def p_empty(request: Request) -> Response:
    denied = await _gate(request)
    if denied:
        return denied
    return _frag(toast_clear())


def create_admin_routes() -> list[Route]:
    """All admin routes; appended to the Gateway app (http and sse alike)."""
    return [
        Route("/", h_index, methods=["GET"]),
        Route("/admin", h_index, methods=["GET"]),
        Route("/admin/servers", h_servers, methods=["GET"]),
        Route("/admin/servers/{name}", h_server_detail, methods=["GET"]),
        Route("/admin/tools", h_tools, methods=["GET"]),
        Route("/admin/observability", h_observability, methods=["GET"]),
        Route("/admin/policy", h_policy, methods=["GET"]),
        Route("/admin/partials/status", p_status, methods=["GET"]),
        Route("/admin/partials/servers", p_servers, methods=["GET"]),
        Route("/admin/partials/servers", p_add_server, methods=["POST"]),
        Route("/admin/partials/refresh", p_refresh_all, methods=["POST"]),
        Route(
            "/admin/partials/servers/{name}/refresh", p_refresh_one, methods=["POST"]
        ),
        Route("/admin/partials/servers/{name}/auth", p_auth, methods=["POST"]),
        Route("/admin/partials/servers/{name}/tools", p_tools_list, methods=["GET"]),
        Route(
            "/admin/partials/servers/{name}/config",
            p_set_config,
            methods=["PUT", "POST"],
        ),
        Route("/admin/partials/servers/{name}/enabled", p_enabled, methods=["PATCH"]),
        Route("/admin/partials/servers/{name}", p_remove, methods=["DELETE"]),
        Route(
            "/admin/partials/policy/unrestricted",
            p_policy_panel,
            methods=["GET"],
        ),
        Route(
            "/admin/partials/policy/unrestricted",
            p_policy_enable,
            methods=["POST"],
        ),
        Route(
            "/admin/partials/policy/unrestricted",
            p_policy_disable,
            methods=["DELETE"],
        ),
        Route("/admin/partials/codemode/list", p_codemode_list, methods=["GET"]),
        Route("/admin/partials/codemode", p_codemode, methods=["POST"]),
        Route("/admin/partials/metrics", p_metrics, methods=["GET"]),
        Route("/admin/partials/empty", p_empty, methods=["GET"]),
    ]
