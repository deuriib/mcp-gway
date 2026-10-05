"""HTTP/SSE gateway server for MCP protocol."""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from mcp_gway import __version__
from mcp_gway.admin.routes import create_admin_routes
from mcp_gway.code_mode import CodeMode
from mcp_gway.models import SSRF_IDLE_TIMEOUT, SSRF_MAX_BODY
from mcp_gway.observability.health import (
    handle_health,
    handle_live,
    handle_metrics,
    handle_ready,
)
from mcp_gway.observability.metrics import MetricsRegistry
from mcp_gway.observability.middleware import (
    CorrelationMiddleware,
    LoggingMiddleware,
    MetricsMiddleware,
)
from mcp_gway.registry import Registry

# WHY relaxed: the admin dashboard (htpy + htmx + Tailwind) loads its two
# runtime libraries from CDNs and renders one inline <style> block plus
# inline style attributes. Everything else stays same-origin; frame-ancestors
# keeps clickjacking off. Tests import this constant — edit in one place.
CSP = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net https://cdn.tailwindcss.com; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self' data:; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)


class _ClientDisconnectMiddleware(BaseHTTPMiddleware):
    """Turn client-abort noise into a quiet synthetic response.

    Same family as the WinError 64 accept abort at the socket layer: the peer
    hung up mid-request, so there is nobody to answer. Without this the error
    bubbles into a 500 + traceback for a client that already left. 204 keeps
    metrics truthful (no phantom 500) and the log at debug.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        try:
            return await call_next(request)
        except (asyncio.CancelledError, ClientDisconnect):
            raise
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            if _is_transient_accept_error({"exception": e}):
                logging.getLogger("mcp_gway.gateway").debug(
                    "client disconnected mid-request: %s", e
                )
                return Response(status_code=204)
            raise


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:  # type: ignore[no-untyped-def]
    """Last-resort 500: JSON shape, secret-safe, never an HTML traceback."""
    data = _safe_error_data(exc)
    logging.getLogger("mcp_gway.gateway").exception(
        "unhandled exception for %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500, content={"detail": "Internal Server Error", "error": data}
    )


class _SecurityMiddleware(BaseHTTPMiddleware):
    """Single security middleware (CSP + nosniff + DENY in one place)."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response


# Deprecated aliases: use _SecurityMiddleware (single). Kept for compatibility.
class _SecurityHeadersMiddleware(_SecurityMiddleware):
    pass


class _CSPMiddleware(_SecurityMiddleware):
    pass


PROTOCOL_VERSION = "2024-11-05"

# per-process concurrency bound for SSE streams (single event-loop process);
# enforced with an async lock to make 129 concurrent GET /mcp -> 429 deterministic.
MAX_CONCURRENT_SSE = 128
MAX_SESSIONS = 128
MAX_QUEUE = 32
MAX_IDLE_SECONDS = SSRF_IDLE_TIMEOUT
# Deprecated alias: use MAX_IDLE_SECONDS (single source of truth).
MAX_IDLE = MAX_IDLE_SECONDS
MAX_POST_CONCURRENT = 32
MAX_BODY_BYTES = SSRF_MAX_BODY
POST_ACQUIRE_TIMEOUT = 1.0
POST_READ_TIMEOUT = 5.0


class InvalidParamsError(ValueError):
    """Raised for JSON-RPC -32602 Invalid params (missing/bad tool arguments)."""


_REASON_RE = __import__("re").compile(r"\[reason=([A-Za-z0-9_]+)\]")

# WinError codes for transient accept aborts on Windows (client closed the
# socket between TCP handshake and asyncio finish_accept). Benign noise from
# the ProactorEventLoop ("Task exception was never retrieved" + "Accept
# failed on a socket"), not a gateway bug: the listening socket stays
# healthy. Downgrade to debug so operators stop paging on them.
_TRANSIENT_ACCEPT_WINERRORS = frozenset({64, 121, 995, 1236})


def _is_transient_accept_error(context: dict[str, object]) -> bool:
    """Return True for benign client-abort noise the loop reports."""
    exc = context.get("exception")
    if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
        return True
    if isinstance(exc, OSError):
        winerror = getattr(exc, "winerror", None)
        if winerror in _TRANSIENT_ACCEPT_WINERRORS:
            return True
        if exc.errno in (10053, 10054):
            return True
    message = str(context.get("message", ""))
    return "Accept failed on a socket" in message


