---
name: mcp-gway-mcp
description: Serve and consume the gateway over MCP (v4.2.0) — stdio/http/sse transports, Code Mode discovery protocol, wiring agents, admin dashboard. Use when running serve, calling the 4 meta-tools, or connecting OpenCode/Pi/Claude to one gateway endpoint.
---

# mcp-gway MCP + serve surface

One gateway process serves `/mcp`, probes, and the admin dashboard on the same Starlette app. Pick a transport, connect one client, then run the 4-step discovery protocol before every tool call.

## Choose your transport

| You want… | Run | `/mcp` behavior |
|-----------|-----|-----------------|
| Agent on the same machine (OpenCode, Claude Desktop local) | `serve --transport stdio` (default) | NDJSON JSON-RPC on stdin/stdout, logs → stderr |
| HTTP client / `.mcp.json` URL | `serve --transport http` | `POST /mcp` (JSON-RPC); `GET /mcp` → 405 `Allow: POST` |
| SSE streaming client | `serve --transport sse` | `GET /mcp` (SSE `endpoint` event) + `POST /mcp/messages?session_id=…`; `POST /mcp` → 405 `Allow: GET` |

No cross-fallback: a mispaired client gets `405` + an `Allow` header naming the right method. `app.state.transport` exposes the active transport. Probes `/health`, `/ready`, `/live`, `/metrics` are always present on `http|sse`.

## serve — variants with examples

`mcp-gway serve [--transport stdio|http|sse] [--host 127.0.0.1] [--port 8080] [--log-level LEVEL] [--registry-dir PATH]`

`--host/--port` apply ONLY to `http|sse` — passing them with stdio exits 2. `mcp-gway mcp` is a DEPRECATED hidden alias for `serve --transport stdio` (same loop + a deprecation notice on stderr).

```bash
# Variant 1 — stdio for a local agent (default)
mcp-gway serve
mcp-gway serve --transport stdio --log-level debug

# Variant 2 — HTTP for URL clients
mcp-gway serve --transport http --port 8080            # binds 127.0.0.1
mcp-gway serve --transport http --host 127.0.0.1 --port 8080 --registry-dir ./servers

# Variant 3 — SSE for streaming clients
mcp-gway serve --transport sse --host 127.0.0.1 --port 8080

# Variant 4 — expose beyond loopback (opt-in, firewall + auth required in front)
MCP_GWAY_ALLOW_REMOTE=1 mcp-gway serve --transport http --host 0.0.0.0 --port 8080
# Without the opt-in: exit 2 + "binding to non-loopback host … requires MCP_GWAY_ALLOW_REMOTE=1"
```

## Connect an agent — variants

```bash
# Start once, verify before wiring anything
mcp-gway serve --transport http --port 8080 &
curl -s http://127.0.0.1:8080/health | jq .status   # "ok"
```

OpenCode (`type: local`, stdio — no URL needed):

```json
{ "type": "local", "command": ["mcp-gway", "serve", "--transport", "stdio"] }
```

Claude Desktop (`claude_desktop_config.json`, HTTP):

```json
{ "mcpServers": { "gateway": { "url": "http://localhost:8080/mcp" } } }
```

Pi (`.mcp.json` at repo root, adapter-discovered):

```json
{ "mcpServers": { "gateway": { "url": "http://127.0.0.1:8080/mcp", "directTools": true, "requestTimeoutMs": 5000 } } }
```

URL/token overrides without touching files (honored by the OpenCode + Pi plugins):

```bash
MCP_GWAY_URL=http://127.0.0.1:9090/mcp mcp-gway serve --transport http --port 9090
MCP_GWAY_TOKEN=secret-xyz  # sent as `Authorization: Bearer …`, never written to .mcp.json
```

## Code Mode protocol — the 4 steps with examples

Mandatory order: `listToolFiles → readToolFile → (optional) getToolDocs → executeToolCode`. Call tools in code as `Server.tool_name(param=value)` and assign output to `result`. The same `CodeMode` class backs `mcp-gway tools …` — the CLI form is in `mcp-gway-cli`; the shapes below are identical.

Step 1 — discover. Call FIRST whenever the user names a server, tool, or capability not in the visible list. Never claim a capability is unavailable until this confirms absence.

```bash
mcp-gway tools list                    # servers/ + one .pyi per server
mcp-gway tools list --binding tool     # servers/<name>/<tool>.pyi per tool
```

Step 2 — read the stub (authoritative signatures). Case-insensitive, `.pyi` optional, `startLine/endLine` for large stubs.

