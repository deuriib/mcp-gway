from __future__ import annotations

import secrets
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


def _new_id(bits: int) -> str:
    return secrets.token_hex(bits // 8)


_trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)
_span_id_ctx: ContextVar[str | None] = ContextVar("span_id", default=None)
_span_stack_ctx: ContextVar[tuple[Span, ...]] = ContextVar("span_stack", default=())


@dataclass
class Span:
    """One unit of traced work — HTTP request, tool call, sandbox eval."""

    name: str
    kind: str = "internal"
    trace_id: str = field(default_factory=lambda: _new_id(128))
    span_id: str = field(default_factory=lambda: _new_id(64))
    parent_id: str | None = None
    start: float = field(default_factory=time.perf_counter)
    end: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None

    def set(self, key: str, value: Any) -> Span:
        self.attributes[key] = value
        return self

    def fail(self, error: str) -> Span:
        self.status = "error"
        self.error = error[:500]
        return self

    @property
    def duration_ms(self) -> float:
        end = self.end if self.end is not None else time.perf_counter()
        return (end - self.start) * 1000.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "kind": self.kind,
            "status": self.status,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 3),
            "attributes": dict(self.attributes),
        }


class Tracer:
    """No-op-friendly stdlib tracer — collects finished spans in a ring buffer."""

    def __init__(self, max_spans: int = 256) -> None:
        self._max_spans = max(16, max_spans)
        self._finished: list[Span] = []

    @contextmanager
    def span(
        self,
        name: str,
        kind: str = "internal",
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        parent_stack = _span_stack_ctx.get()
        parent = parent_stack[-1] if parent_stack else None
        trace_id = _trace_id_ctx.get() or (parent.trace_id if parent else _new_id(128))
        span = Span(
            name=name,
            kind=kind,
            trace_id=trace_id,
            parent_id=parent.span_id if parent else None,
        )
        if attributes:
            span.attributes.update(attributes)
        token_trace = _trace_id_ctx.set(trace_id)
        token_span = _span_id_ctx.set(span.span_id)
        token_stack = _span_stack_ctx.set(parent_stack + (span,))
        try:
            yield span
        except Exception as exc:
            span.fail(f"{type(exc).__name__}: {exc}")
            raise
        finally:
            span.end = time.perf_counter()
            _span_stack_ctx.reset(token_stack)
            _span_id_ctx.reset(token_span)
            _trace_id_ctx.reset(token_trace)
            self._record(span)

    def _record(self, span: Span) -> None:
        self._finished.append(span)
        if len(self._finished) > self._max_spans:
            del self._finished[: len(self._finished) - self._max_spans]

    def current_trace_id(self) -> str | None:
        return _trace_id_ctx.get()

    def current_span_id(self) -> str | None:
        return _span_id_ctx.get()

    def recent_spans(self, limit: int = 50) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self._finished[-limit:]]

    def clear(self) -> None:
        self._finished.clear()


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer()
    return _tracer


def set_tracer(tracer: Tracer | None) -> None:
    global _tracer
    _tracer = tracer


def parse_traceparent(value: str | None) -> tuple[str | None, str | None]:
    """Parse a W3C traceparent header → (trace_id, parent_span_id)."""
    if not value:
        return None, None
    try:
        parts = value.strip().split("-")
        if len(parts) != 4 or parts[0] != "00":
            return None, None
        _, trace_id, span_id, _flags = parts
        if len(trace_id) != 32 or len(span_id) != 16:
            return None, None
        int(trace_id, 16)
        int(span_id, 16)
        if trace_id == "0" * 32 or span_id == "0" * 16:
            return None, None
        return trace_id, span_id
    except Exception:
        return None, None


def format_traceparent(trace_id: str, span_id: str) -> str:
    return f"00-{trace_id}-{span_id}-01"


__all__ = [
    "Span",
    "Tracer",
    "format_traceparent",
    "get_tracer",
    "parse_traceparent",
    "set_tracer",
]
