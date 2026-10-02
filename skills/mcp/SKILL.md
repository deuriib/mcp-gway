---
name: mcp-gway-mcp
description: Serve and consume the gateway over MCP (v3.1.0) — stdio/http/sse transports, Code Mode protocol, admin dashboard. Use when wiring agents (OpenCode/Claude/Pi) to the gateway.
---

# mcp-gway MCP + serve surface

## `serve` transports (routes split by transport, no cross-fallback — `gateway.py`)

```bash
mcp-gway serve [--transport stdio|http|sse] [--host 127.0.0.1] [--port 8080]
               [--log-level LEVEL] [--registry-dir PATH]
```

Default `--transport stdio` (NDJSON JSON-RPC on stdin/stdout, logs → stderr).
`--host/--port` only with `http|sse` (with stdio → exit 2).
`mcp-gway mcp` is a DEPRECATED hidden alias for `serve --transport stdio`.

| Transport | `/mcp` routes |
|-----------|---------------|
| `http` | `POST /mcp` (JSON-RPC); `GET /mcp` → 405 `Allow: POST` |
| `sse` | `GET /mcp` (SSE `endpoint` event) + `POST /mcp/messages?session_id=…`; `POST /mcp` → 405 `Allow: GET` |

Always present: probes `/health`, `/ready`, `/live`, `/metrics`; admin `GET /` + `/admin*` (24 routes).
`app.state.transport` exposes the active transport.

OpenCode client: `{ "type": "local", "command": ["mcp-gway", "serve", "--transport", "stdio"] }`.

## Code Mode protocol (4 meta-tools, `gateway.py:CODE_MODE_TOOLS`)

Workflow: `listToolFiles → readToolFile → (optional) getToolDocs → executeToolCode`.
Call tools in code as `Server.tool_name(param=value)` (e.g. `Filesystem.read_file(path=".")`);
assign output to `result`. Same `CodeMode` class backs `mcp-gway tools …` (see `mcp-gway-cli`).

- `listToolFiles` — call FIRST when the user names a server/tool/capability not in the visible list. Never claim a capability is unavailable until this confirms absence.
- `readToolFile` — `servers/<server>.pyi` (full signatures) or `servers/<server>/<tool>.pyi` (single tool); case-insensitive, `.pyi` optional; `startLine`/`endLine` for large stubs.
- `getToolDocs` — needs `server` + `tool`; use when the compact signature is insufficient.
- `executeToolCode` — sandboxed Starlark: L1 validation (no imports/classes/file-IO/network), L2 sandbox (no external modules/fs/net/process except via MCP tools), L3 bounded timeout, L4 Tool ACL (`tools_to_execute`). Starlark rules: no try/except/raise, no classes/imports/f-strings (`%` formatting), no `is` (use `==`), sync calls only, `result["key"]` dict access, fresh isolated scope per call, `print()` → logs. Returns `{"result": …, "logs": […]}`.

## Admin dashboard (par CLI, loopback-only)

`/` index + `/admin/servers[/{name}]`, `/admin/tools` (Code Mode page: explorer + read/docs/execute forms), `/admin/observability`, `/admin/policy`. Gate: 403 unless loopback host; CSRF required on every mutation (`X-CSRF-Token` or `_csrf`); headers/OAuth masked in detail view; OAuth never inline (background task, parity `refresh --auth`); CSP single constant `CSP` in `gateway.py`.

## Local-first security for serve

Binds `127.0.0.1` by default. `--host 0.0.0.0` without `MCP_GWAY_ALLOW_REMOTE=1` → exit 2. With opt-in → `WARNING: server exposed on non-loopback`; `X-Warning: exposed` only on `GET /metrics` → `403`. Never expose without firewall/auth in front. Full policy gates: see `mcp-gway-core`.