```bash
mcp-gway tools read --server ParallelSearch
# def web_search(objective: str, search_queries: list, session_id: str = None, model_name: str = None) -> dict
# def web_fetch(urls: list, objective: str = None, …) -> dict

mcp-gway tools read --server Context7 --tool resolve_library_id
mcp-gway tools read --server Big --start-line 1 --end-line 40
```

Step 3 — docs when the one-line signature is not enough (needs `server` + `tool`).

```bash
mcp-gway tools docs --server Context7 --tool resolve_library_id
```

Step 4 — execute. Two variants, same sandbox, prints `{"result": …, "logs": […]}`.

```bash
# Variant A — inline snippet
mcp-gway tools exec --code 'result = Context7.resolve_library_id(query="react hooks", libraryName="react")'
# {"result": "Available Libraries:\n- Title: React\n- Context7-compatible library ID: /reactjs/react.dev\n…", "logs": []}

# Variant B — script file (better for multi-line / reuse)
cat > run.star << 'EOF'
result = ParallelSearch.web_search(
  objective="Latest features in Python 3.13",
  search_queries=["Python 3.13 new features", "Python 3.13 changelog"])
EOF
mcp-gway tools exec --file run.star
mcp-gway tools exec --file run.star --timeout 10   # seconds, default 30

# Variant C — chain discovery → execution (refresh first when params look stale)
mcp-gway refresh ParallelSearch && \
  mcp-gway tools read --server ParallelSearch && \
  mcp-gway tools exec --code 'result = ParallelSearch.web_fetch(urls=["https://docs.python.org/3.13/whatsnew/3.13.html"])'
```

## Starlark cookbook — what the sandbox allows

L1 validation blocks imports/classes/file-IO/network; L2 sandbox exposes only MCP tools; L3 bounds the timeout; L4 enforces the `tools_to_execute` ACL (`["*"]` = all). Each call runs in a fresh isolated scope — re-fetch or persist via MCP, never assume cross-call state.

```python
# DO — keyword args, bracket access, % formatting, print goes to logs
result = Context7.resolve_library_id(query="react hooks", libraryName="react")
top = result["result"][0:200]
print("hits: %s" % len(result["result"]))

# DO — fan out after step 1 (steps 2-4 run concurrently across servers/tools)
result = ParallelSearch.web_search(objective="Python 3.13 features", search_queries=["Python 3.13 changelog"])

# DON'T — try/except, classes, imports, f-strings, `is`, dot access on dicts
```

Errors you will actually hit: unknown server/tool or blocked Starlark → `Error: …` + exit 1; both/neither of `--code`/`--file` → exit 2; stub with no params (e.g. `def web_search() -> dict`) → run `mcp-gway refresh <name>` and read again.

## Probes + metrics — quick check

```bash
curl -s http://127.0.0.1:8080/health | jq    # {"status":"ok","version":"…","checks":{…},"uptime_seconds":N}
curl -s http://127.0.0.1:8080/ready | jq      # 200 ready / 503 not_ready
curl -s http://127.0.0.1:8080/live | jq       # 200 alive, no FS I/O, <5ms
curl -s http://127.0.0.1:8080/metrics | head -n 20
curl -s -H "X-Request-ID: demo123" http://127.0.0.1:8080/health -D - | grep -i X-Request-ID
```

## Admin dashboard — CLI parity in the browser

`mcp-gway serve --transport http`, then open `http://127.0.0.1:8080/`. Pages: `/` index (= `/admin` alias), `/admin/servers[/{name}]`, `/admin/tools` (Code Mode explorer: list/read/docs/execute forms), `/admin/observability`, `/admin/policy` — plus htmx partials under `/admin/partials/*` (21 routes total, both transports).

Gate: 403 unless the serve host is loopback (fails closed even when bound to `0.0.0.0`). Every mutation needs CSRF (`X-CSRF-Token` header or `_csrf` field, per-process token). Headers/OAuth values are masked in the detail view. OAuth never runs inline — it fires a background task with `refresh --auth` parity. One relaxed CSP constant (`CSP` in `gateway.py`) allows the Tailwind/htmx CDNs.

## Serve security — the short version

Binds `127.0.0.1` by default. `--host 0.0.0.0` without `MCP_GWAY_ALLOW_REMOTE=1` → exit 2. With opt-in → `WARNING: server exposed on non-loopback` in the log; `X-Warning: exposed` appears only on `GET /metrics` → `403`. Never expose without firewall + auth in front. Local-spawn and registry gates live in `mcp-gway-core`.
