"""Factory that creates server objects for the Starlark sandbox.

Bridges async MCP clients with synchronous Starlark execution by:
1. Reading server configs from the Registry
2. Creating MCP client connections on-demand
3. Wrapping async tool calls with asyncio.run()
4. Returning sync functions callable from Starlark
"""

from __future__ import annotations

import asyncio
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from mcp_gway.registry import Registry

# Characters not allowed in Python identifiers
_INVALID_IDENTIFIER_RE = re.compile(r"[^a-zA-Z0-9_]")

# Per-execution plumbing, published by CodeMode before a script runs and read
# by the tool closures. ContextVars (not attributes) so two concurrent scripts
# cannot share a connection cache or a trace.

# Slack added on top of a tool's own timeout before the sandbox thread gives up
# waiting on the event loop. The inner wait_for should always fire first; this
# only catches a wedged loop.
_LOOP_WAIT_SLACK = 5.0


@dataclass
class _CachedConnection:
    """A live upstream session reused for the duration of one script."""

    session: Any
    stack: Any

    async def aclose(self) -> None:
        try:
            await asyncio.wait_for(self.stack.aclose(), timeout=5.0)
        except Exception:
            # WHY broad: teardown must never mask the tool error being raised.
            pass


_ACTIVE_LOOP: ContextVar[Any] = ContextVar("mcp_gway_active_loop", default=None)
_ACTIVE_CACHE: ContextVar[dict[str, _CachedConnection] | None] = ContextVar(
    "mcp_gway_active_cache", default=None
)
_ACTIVE_TRACE: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "mcp_gway_active_trace", default=None
)