def install_asyncio_exception_handler(
    loop: asyncio.AbstractEventLoop | None = None,
) -> None:
    """Install a loop exception handler that quiets transient accept noise.

    Benign Windows accept aborts (WinError 64 et al.) go to ``debug``;
    everything else keeps asyncio's default handler. Idempotent per loop.
    """
    try:
        target = loop or asyncio.get_running_loop()
    except RuntimeError:
        return
    default_handler = target.get_exception_handler()
    if getattr(default_handler, "_mcp_gway_quiet_accept", False):
        return

    def _handler(loop: asyncio.AbstractEventLoop, context: dict[str, object]) -> None:
        if _is_transient_accept_error(context):
            logging.getLogger("mcp_gway.gateway").debug(
                "transient accept aborted by client: %s",
                context.get("exception", context.get("message")),
            )
            return
        if default_handler is not None:
            default_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    _handler._mcp_gway_quiet_accept = True  # type: ignore[attr-defined]
    target.set_exception_handler(_handler)


def _safe_error_data(exc: BaseException) -> dict[str, str] | None:
    """Extract safe, actionable error data without leaking secrets.

    Only surfaces allow-listed [reason=...] tokens plus exception type.
    Never includes raw messages (they may contain headers/tokens/paths).
    """
    try:
        msg = str(exc)
    except Exception:
        # WHY broad: str(exc) can raise anything (custom __str__); the safe
        # fallback is type-only. Never includes raw messages (secret-safe).
        return {"type": type(exc).__name__}
    m = _REASON_RE.search(msg)
    if m:
        return {"type": type(exc).__name__, "reason": m.group(1)}
    return {"type": type(exc).__name__}


CODE_MODE_TOOLS = [
    {
        "name": "listToolFiles",
        "description": 'Lists the virtual .pyi stub files for connected CodeMode MCP servers (Bifrost CodeMode VFS). Default server-level binding returns servers/<server>.pyi per server (e.g., servers/filesystem.pyi); tool-level binding returns servers/<server>/<tool>.pyi per tool. The <tool> filename stem is the exact callable name for executeToolCode. Workflow: listToolFiles -> readToolFile -> (optional) getToolDocs -> executeToolCode. In code, call tools as Server.tool_name(param=value) (e.g., Filesystem.read_file(path=".")). CALL THIS FIRST when the user names a server, tool, or capability not in your visible tool list — connected MCP servers are only discoverable here. Do NOT claim a server or capability is unavailable until listToolFiles confirms it is absent.',
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "readToolFile",
        "description": "Reads a virtual .pyi stub: servers/<server>.pyi for the full server signature list, or servers/<server>/<tool>.pyi for a single tool (both listed by listToolFiles). Matching is case-insensitive and the .pyi extension is optional. Returns the authoritative callable name and arguments for executeToolCode as Server.tool_name(param=value). If the compact signature is insufficient, use getToolDocs. Workflow: listToolFiles -> readToolFile -> (optional) getToolDocs -> executeToolCode.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "fileName": {
                    "type": "string",
                    "description": "Stub to read — e.g., servers/filesystem.pyi or servers/filesystem/read_file.pyi",
                },
                "startLine": {
                    "type": "integer",
                    "description": "Where to start reading — useful for large servers (leave empty for full view).",
                },
                "endLine": {
                    "type": "integer",
                    "description": "Where to stop reading — useful for large servers (leave empty for full view).",
                },
            },
            "required": ["fileName"],
        },
    },
    {
        "name": "getToolDocs",
        "description": 'Get detailed documentation for a specific tool including full parameter descriptions, types, and usage examples. Use this when the compact signature from readToolFile is not sufficient to understand how to use a tool. Requires both server name and tool name as parameters (e.g., server="filesystem", tool="read_file").',
        "inputSchema": {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "The server that owns the tool, like filesystem",
                },
                "tool": {
                    "type": "string",
                    "description": "The tool you want to explore, like read_file",
                },
            },
            "required": ["server", "tool"],
        },
    },
    {
        "name": "executeToolCode",
        "description": 'Executes Python-like (Starlark) code in a sandboxed interpreter with MCP tool access as Server.tool_name(param=value) (e.g., result = Filesystem.read_file(path=".")). Final step of listToolFiles -> readToolFile -> (optional) getToolDocs -> executeToolCode; read the stub first and use the exact callable name shown. Security: L1 code validation (no imports/classes/file-IO/network primitives), L2 sandboxed runtime (no external modules, no filesystem/network/process access except via MCP tools, memory isolation), L3 bounded execution timeout, L4 Tool ACL (only tools_to_execute-allowed CodeMode servers/tools are visible). STARLARK RULES: no try/except/raise, no classes, no imports, no f-strings (use % formatting), no `is` (use ==), synchronous calls only, dict access via result["key"], assign output to `result`. Each call runs in a FRESH ISOLATED SCOPE (no state persists); print() output is captured to logs. Returns {"result": ..., "logs": [...]}.',
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": 'Starlark code calling tools as result = Server.tool_name(param="value") — assign `result` to your final answer',
                }
            },
            "required": ["code"],
        },
    },
]


