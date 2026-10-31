# Code Mode

Code Mode exposes five MCP meta-tools for lazy discovery and bounded orchestration.
The discovery flow still funnels through the same four Starlark-safe tools, and
`callManyTool` is the fifth tool: a host-side fan-out adapter for parallel MCP calls
without exposing new sandbox capabilities.

| Tool | Description |
| ----- | ----------- |
| `listToolFiles` | Discover available server stubs (`.pyi`) |
| `readToolFile` | Read exact tool names and parameters from a stub |
| `getToolDocs` | Fetch full docs if the stub is not enough |
| `executeTool` | Execute in the hermetic Starlark sandbox |
| `callManyTool` | Fan out up to 50 MCP calls with per-item error isolation |

## Discovery Flow (Recommended)

1. `listToolFiles` — discover available servers.
2. `readToolFile` — read the `.pyi` stub for exact call signatures.
3. `getToolDocs` (optional) — fetch full docs if needed.
4. `executeTool` — run Starlark with `Server.tool(param=value)`.
5. `callManyTool` — when the host needs parallel fan-out without writing Starlark.

The discovery workflow still starts with the four tool-discovery meta-tools. The
fifth tool is a direct host-side helper for orchestration and is not available
inside Starlark.

## Calling Convention (Starlark)

```python
result = Server.tool(param=value, params...)
value = result["key"]  # bracket access only
```

## Constraints

- Synchronous only; use keyword arguments.
- No `try/except`, classes, or imports.
- Each execution scope is fresh — re-fetch or persist via MCP.
- Use stubs from `readToolFile` as the source of truth for signatures.
- `callManyTool` is a host-side tool; it is never callable from the sandbox.

## Response Envelope

`executeTool` returns JSON with four keys:

```json
{
  "result": "...",
  "logs": ["..."],
  "calls": [
    {"i": 1, "server": "filesystem", "tool": "read_file", "status": "ok"}
  ],
  "usage": {"call_count": 1, "ms": 18, "limit_bytes": 262144, "truncated": false}
}
```

`calls` is the execution trace: what actually ran, in order, with status and timing.
Use it instead of guessing why a script failed.

## Session Reuse

All calls in one script share one upstream connection per server. Three calls to
`Filesystem` spawn one process and run one MCP handshake, not three.

Reuse is scoped to a single `executeTool` invocation. A new script opens a
fresh connection, so a crashed upstream never poisons the next run.

## `callManyTool` contract

The `callManyTool` tool accepts a `calls` array of one to fifty items.
Each item looks like this:

```json
{
  "server": "filesystem",
  "tool": "read_file",
  "arguments": {"path": "README.md"},
  "id": "a"
}
```

Rules:
- `calls` is required.
- `arguments` defaults to `{}` when omitted.
- Item shape is validated per entry; malformed items produce `ok: false` results,
  not a batch abort.
- A denied tool or unknown server is also reported as a per-item error.
- Results keep input order.
- Default concurrency stays `min(8, len(calls))`.

The response is still the normal `build_envelope` payload:

```json
{
  "result": [
    {"id": "a", "server": "filesystem", "tool": "read_file", "ok": true, "result": {...}},
    {"id": "b", "server": "filesystem", "tool": "read_file", "ok": false, "error": {"type": "FileNotFoundError", "message": "..."}}
  ],
  "logs": [],
  "calls": [],
  "usage": {"call_count": 0, "ms": 12, "limit_bytes": 262144, "truncated": false}
}
```

This tool is intentionally not available inside Starlark. It is a host-side
orchestration surface, and the sandbox keeps the same safety profile.

## Result Budget

Responses are capped at `MCP_GWAY_MAX_RESULT_BYTES` (default `262144`, minimum
`1024`, maximum `8388608`). Oversized payloads are trimmed in a predictable order,
then labelled as truncated. The envelope stays valid JSON — a truncated response
is never a broken document.

## Usage Example

```python
result = Server.filesystem.read_file(path="/tmp/example.txt")
content = result["content"]
```
