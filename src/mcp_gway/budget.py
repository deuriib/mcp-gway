"""Bound the size of a Code Mode response.

A single tool result can be megabytes. Without a budget the whole payload is
handed back to the model, where it either blows the context window or pushes
out the instructions the agent was following. This module trims the envelope
in a predictable order (logs, call trace, result structure, result text) and
labels every cut so the agent can narrow the query instead of guessing.

The envelope is always valid JSON: the final fallback is a minimal envelope,
never a truncated JSON document.
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_MAX_RESULT_BYTES = 262_144
MIN_RESULT_BYTES = 1_024
MAX_RESULT_BYTES_CEILING = 8_388_608

MAX_LOG_LINES = 200
MAX_LOG_BYTES = 65_536
MAX_TRACE_CALLS = 200
MIN_TRACE_CALLS = 20

_GENEROUS_STRING_LIMIT = 8_192
_GENEROUS_ITEM_LIMIT = 200
_AGGRESSIVE_STRING_LIMIT = 2_048
_AGGRESSIVE_ITEM_LIMIT = 50

_TRUNCATION_HINT = (
    "narrow the query, page the results, or read a slice "
    "(readToolFile startLine/endLine)"
)


def max_result_bytes() -> int:
    """Read the byte budget from ``MCP_GWAY_MAX_RESULT_BYTES``.

    Unparseable or out-of-range values fall back to the default rather than
    failing a tool call; the cap is a guard rail, not a contract.
    """
    raw = os.environ.get("MCP_GWAY_MAX_RESULT_BYTES")
    if not raw:
        return DEFAULT_MAX_RESULT_BYTES
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_MAX_RESULT_BYTES
    if value < MIN_RESULT_BYTES:
        return MIN_RESULT_BYTES
    if value > MAX_RESULT_BYTES_CEILING:
        return MAX_RESULT_BYTES_CEILING
    return value


def _dump(value: Any, default: Any) -> str:
    return json.dumps(value, default=default, ensure_ascii=False)


def _truncated_text(total: int) -> str:
    return f"…[truncated {total} bytes — {_TRUNCATION_HINT}]"


def _shrink(
    value: Any,
    *,
    string_limit: int,
    item_limit: int,
    state: dict[str, bool],
    depth: int = 0,
) -> Any:
    """Trim oversized strings and collections, keeping JSON shape intact."""
    if depth > 6:
        state["truncated"] = True
        return f"<nested value: {type(value).__name__}>"
    if isinstance(value, str):
        if len(value) <= string_limit:
            return value
        state["truncated"] = True
        return value[:string_limit] + _truncated_text(len(value) - string_limit)
    if isinstance(value, (bytes, bytearray)):
        if len(value) <= string_limit:
            return bytes(value).decode("utf-8", "replace")
        state["truncated"] = True
        return bytes(value[:string_limit]).decode("utf-8", "replace") + _truncated_text(
            len(value) - string_limit
        )
    if isinstance(value, dict):
        items = list(value.items())
        out: dict[Any, Any] = {}
        for key, item in items[:item_limit]:
            out[key] = _shrink(
                item,
                string_limit=string_limit,
                item_limit=item_limit,
                state=state,
                depth=depth + 1,
            )
        if len(items) > item_limit:
            state["truncated"] = True
            out["_dropped_keys"] = len(items) - item_limit
        return out
    if isinstance(value, (list, tuple)):
        out_list = [
            _shrink(
                item,
                string_limit=string_limit,
                item_limit=item_limit,
                state=state,
                depth=depth + 1,
            )
            for item in value[:item_limit]
        ]
        if len(value) > item_limit:
            state["truncated"] = True
            out_list.append(f"…[+{len(value) - item_limit} more items]")
        return out_list
    return value


def _cap_logs(logs: Any, state: dict[str, bool]) -> list[str]:
    if not logs:
        return []
    lines = [str(line) for line in logs]
    if len(lines) > MAX_LOG_LINES:
        state["truncated"] = True
        dropped = len(lines) - MAX_LOG_LINES
        lines = [f"…[{dropped} earlier log lines dropped]"] + lines[-MAX_LOG_LINES:]
    total = 0
    kept: list[str] = []
    for line in reversed(lines):
        total += len(line)
        if total > MAX_LOG_BYTES:
            state["truncated"] = True
            kept.append(f"…[earlier log output dropped at {MAX_LOG_BYTES} bytes]")
            break
        kept.append(line)
    return list(reversed(kept))


def _cap_trace(calls: Any, state: dict[str, bool]) -> list[Any]:
    if not calls:
        return []
    items = list(calls)
    if len(items) > MAX_TRACE_CALLS:
        state["truncated"] = True
        dropped = len(items) - MAX_TRACE_CALLS
        return items[:MAX_TRACE_CALLS] + [{"dropped_calls": dropped}]
    return items


def _envelope(
    result: Any,
    logs: list[str],
    calls: list[Any],
    duration_ms: int,
    limit: int,
    state: dict[str, bool],
) -> dict[str, Any]:
    return {
        "result": result,
        "logs": logs,
        "calls": calls,
        "usage": {
            "call_count": sum(1 for c in calls if isinstance(c, dict) and "tool" in c),
            "ms": duration_ms,
            "limit_bytes": limit,
            "truncated": bool(state["truncated"]),
        },
    }


def build_envelope(
    *,
    result: Any,
    logs: Any,
    calls: Any,
    duration_ms: int,
    default: Any = str,
) -> str:
    """Serialize a Code Mode response under the byte budget.

    Raises the same serialization error ``json.dumps`` would raise so callers
    keep their existing error contract.
    """
    limit = max_result_bytes()
    state = {"truncated": False}

    safe_logs = _cap_logs(logs, state)
    safe_calls = _cap_trace(calls, state)

    first = _shrink(
        result,
        string_limit=_GENEROUS_STRING_LIMIT,
        item_limit=_GENEROUS_ITEM_LIMIT,
        state=state,
    )
    text = _dump(
        _envelope(first, safe_logs, safe_calls, duration_ms, limit, state), default
    )
    if len(text.encode("utf-8")) <= limit:
        return text

    state["truncated"] = True
    aggressive = _shrink(
        result,
        string_limit=_AGGRESSIVE_STRING_LIMIT,
        item_limit=_AGGRESSIVE_ITEM_LIMIT,
        state=state,
    )
    text = _dump(
        _envelope(
            aggressive,
            safe_logs,
            safe_calls[:MIN_TRACE_CALLS],
            duration_ms,
            limit,
            state,
        ),
        default,
    )
    if len(text.encode("utf-8")) <= limit:
        return text

    serialized = _dump(result, default)
    overhead = 256
    keep = max(0, min(len(serialized), limit - overhead))
    preview = serialized[:keep] + _truncated_text(len(serialized) - keep)
    minimal = _envelope(
        preview,
        [f"…[{len(safe_logs)} log lines dropped with oversized result]"]
        if safe_logs
        else [],
        [],
        duration_ms,
        limit,
        {"truncated": True},
    )
    text = _dump(minimal, default)
    if len(text.encode("utf-8")) <= limit:
        return text

    minimal["result"] = ""
    minimal["logs"] = []
    return _dump(minimal, default)