@dataclass
class SessionInfo:
    queue: asyncio.Queue[dict[str, Any]]
    last_activity: float = field(default_factory=time.monotonic)


class Gateway:
    def __init__(
        self,
        registry: Registry,
        host: str = "127.0.0.1",
        transport: str = "http",
    ) -> None:
        """Build the ASGI app for a single MCP transport.

        ``transport`` selects which routes are exposed on ``/mcp``:
        ``http`` (Streamable HTTP) exposes POST /mcp only; ``sse`` exposes
        GET /mcp + POST /mcp/messages only. The two never coexist and there
        is no fallback between them.
        """
        if transport not in ("http", "sse"):
            raise ValueError(f"unknown transport '{transport}'")
        self.registry = registry
        self.host = host
        self.transport = transport
        self.code_mode = CodeMode(registry)
        self._sessions: dict[str, SessionInfo] = {}
        self.start_time: float = time.monotonic()
        self._last_loop_tick: float = time.monotonic()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._sse_lock = asyncio.Lock()
        self._post_sem = asyncio.Semaphore(MAX_POST_CONCURRENT)
        self._post_inflight = 0
        self.metrics = MetricsRegistry()
        # pre-register common metrics
        self.metrics.counter(
            "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
        )
        self.metrics.histogram(
            "http_request_duration_seconds", "HTTP request latency", ["path"]
        )
        self.metrics.counter(
            "mcp_tool_calls_total",
            "MCP tool call count by server/tool/status",
            ["server", "tool", "status"],
        )
        self.metrics.histogram(
            "discovery_duration_seconds", "Discovery latency", ["server", "status"]
        )
        self.metrics.counter(
            "stdio_requests_total",
            "stdio requests by method/status",
            ["method", "status"],
        )
        self.metrics.histogram(
            "stdio_request_duration_seconds", "stdio request latency", ["method"]
        )
        self.metrics.counter("sandbox_execute_total", "Sandbox executions", ["status"])
        self.metrics.histogram(
            "sandbox_duration_seconds", "Sandbox duration", ["status"]
        )
        self.metrics.counter(
            "registry_operations_total", "Registry add/remove/update counts", ["op"]
        )
        self.metrics.gauge("gateway_sessions_active", "Current SSE sessions", [])
        self.metrics.gauge("gateway_post_inflight", "Current POST /mcp inflight", [])
        self.metrics.counter(
            "gateway_post_total", "POST /mcp count by status", ["status"]
        )
        self.metrics.counter(
            "gateway_sse_dropped_total", "Dropped SSE messages (queue full)", ["reason"]
        )
        # FEAT-007 process/build metrics (BR-101): build_info{version} is the
        # canonical Prometheus incarnation marker; start_time/uptime let scrapers
        # and SLOs reason about process age without probing /health.
        self.metrics.gauge(
            "process_start_time_seconds", "Gateway process start (unix epoch)", []
        )
        self.metrics.set("process_start_time_seconds", time.time(), {})
        self.metrics.gauge("uptime_seconds", "Gateway uptime in seconds", [])
        self.metrics.set("uptime_seconds", 0.0, {})
        self.metrics.counter("build_info", "Gateway build info", ["version"])
        self.metrics.inc("build_info", {"version": __version__})
        self.metrics.gauge(
            "lifetime_seconds", "Gateway lifetime at shutdown (seconds)", []
        )
        self.metrics.counter(
            "gateway_sse_disconnects_total",
            "SSE stream disconnects by reason",
            ["reason"],
        )
        # FEAT-007 upstream/CodeMode telemetry (BR-111/113/114): pre-registered so
        # /metrics exposition is stable and histograms carry explicit buckets.
        self.metrics.counter(
            "upstream_tool_calls_total",
            "Upstream MCP tool calls by server/tool/status",
            ["server", "tool", "status"],
        )
        self.metrics.histogram(
            "upstream_tool_duration_seconds",
            "Upstream MCP tool latency",
            ["server", "tool"],
        )
        self.metrics.counter(
            "upstream_retries_total",
            "Accepted transport-phase retries by server",
            ["server"],
        )
        self.metrics.counter(
            "code_mode_servers_skipped_total",
            "CodeMode servers skipped at inject/refresh",
            ["reason"],
        )
        registry.ensure()
        try:
            registry._metrics = self.metrics  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            self.code_mode.sandbox._metrics = self.metrics  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            self.code_mode.server_factory._metrics = (  # type: ignore[attr-defined]
                self.metrics
            )
        except Exception:
            pass
        # FEAT-007 (BR-114): servers broken at startup must count too. The
        # sandbox had no registry during the first inject pass, so re-sync now
        # that metrics are wired — refresh() only re-attempts servers that
        # FAILED injection (healthy ones are already in _modules) and records
        # a skip metric + WARN for each (single skip per server, idempotent).
        try:
            self.code_mode.refresh()
        except Exception:
            pass
        from contextlib import asynccontextmanager as _acm

        gateway_self = self

        @_acm
        async def _lifespan(app):  # type: ignore[no-untyped-def]
            install_asyncio_exception_handler()
            try:
                loop = asyncio.get_running_loop()
                if (
                    gateway_self._heartbeat_task is None
                    or gateway_self._heartbeat_task.done()
                ):
                    gateway_self._heartbeat_task = loop.create_task(
                        gateway_self._heartbeat()
                    )
            except RuntimeError:
                pass
            try:
                yield
            finally:
                await gateway_self.aclose()

        # WHY gated routes instead of omitting them: an absent route yields
        # Starlette's plain-text 405/404; an explicit route answers with a JSON
        # `detail` + RFC-correct `Allow`, so a client can discover which
        # transport this process serves (405, not 404 — the path exists, the
        # method is what's off-transport).
        if transport == "sse":
            mcp_routes = [
                Route("/mcp", self._mcp_sse, methods=["GET"]),
                Route("/mcp", self._mcp_post_not_allowed, methods=["POST"]),
                Route("/mcp/messages", self._mcp_post, methods=["POST"]),
            ]
        else:
            mcp_routes = [
                Route("/mcp", self._mcp_post, methods=["POST"]),
                Route("/mcp", self._mcp_get_not_allowed, methods=["GET"]),
            ]

        async def _http_exception_handler(
            request: Request, exc: HTTPException
        ) -> JSONResponse:  # type: ignore[no-untyped-def]
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )

        self.app = Starlette(
            routes=[
                Route("/health", self._health, methods=["GET"]),
                Route("/ready", handle_ready, methods=["GET"]),
                Route("/live", handle_live, methods=["GET"]),
                Route("/metrics", handle_metrics, methods=["GET"]),
                *mcp_routes,
                *create_admin_routes(),
            ],
            lifespan=_lifespan,
            exception_handlers={
                Exception: _unhandled_exception_handler,
                HTTPException: _http_exception_handler,
            },
        )
        # order outer→inner: Correlation→Metrics→Logging→Security
        # Starlette last added = outermost, so add innermost first
        self.app.add_middleware(_SecurityMiddleware)
        self.app.add_middleware(LoggingMiddleware)
        self.app.add_middleware(MetricsMiddleware, registry=self.metrics)
        self.app.add_middleware(CorrelationMiddleware)
        self.app.add_middleware(_ClientDisconnectMiddleware)
        self.app.state.registry = registry  # type: ignore[attr-defined]
        self.app.state.serve_host = host  # type: ignore[attr-defined]
        self.app.state.transport = transport  # type: ignore[attr-defined]
        self.app.state.metrics = self.metrics  # type: ignore[attr-defined]
        self.app.state.gateway = self  # type: ignore[attr-defined]
        self.app.state.start_time = self.start_time  # type: ignore[attr-defined]
        self.app.state.csrf_token = secrets.token_urlsafe(32)  # type: ignore[attr-defined]
        try:
            install_asyncio_exception_handler()
        except Exception:
            pass
        try:
            loop = asyncio.get_running_loop()
            self._heartbeat_task = loop.create_task(self._heartbeat())
        except RuntimeError:
            pass

    async def aclose(self) -> None:
        task = self._heartbeat_task
        self._heartbeat_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        # FEAT-007 (BR-105): the last observability act — a shutdown summary so
        # an operator grepping stderr after exit sees what the process did.
        try:
            uptime = time.monotonic() - self.start_time
            self.metrics.set("lifetime_seconds", uptime, {})
            summary = {
                "uptime_seconds": round(uptime, 3),
                "http_requests_total": int(self.metrics.sum("http_requests_total")),
                "sessions_active": len(self._sessions),
                "sse_dropped_total": int(self.metrics.sum("gateway_sse_dropped_total")),
            }
            logging.getLogger("mcp_gway.gateway").info(
                "gateway shutdown summary", extra=summary
            )
        except Exception:
            # WHY broad: shutdown must never raise hiding cancellation.
            pass

    def _create_session(self, session_id: str) -> SessionInfo:
        info = SessionInfo(queue=asyncio.Queue(maxsize=MAX_QUEUE))
        self._sessions[session_id] = info
        try:
            self.metrics.set("gateway_sessions_active", float(len(self._sessions)), {})
        except Exception:
            pass
        return info

    def cleanup_expired_sessions(
        self, max_idle_seconds: float = SSRF_IDLE_TIMEOUT
    ) -> int:
        now = time.monotonic()
        expired = [
            sid
            for sid, info in self._sessions.items()
            if now - info.last_activity > max_idle_seconds
        ]
        for sid in expired:
            info = self._sessions.pop(sid)
            try:
                info.queue.put_nowait(None)
            except asyncio.QueueFull:
                try:
                    while True:
                        info.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    info.queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
        if expired:
            try:
                self.metrics.set(
                    "gateway_sessions_active", float(len(self._sessions)), {}
                )
            except Exception:
                pass
        return len(expired)

    async def _handle_post(
        self, body: dict[str, Any], *, session_id: str | None = None
    ) -> dict[str, Any]:
        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params", {})

        if session_id and session_id not in self._sessions:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32001, "message": "Session not found or expired"},
            }

        try:
            if (
                method == "tools/call"
                and isinstance(params, dict)
                and params.get("name") == "executeToolCode"
            ):
                # Starlark sandbox blocks (ThreadPool wait + asyncio.run inside);
                # never hold the event loop: offload the whole tool call.
                result = await asyncio.to_thread(self._handle_method, method, params)
            else:
                result = self._handle_method(method, params)
            response = {"jsonrpc": "2.0", "id": req_id, "result": result}
        except InvalidParamsError as e:
            data = _safe_error_data(e)
            err: dict[str, Any] = {"code": -32602, "message": "Invalid params"}
            if data:
                err["data"] = data
            response = {"jsonrpc": "2.0", "id": req_id, "error": err}
        except ValueError as e:
            msg = str(e)
            if msg.startswith(("Unknown method", "Unknown tool")):
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": "Method not found"},
                }
            else:
                data = _safe_error_data(e)
                err2: dict[str, Any] = {"code": -32603, "message": "Internal error"}
                if data:
                    err2["data"] = data
                response = {"jsonrpc": "2.0", "id": req_id, "error": err2}
        except (FileNotFoundError, PermissionError) as e:
            data = _safe_error_data(e)
            err3: dict[str, Any] = {"code": -32603, "message": "Internal error"}
            if data:
                err3["data"] = data
            response = {"jsonrpc": "2.0", "id": req_id, "error": err3}
        except Exception as e:
            data = _safe_error_data(e)
            err4: dict[str, Any] = {"code": -32603, "message": "Internal error"}
            if data:
                err4["data"] = data
            response = {"jsonrpc": "2.0", "id": req_id, "error": err4}

        if session_id and session_id in self._sessions:
            info = self._sessions[session_id]
            info.last_activity = time.monotonic()
            try:
                info.queue.put_nowait(response)
            except asyncio.QueueFull:
                try:
                    self.metrics.inc(
                        "gateway_sse_dropped_total", {"reason": "queue_full"}
                    )
                except Exception:
                    pass

        return response

    async def _heartbeat(self) -> None:
        while True:
            self._last_loop_tick = time.monotonic()
            try:
                self.metrics.set(
                    "uptime_seconds", time.monotonic() - self.start_time, {}
                )
            except Exception:
                # WHY broad: the heartbeat must never die from a registry error.
                pass
            try:
                self.cleanup_expired_sessions(MAX_IDLE_SECONDS)
            except Exception:
                pass
            await asyncio.sleep(30)

    async def _health(self, request: Request) -> JSONResponse:
        return await handle_health(request)

    async def _mcp_get_not_allowed(self, request: Request) -> JSONResponse:
        """GET /mcp is gated off: this gateway serves Streamable HTTP only."""
        return JSONResponse(
            {"detail": "SSE transport not enabled (serve --transport sse)"},
            status_code=405,
            headers={"Allow": "POST"},
        )

    async def _mcp_post_not_allowed(self, request: Request) -> JSONResponse:
        """POST /mcp is gated off: this gateway serves SSE only."""
        return JSONResponse(
            {
                "detail": "Streamable HTTP transport not enabled (serve --transport http)"
            },
            status_code=405,
            headers={"Allow": "GET"},
        )

    async def _mcp_sse(self, request: Request) -> StreamingResponse:
        # per-process gate: lock makes concurrent check-and-create atomic,
        # so 129 concurrent GET /mcp deterministically yields one 429.
        async with self._sse_lock:
            if len(self._sessions) >= MAX_CONCURRENT_SSE:
                return JSONResponse(
                    {"detail": "too many sessions"},
                    status_code=429,
                    headers={"Retry-After": "30"},
                )  # type: ignore[return-value]
            session_id = str(uuid.uuid4())
            info = self._create_session(session_id)

        async def event_stream():
            reason = "client_disconnect"
            try:
                yield f"event: endpoint\ndata: /mcp/messages?session_id={session_id}\n\n"
                while True:
                    try:
                        msg = await asyncio.wait_for(
                            info.queue.get(), timeout=MAX_IDLE_SECONDS
                        )
                    except TimeoutError:
                        reason = "idle"
                        break
                    if msg is None:
                        reason = "idle"
                        break
                    info.last_activity = time.monotonic()
                    yield f"event: message\ndata: {json.dumps(msg)}\n\n"
            except asyncio.CancelledError:
                reason = "client_disconnect"
                raise
            except GeneratorExit:
                reason = "client_disconnect"
                raise
            except Exception:
                reason = "error"
                raise
            finally:
                self._sessions.pop(session_id, None)
                try:
                    self.metrics.set(
                        "gateway_sessions_active", float(len(self._sessions)), {}
                    )
                except Exception:
                    pass
                try:
                    self.metrics.inc(
                        "gateway_sse_disconnects_total", {"reason": reason}
                    )
                except Exception:
                    pass
                logging.getLogger("mcp_gway.gateway").warning(
                    "SSE session ended",
                    extra={"session_id": session_id, "reason": reason},
                )

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    async def _mcp_post(self, request: Request) -> JSONResponse:
        # Slow-loris guard: body is read OUTSIDE the POST slot with a bounded
        # timeout so a stalled sender never holds concurrency budget.
        # Slot wait itself is bounded -> 429 + Retry-After parity with SSE.
        try:
            body = await asyncio.wait_for(
                self._read_limited_json(request), timeout=POST_READ_TIMEOUT
            )
        except TimeoutError:
            try:
                self.metrics.inc("gateway_post_total", {"status": "rejected"})
            except Exception:
                pass
            return JSONResponse({"detail": "read timeout"}, status_code=408)
        if isinstance(body, JSONResponse):
            try:
                self.metrics.inc("gateway_post_total", {"status": "rejected"})
            except Exception:
                pass
            return body
        try:
            await asyncio.wait_for(
                self._post_sem.acquire(), timeout=POST_ACQUIRE_TIMEOUT
            )
        except TimeoutError:
            try:
                self.metrics.inc("gateway_post_total", {"status": "rejected"})
            except Exception:
                pass
            return JSONResponse(
                {"detail": "too many requests"},
                status_code=429,
                headers={"Retry-After": "1"},
            )
        self._post_inflight += 1
        try:
            try:
                self.metrics.set(
                    "gateway_post_inflight", float(self._post_inflight), {}
                )
            except Exception:
                # WHY broad: metrics must never break the request path; any
                # registry error falls back to serving without instrumentation.
                pass
            try:
                session_id = request.query_params.get("session_id")
                response = await self._handle_post(body, session_id=session_id)
                try:
                    self.metrics.inc("gateway_post_total", {"status": "ok"})
                except Exception:
                    pass
                return JSONResponse(response)
            finally:
                self._post_inflight -= 1
                try:
                    self.metrics.set(
                        "gateway_post_inflight", float(self._post_inflight), {}
                    )
                except Exception:
                    pass
        finally:
            self._post_sem.release()

    async def _read_limited_json(
        self, request: Request
    ) -> dict[str, Any] | JSONResponse:
        clen = request.headers.get("content-length")
        if clen and clen.isdigit() and int(clen) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "payload too large"}, status_code=413)
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_BODY_BYTES:
                return JSONResponse({"detail": "payload too large"}, status_code=413)
        try:
            return json.loads(body.decode("utf-8") if body else "{}")
        except (ValueError, UnicodeError):
            # WHY narrow: only malformed JSON/encoding maps to 400; stream
            # errors already surfaced above, never mask cancellation.
            return JSONResponse({"detail": "Invalid JSON"}, status_code=400)

    def _handle_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "ping":
            return {}
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-gway", "version": __version__},
            }
        if method == "notifications/initialized":
            return {}
        if method == "tools/list":
            return {"tools": CODE_MODE_TOOLS}
        if method == "tools/call":
            return self._handle_tool_call(params)
        raise ValueError(f"Unknown method: {method}")

    def _handle_tool_call(self, params: dict[str, Any]) -> dict[str, Any]:
        import re

        name = params.get("name")
        arguments = params.get("arguments", {})

        # Instrumentation helper: sanitize labels
        def _san(v: str) -> str:
            s = re.sub(r"[^A-Za-z0-9_]", "_", v)[:32]
            return s.strip("_") or "_other"

        status = "ok"
        server_label = "gateway"
        tool_label = _san(str(name)) if name else "_other"
        # For executeToolCode we could try to parse server from code, but keep gateway
        try:
            if name == "listToolFiles":
                result = self.code_mode.list_tool_files()
            elif name == "readToolFile":
                if not isinstance(arguments, dict) or not arguments.get("fileName"):
                    raise InvalidParamsError(
                        "readToolFile requires fileName [reason=invalid_params]"
                    )
                result = self.code_mode.read_tool_file(
                    fileName=arguments["fileName"],
                    startLine=arguments.get("startLine"),
                    endLine=arguments.get("endLine"),
                )
            elif name == "getToolDocs":
                # server label from arguments
                try:
                    server_label = _san(str(arguments.get("server", "gateway")))
                    tool_label = _san(str(arguments.get("tool", str(name))))
                except Exception:
                    pass
                if (
                    not isinstance(arguments, dict)
                    or not arguments.get("server")
                    or not arguments.get("tool")
                ):
                    raise InvalidParamsError(
                        "getToolDocs requires server and tool [reason=invalid_params]"
                    )
                result = self.code_mode.get_tool_docs(
                    server=arguments["server"], tool=arguments["tool"]
                )
            elif name == "executeToolCode":
                if not isinstance(arguments, dict) or not isinstance(
                    arguments.get("code"), str
                ):
                    raise InvalidParamsError(
                        "executeToolCode requires code string [reason=invalid_params]"
                    )
                if not arguments["code"].strip():
                    raise InvalidParamsError(
                        "executeToolCode requires non-empty code [reason=invalid_params]"
                    )
                result = self.code_mode.execute_tool_code(code=arguments["code"])
            else:
                status = "error"
                raise ValueError(f"Unknown tool: {name}")
            # success path
            try:
                self.metrics.inc(
                    "mcp_tool_calls_total",
                    {"server": server_label, "tool": tool_label, "status": status},
                )
            except Exception:
                pass
            return {"content": [{"type": "text", "text": result}]}
        except Exception:
            # record error if not already
            if status != "error":
                status = "error"
                try:
                    self.metrics.inc(
                        "mcp_tool_calls_total",
                        {"server": server_label, "tool": tool_label, "status": status},
                    )
                except Exception:
                    pass
            raise