def _sanitize_identifier(name: str) -> str:
    """Replace non-identifier characters with underscores.

    MCP tool names may contain hyphens (e.g. query-docs) which are
    invalid as Python/Starlark identifiers.
    """
    sanitized = _INVALID_IDENTIFIER_RE.sub("_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized


class ServerFactory:
    """Creates injectable server objects for the Starlark sandbox.

    Each server object is a Starlark-compatible struct with sync methods
    that wrap async MCP tool calls.
    """

    def __init__(self, registry: Registry) -> None:
        self._registry = registry
        # FEAT-007: injected by Gateway (BR-111) — upstream tool telemetry.
        self._metrics: object | None = None

    def is_auto_executable(self, server: str, tool: str) -> bool:
        """Agent Mode classification: executable AND auto-approved."""
        try:
            config = self._registry.get_config(server)
        except Exception:
            return False
        if not getattr(config, "is_code_mode_client", True):
            return False
        try:
            self._check_tool_allowed(config, tool)
        except Exception:
            return False
        auto = getattr(config, "tools_to_auto_execute", []) or []
        if "*" in auto:
            return True
        import re as _re

        safe = _re.sub(r"[^A-Za-z0-9_]", "_", tool)
        if safe and safe[0].isdigit():
            safe = f"_{safe}"
        return tool in auto or safe in auto

    async def _call_tool_async(
        self, config: Any, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Call an MCP tool asynchronously with a bounded per-config timeout.

        FEAT-007 (BR-111/112/113): every call records upstream telemetry
        (``upstream_tool_calls_total`` + ``upstream_tool_duration_seconds``,
        classifying ``timeout`` vs ``error``). With opt-in
        ``retry_on_transport_error`` the transport/connect/initialize phase is
        retried exactly once — ``session.call_tool`` is never re-run, so a
        non-idempotent tool cannot be executed twice on a transient blip.

        When a script is executing, a live connection is cached per server for
        the whole run: six calls to one server spawn one process, not six. The
        cache is per execution, so a crashed upstream is evicted rather than
        shared across scripts.
        """
        from mcp import ClientSession

        from mcp_gway.core import create_client_transport
        from mcp_gway.observability.tracing import get_tracer

        self._check_tool_allowed(config, tool_name)

        raw_timeout = getattr(config, "timeout", 5000)
        if raw_timeout is None or raw_timeout <= 0:
            timeout_sec = 5.0
        else:
            timeout_sec = raw_timeout / 1000
        server = getattr(config, "name", "unknown")
        tool_label = _sanitize_identifier(tool_name) or "_other"
        metrics = self._metrics
        cache = _ACTIVE_CACHE.get()
        trace = _ACTIVE_TRACE.get()
        status = "error"
        retried = False
        result_bytes = 0
        cache_hit = False
        start = time.perf_counter()
        tracer = get_tracer()
        entry: _CachedConnection | None = None
        stack: Any = None
        with tracer.span(
            f"tool {server}.{tool_label}",
            kind="client",
            attributes={"mcp.server": server, "mcp.tool": tool_label},
        ) as span:
            try:
                from contextlib import AsyncExitStack

                async def _setup(stack: Any) -> Any:
                    """Transport + initialize phase — the ONLY retry-eligible step.

                    At this point the tool call has not started, so re-running this
                    phase cannot duplicate a side effect (BR-112).
                    """
                    read, write = await stack.enter_async_context(
                        create_client_transport(config)
                    )
                    session = await stack.enter_async_context(
                        ClientSession(read, write)
                    )
                    await asyncio.wait_for(session.initialize(), timeout=timeout_sec)
                    return session

                if cache is not None:
                    entry = cache.get(server)
                if entry is not None:
                    cache_hit = True
                    result = await asyncio.wait_for(
                        entry.session.call_tool(tool_name, arguments),
                        timeout=timeout_sec,
                    )
                else:
                    stack = AsyncExitStack()
                    try:
                        try:
                            session = await _setup(stack)
                        except Exception:
                            if not getattr(config, "retry_on_transport_error", False):
                                raise
                            retried = True
                            await stack.aclose()
                            stack = AsyncExitStack()
                            session = await _setup(stack)
                        result = await asyncio.wait_for(
                            session.call_tool(tool_name, arguments),
                            timeout=timeout_sec,
                        )
                    except BaseException:
                        await stack.aclose()
                        raise
                    if cache is not None:
                        entry = _CachedConnection(session=session, stack=stack)
                        cache[server] = entry
                status = "ok"
                span.set("mcp.status", status)
                if cache_hit:
                    span.set("mcp.session_reused", True)
                extracted = _extract_result(result)
                result_bytes = _approx_bytes(extracted)
                return extracted
            except BaseException as exc:  # noqa: BLE001 — telemetry classifies, then re-raises
                status = "timeout" if isinstance(exc, TimeoutError) else "error"
                if (
                    entry is not None
                    and cache is not None
                    and cache.get(server) is entry
                ):
                    cache.pop(server, None)
                    await entry.aclose()
                try:
                    span.fail(f"{type(exc).__name__}: {exc}")
                    span.set("mcp.status", status)
                    if retried:
                        span.set("mcp.retried", True)
                    if cache_hit:
                        span.set("mcp.session_reused", True)
                except Exception:
                    pass
                raise
            finally:
                duration = time.perf_counter() - start
                if trace is not None:
                    trace.append(
                        {
                            "i": len(trace) + 1,
                            "server": server,
                            "tool": tool_name,
                            "ms": int(duration * 1000),
                            "status": status,
                            "bytes": result_bytes,
                            "reused": cache_hit,
                        }
                    )
                if metrics is not None:
                    try:
                        metrics.inc(
                            "upstream_tool_calls_total",
                            {"server": server, "tool": tool_label, "status": status},
                        )
                        metrics.observe(
                            "upstream_tool_duration_seconds",
                            duration,
                            {"server": server, "tool": tool_label},
                        )
                        if retried:
                            metrics.inc("upstream_retries_total", {"server": server})
                        if cache_hit:
                            metrics.inc(
                                "upstream_session_reused_total", {"server": server}
                            )
                    except Exception:
                        # WHY broad: telemetry must never alter the tool outcome.
                        pass

    async def aclose_sessions(self) -> None:
        """Close every connection cached for the active execution."""
        cache = _ACTIVE_CACHE.get()
        if not cache:
            return
        entries = list(cache.values())
        cache.clear()
        for entry in entries:
            await entry.aclose()

    def make_server_struct(self, server_name: str) -> object:
        """Create a Starlark-compatible server object.

        The sandbox's inject_server() introspects this object to
        create Starlark struct methods. Only tools_to_execute-allowed
        tools are bound (Tool ACL).
        """
        config = self._registry.get_config(server_name)
        tool_names = self._get_tool_names(server_name)

        class ServerStruct:
            pass

        struct = ServerStruct()
        struct.__name__ = server_name

        for tool_name in tool_names:
            self._bind_tool_method(struct, config, tool_name)

        return struct

    def _bind_tool_method(self, struct: object, config: Any, tool_name: str) -> None:
        """Bind a synchronous tool method to the struct.

        Uses sanitized attribute names (hyphens → underscores) so that
        the struct is introspectable by the Starlark sandbox.
        The original tool_name is preserved for MCP calls.
        """

        def make_tool_fn(cfg: Any, tn: str) -> Any:
            def tool_fn(**kwargs: Any) -> Any:
                coro = self._call_tool_async(cfg, tn, kwargs)
                loop = _ACTIVE_LOOP.get()
                if loop is None:
                    return asyncio.run(coro)
                # call_soon_threadsafe copies the caller's context, which is how
                # the cache, trace and loop reach the coroutine on the loop thread.
                try:
                    future = asyncio.run_coroutine_threadsafe(coro, loop)
                except BaseException:
                    coro.close()
                    raise
                raw_timeout = getattr(cfg, "timeout", 5000) or 5000
                wait_budget = max(raw_timeout / 1000 + _LOOP_WAIT_SLACK, 30.0)
                try:
                    return future.result(timeout=wait_budget)
                except TimeoutError:
                    future.cancel()
                    raise TimeoutError(
                        f"tool '{tn}' did not return within {wait_budget:.0f}s "
                        "[reason=loop_timeout]"
                    ) from None

            tool_fn.__name__ = tn
            return tool_fn

        safe_name = _sanitize_identifier(tool_name)
        setattr(struct, safe_name, make_tool_fn(config, tool_name))

    def _check_tool_allowed(self, config: Any, tool_name: str) -> None:
        """Enforce tools_to_execute allow-list; ["*"] allows all."""
        allow = getattr(config, "tools_to_execute", ["*"]) or ["*"]
        if "*" in allow:
            return
        allowed = set(allow)
        if tool_name in allowed:
            return
        import re as _re

        safe = _re.sub(r"[^A-Za-z0-9_]", "_", tool_name)
        if safe and safe[0].isdigit():
            safe = f"_{safe}"
        if safe in allowed:
            return
        from mcp_gway.gateway import InvalidParamsError

        raise InvalidParamsError(
            f"tool '{tool_name}' not in tools_to_execute [reason=tool_not_allowed]"
        )

    def _get_tool_names(self, server_name: str) -> list[str]:
        """Extract tool names from the server's .pyi stub, filtered by ACL."""
        import re as _re

        content = self._registry.read_pyi(server_name)
        names: list[str] = []
        for line in content.splitlines():
            if line.startswith("def "):
                name = line.split("def ")[1].split("(")[0].strip()
                if not name:
                    continue
                m = _re.search(r"\[original:\s*([^\]]+)\]", line)
                if m:
                    orig = m.group(1).strip()
                    if orig:
                        names.append(orig)
                        continue
                names.append(name)
        try:
            config = self._registry.get_config(server_name)
            allow = getattr(config, "tools_to_execute", ["*"]) or ["*"]
            if "*" not in allow:
                allowed = set(allow)
                filtered: list[str] = []
                for n in names:
                    safe = _re.sub(r"[^A-Za-z0-9_]", "_", n)
                    if safe and safe[0].isdigit():
                        safe = f"_{safe}"
                    if n in allowed or safe in allowed:
                        filtered.append(n)
                return filtered
        except Exception:
            pass
        return names


def _approx_bytes(value: Any) -> int:
    """Cheap size estimate for the call trace (never raises)."""
    if isinstance(value, str):
        return len(value)
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    try:
        import json

        return len(json.dumps(value, default=str))
    except Exception:
        return 0


def _extract_result(result: Any) -> Any:
    """Extract a Python-friendly result from MCP tool result."""
    if hasattr(result, "content"):
        parts = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
            else:
                parts.append(str(item))
        text = "\n".join(parts)
        try:
            import json

            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text
    return result
