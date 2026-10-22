# Code Mode

Code Mode exposes four meta-tools for lazy discovery, allowing agents to find and execute tools without loading all schemas into context.

| Tool                | Description                                         |
| ------------------- | --------------------------------------------------- |
| `gateway_listToolFiles`   | Discover available server stubs (`.pyi`)         |
| `gateway_readToolFile`    | Read exact tool names and parameters from a stub  |
| `gateway_getToolDocs`     | Fetch full documentation if the stub is truncated (optional) |
| `gateway_executeToolCode` | Execute in a hermetic Starlark sandbox            |

## Discovery Flow (Recommended)

1. `gateway_listToolFiles` — Discover available servers.
2. `gateway_readToolFile` — Read the `.pyi` stub for exact tool names and parameters.
3. `gateway_getToolDocs` (optional) — Fetch full docs if needed.
4. `gateway_executeToolCode` — Run Starlark: `Server.tool(param=value)`

> **Parallelization:** Run step 1 first. Steps 2–4 can run concurrently across servers/tools.

## Calling Convention (Starlark)

```python
result = Server.tool(param=value, params...)
value = result["key"]  # Use bracket access, not dot notation
```

## Constraints

- Synchronous only; use keyword arguments.
- No `try/except`, classes, or imports.
- Each execution scope is fresh — re-fetch or persist via MCP.
- Use stubs from `readToolFile` as the source of truth for signatures.

## Response Envelope

`executeToolCode` returns JSON with four keys:

```json
{
  "result": "...",
  "logs": ["..."],
  "calls": [
    {"i": 1, "server": "filesystem", "tool": "read_file", "ms": 12, "status": "ok", "bytes": 340, "reused": false}
  ],
  "usage": {"call_count": 1, "ms": 18, "limit_bytes": 262144, "truncated": false}
}
```

`calls` is the execution trace: what actually ran, in order, with duration and
payload size. Use it instead of guessing why a script failed. `reused: true`
means the call shared a connection opened earlier in the same script.

## Session Reuse

All calls in one script share one upstream connection per server. Three calls
to `Filesystem` spawn one process and run one MCP handshake, not three.

Reuse is scoped to a single `executeToolCode` invocation. A new script opens a
fresh connection, so a crashed upstream never poisons the next run. A failed
call evicts its connection and is never retried — a non-idempotent tool must
not run twice.

A script that calls `N` servers concurrently is still sequential: Starlark has
no `async`. Parallelism is a host-side concern.

## Result Budget

Responses are capped at `MCP_GWAY_MAX_RESULT_BYTES` (default `262144`, minimum
`1024`, maximum `8388608`). Oversized payloads are trimmed in this order:
log lines (last 200 kept), call trace (first 200 kept), long strings and
collections in `result`, then the whole result as a labelled preview.

Truncation is always labelled inside the value and reported as
`usage.truncated: true`. The envelope stays valid JSON — a truncated response
is never a broken document. When you see the marker, narrow the query or page
the results instead of retrying the same call.

## Usage Example

```python
result = Server.filesystem.read_file(path="/tmp/example.txt")
content = result["content"]
```
