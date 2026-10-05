from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from mcp_gway.observability.logging import request_id_ctx, sanitize_request_id
from mcp_gway.observability.metrics import MetricsRegistry

logger = logging.getLogger(__name__)

# FEAT-007 (BR-106): requests above this threshold emit a WARN-level log so
# operators can triage p95 outliers without enabling verbose DEBUG. Fixed
# constant, no env — decision recorded in ADR-012.
_SLOW_REQUEST_THRESHOLD_MS = 1000


def _get_request_id(request: Request) -> str:
    raw = request.headers.get("X-Request-ID") or request.headers.get("x-request-id")
    if not raw:
        raw = request.headers.get("X-Correlation-ID") or request.headers.get(
            "x-correlation-id"
        )
    if raw:
        sanitized = sanitize_request_id(raw)
        if sanitized != "unknown":
            return sanitized
    return uuid.uuid4().hex


def path_template(path: str) -> str:
    if path.startswith("/mcp"):
        # keep as /mcp or /mcp/messages
        if path.startswith("/mcp/messages"):
            return "/mcp/messages"
        return "/mcp"
    if path.startswith("/admin"):
        # admin pages are a fixed set; only per-server detail and partial
        # endpoints carry variable segments — collapse them so metric label
        # cardinality stays bounded.
        if path.startswith("/admin/partials"):
            return "/admin/partials"
        if path.startswith("/admin/servers/"):
            return "/admin/servers/{name}"
        if path in (
            "/admin",
            "/admin/servers",
            "/admin/tools",
            "/admin/observability",
            "/admin/policy",
        ):
            return path
        return "/admin"
    return path


class TracingMiddleware(BaseHTTPMiddleware):
    """W3C traceparent in, server span out — completes logs+metrics with traces."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        from mcp_gway.observability.tracing import (
            format_traceparent,
            get_tracer,
            parse_traceparent,
        )

        incoming_trace, incoming_parent = parse_traceparent(
            request.headers.get("traceparent")
        )
        tracer = get_tracer()
        attrs = {
            "http.method": request.method,
            "http.route": path_template(request.url.path),
        }
        if incoming_trace:
            attrs["parent_span_id"] = incoming_parent or "unknown"
        with tracer.span(
            f"{request.method} {path_template(request.url.path)}",
            kind="server",
            attributes=attrs,
        ) as span:
            if incoming_trace:
                span.trace_id = incoming_trace
                span.parent_id = incoming_parent
            request.state.trace_id = span.trace_id  # type: ignore[attr-defined]
            request.state.span_id = span.span_id  # type: ignore[attr-defined]
            try:
                response = await call_next(request)
            except Exception as exc:
                span.fail(f"{type(exc).__name__}: {exc}")
                raise
            span.set("http.status_code", response.status_code)
            if response.status_code >= 500:
                span.status = "error"
            response.headers["traceparent"] = format_traceparent(
                span.trace_id, span.span_id
            )
            return response


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = _get_request_id(request)
        token = request_id_ctx.set(rid)
        request.state.request_id = rid  # type: ignore[attr-defined]
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_ctx.reset(token)


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, registry: MetricsRegistry) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.registry = registry
        # ensure metrics exist
        self.registry.counter(
            "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
        )
        self.registry.histogram(
            "http_request_duration_seconds", "HTTP request latency", ["path"]
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - start
            status = str(response.status_code) if response is not None else "500"
            method = request.method
            tmpl = path_template(request.url.path)
            # sanitize method? keep as is
            try:
                self.registry.inc(
                    "http_requests_total",
                    {"method": method, "path": tmpl, "status": status},
                )
                self.registry.observe(
                    "http_request_duration_seconds", duration, {"path": tmpl}
                )
            except Exception:
                # never break request
                pass


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        from starlette.requests import ClientDisconnect

        start = time.perf_counter()
        rid = getattr(request.state, "request_id", None) or request_id_ctx.get() or "-"
        try:
            response = await call_next(request)
        except (asyncio.CancelledError, ClientDisconnect):
            raise
        except (ConnectionResetError, BrokenPipeError) as e:
            # Client hung up mid-request: debug, not a 500. Re-raise so the
            # disconnect middleware answers quietly; the disconnect itself
            # is not an application failure.
            logger.debug(
                "client disconnected during %s %s: %s",
                request.method,
                request.url.path,
                e,
            )
            raise
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.exception(
                "request failed",
                extra={
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": 500,
                    "duration_ms": duration_ms,
                },
            )
            raise
        duration_ms = int((time.perf_counter() - start) * 1000)
        # Use logger with extra fields for JSONFormatter
        extra = {
            "request_id": rid,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }
        # Log at INFO, but avoid logging health probes too verbosely? We log all
        logger.info("request completed", extra=extra)
        if duration_ms > _SLOW_REQUEST_THRESHOLD_MS:
            logger.warning("slow request", extra=extra)
        return response


_SANITIZE_LABEL_RE = re.compile(r"[^A-Za-z0-9_]")


def sanitize_label(value: str) -> str:
    s = _SANITIZE_LABEL_RE.sub("_", value)[:32]
    return s.strip("_") or "_other"
