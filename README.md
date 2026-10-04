# MCP Gateway

[![PyPI version](https://badge.fury.io/py/mcp-gway.svg)](https://pypi.org/project/mcp-gway/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-gway)](https://pypi.org/project/mcp-gway/)
[![License](https://img.shields.io/pypi/l/mcp-gway)](https://github.com/deuriib/mcp-gateway/blob/main/LICENSE)

One endpoint for every MCP server your agent needs — so it reads tool schemas on demand instead of loading them all upfront.

MCP Gateway aggregates multiple MCP servers behind a single headless HTTP/SSE endpoint. Its **Code Mode** exposes 4 meta-tools (`listToolFiles → readToolFile → getToolDocs → executeToolCode`) so the agent discovers signatures lazily and executes in a hermetic Starlark sandbox. Manage it from the CLI (`mcp-gway`, alias `mgw`) or the built-in admin dashboard: `mcp-gway serve --transport http`, then open `http://127.0.0.1:8080/`.

## Why this exists

- **Fewer wasted tokens** — agents fetch only the schemas they use, when they use them.
- **One connection to manage** — add/remove/refresh servers in one registry; agents see one endpoint.
- **Safe local defaults** — binds `127.0.0.1`, screens local commands through an allow-list, masks secrets, CSRF-protects the dashboard.

## Who it is for

- **Agent developers** wiring OpenCode, Pi, Antigravity, Claude Desktop, or Cursor to many MCP servers through one gateway.
- **Operators** running local-first infrastructure who want a CLI + dashboard with health probes, Prometheus metrics, and JSON logs.

## Features

- **Multi-Server Aggregation** — Connect to multiple MCP servers (`remote` / `local`, OpenCode format) and expose them through a single endpoint — one URL for every agent, one registry to manage
- **Code Mode** — 4 meta-tools that let LLMs discover schemas on demand and execute in a sandbox, instead of loading every tool definition into context
- **OAuth 2.0 Support** — Built-in OAuth flow with dynamic client registration (RFC 7591) and token storage
- **Hermetic Sandbox** — Starlark-based sandbox for safe code execution
- **MCP Protocol Compliant** — Works with OpenCode, Pi, Antigravity, Claude Desktop, Cursor, and any MCP-compatible client

## Installation

```bash
pip install mcp-gway
```

Both `mcp-gway` (canonical) and `mgw` (shortcut, 1:1) are exposed.

Or with [mise](https://mise.jdx.dev/):

```bash
mise install
uv sync --all-groups  # installs dev group with pre-commit
```

## Quick Start

### OpenCode Format (Primary)

OpenCode schema — `remote` / `local` with transport auto-detection. This is the recommended path.

```bash
# Remote — auto-detects transport (streamable-http → sse → http)
mcp-gway add youtube --type remote --url https://api.example.com/mcp
# SSRF-guard: private/loopback/link-local hosts rejected (src/mcp_gway/models.py:115-163); localhost only in tests.

# Remote with headers
mcp-gway add supabase --type remote --url https://mcp.supabase.com/mcp --header "Authorization=Bearer TOKEN"

# Remote with pre-registered OAuth
mcp-gway add supabase --type remote --url https://mcp.supabase.com/mcp --oauth-client-id ID --oauth-client-secret SECRET --oauth-scope "openid profile"

> **Shell-history warning:** never pass real secrets via `--header` / `--oauth-client-secret` (they persist in shell history and process lists). Prefer `mcp-gway refresh <name> --auth` or short-lived env vars.

# Remote with timeout and enable toggle
mcp-gway add api --type remote --url https://api.example.com/mcp --timeout 10000 --enabled
mcp-gway add api --type remote --url https://api.example.com/mcp --timeout 10000 --no-enabled

# Local
mcp-gway add filesystem --type local --command "npx -y @anthropic/mcp-filesystem"
mcp-gway add tools --type local --command "python -m my_mcp_server" --env MY_VAR=value --cwd /path/to/workdir
mcp-gway add tools --type local --command "npx -y my-mcp" --env KEY=VALUE --env OTHER=123 --cwd /srv/mcp/workdir

# List and serve (local-first)
mcp-gway list
mcp-gway serve --transport http --port 8080         # binds 127.0.0.1 by default
mcp-gway serve --transport http --host 127.0.0.1 --port 8080
curl -s http://127.0.0.1:8080/health | jq
```

### Server Types (only `remote` / `local`)

`--type` only accepts `local|remote` (`cli.py:50`). Legacy values `http|stdio|sse|streamable-http` are rejected by click, and `--args` / `--docs-url` do not exist. For `local`, `--command` is a single string (split via `shlex`).

## Management — CLI + Admin Dashboard

Server management (`add`/`remove`/`list`/`inspect`/`refresh`/`--version`) lives in the CLI with full parity in the admin dashboard: `mcp-gway serve --transport http`, then open `http://127.0.0.1:8080/` (pages `/admin/*`, htmx partials `/admin/partials/*`).
One `Gateway(registry, host)` process serves `/mcp`, `/health`, `/ready`, `/live`, `/metrics` and the admin routes on the same `Starlette` app. Registry (`servers/*.json` + `servers/*.pyi`) is the single source of truth. The dashboard is loopback-only and CSRF-protected; the legacy `/dashboard` + catalog surfaces stay retired.

### Local-First Security

```bash
# Secure default — loopback only
mcp-gway serve --transport http --port 8080   # binds 127.0.0.1

# Binding 0.0.0.0 requires explicit opt-in
MCP_GWAY_ALLOW_REMOTE=1 mcp-gway serve --transport http --host 0.0.0.0 --port 8080
# └─ log warning "server exposed on non-loopback host"
# Shield with a firewall + reverse-proxy auth: never expose 0.0.0.0 without both in front.

# Without opt-in → controlled error
mcp-gway serve --transport http --host 0.0.0.0
# Error: binding to non-loopback host '0.0.0.0' requires MCP_GWAY_ALLOW_REMOTE=1
# exit 2
```

## Observability — Logs + Metrics + Health (Approach C, v2.4.0)

> **Zero vendor lock-in:** stdlib `json` logs (no `structlog`), vendored `MetricsRegistry` (no `prometheus_client`), correlation via `X-Request-ID` + `contextvars`, health probes `/health|/ready|/live` + Prometheus text `/metrics`. Local-first + masking `***` preserved; `X-Warning: exposed` only on `GET /metrics` → `403`.

**Health & Metrics:**

```bash
curl -s http://127.0.0.1:8080/health | jq
# {"status":"ok","version":"3.1.0","checks":{"registry":"ok","routes":"ok"},"uptime_seconds":42}
curl -s http://127.0.0.1:8080/ready | jq   # 200 ready / 503 not_ready (registry/routes/event_loop checks)
curl -s http://127.0.0.1:8080/live | jq    # 200 alive — no FS I/O, <5ms
curl -s http://127.0.0.1:8080/metrics | head -n 20
# # HELP mcp_gway_http_requests_total Total HTTP requests
# # TYPE mcp_gway_http_requests_total counter
# mcp_gway_http_requests_total{method="GET",path="/health",status="200"} 7
```

**Correlation & JSON logs:**

```bash
curl -s -H "X-Request-ID: demo123" http://127.0.0.1:8080/health -D - | grep -i X-Request-ID
# X-Request-ID: demo123  ← echo on every response; json log line also has "request_id":"demo123"
uv run mcp-gway serve --transport http --port 8080 2>&1 | head   # each line valid JSON: timestamp, level, logger, message, request_id, method, path, status, duration_ms
```

- `X-Request-ID` or `X-Correlation-ID` accepted, sanitized to `^[A-Za-z0-9_-]{1,64}$`, truncated; auto `uuid4` if absent.
- Labels bounded: `path` collapsed to `/mcp` or `/mcp/messages` (SSE alias to the same `_mcp_post` handler, not a separate endpoint; all other routes recorded as-is), server sanitized `[^A-Za-z0-9_]`→`_` 32 chars.
- Metrics: `http_requests_total`, `http_request_duration_seconds` (buckets 0.005..5), `mcp_tool_calls_total{server,tool,status}`, `discovery_duration_seconds`, `sandbox_execute_total{status}`, `registry_operations_total{op}`, `gateway_sessions_active`.

**FEAT-007 hardening (v2.2.1):** process/build lifecycle, stdio coverage, upstream telemetry, cardinality cap.

- Lifecycle: `build_info{version}`, `process_start_time_seconds`, `uptime_seconds` (heartbeat, 30s tick), `lifetime_seconds` (set at shutdown) + a JSON `gateway shutdown summary` (uptime + totals) on exit.
- stdio (`serve --transport stdio`, default): per-request `stdio_requests_total{method,status}` + `stdio_request_duration_seconds{method}` and a JSON access log (`transport:"stdio"`, same shape as HTTP).
- Upstream CodeMode calls (tool execution): `upstream_tool_calls_total{server,tool,status}` (`ok`/`timeout`/`error`), `upstream_tool_duration_seconds{server,tool}`; opt-in retries counted in `upstream_retries_total{server}`.
- Corruption visibility: `code_mode_servers_skipped_total{reason}` + structured WARN + degraded banner hint (`mcp-gway refresh <name>`) when a server fails injection at startup.
- Label cardinality hard-capped per metric (`_MAX_LABEL_COMBOS=200`); overflow coalesces into a reserved `_other` series so a label storm cannot grow memory without bound.
- Slow-request WARN: requests over `_SLOW_REQUEST_THRESHOLD_MS` (1000) additionally log a `slow request` JSON line with duration.
- CLI structured outcomes: `cli <action> <status>` JSON events — WARNING always emitted, INFO only when `MCP_GWAY_LOG_LEVEL` is set (zero operator noise by default).
- New opt-in flag: `mcp-gway add --retry-on-transport-error` — retries exactly once ONLY when the transport/connect phase fails (never after the tool call starts; non-idempotency-safe, ADR-012 decision 9). Default off → zero behavior change.

**Local-first gating:** `/metrics` never leaks secrets; `serve` on non-loopback without `MCP_GWAY_ALLOW_REMOTE=1` exits 2; `X-Warning: exposed` only on `GET /metrics` → `403` (src/mcp_gway/observability/health.py:127-139).

## Connect from Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gateway": {
      "url": "http://localhost:8080/mcp"
    }
  }
}
```

> **Transport note:** gateway pairing is transport-agnostic — the routes are per-transport (`serve --transport http` → `POST /mcp` only; `serve --transport sse` → `GET /mcp` + `POST /mcp/messages` only). A mispaired client gets `405` + `Allow` header telling it which transport serves that method. If you upgrade from v2.x, see [MIGRATION.md](MIGRATION.md).

## Commands

| Command                                                                                                                      | Description                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `mcp-gway add --type remote\|local`                                                                                          | Add an MCP server and generate `.pyi` stub (OpenCode format, primary)                                                                                                                                                                                                                                                                                                                                                                               |
| `mcp-gway remove`                                                                                                            | Remove an MCP server                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `mcp-gway update`                                                                                                            | Update tools for a server                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `mcp-gway list`                                                                                                              | List all connected servers                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `mcp-gway inspect`                                                                                                           | Show tool signatures for a server                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `mcp-gway refresh [<name>] [--auth] [--oauth-port <port>]`                                                                   | Refresh connection and re-discover tools                                                                                                                                                                                                                                                                                                                                                                                                            |
| `mcp-gway serve [--transport stdio\|http\|sse] [--host 127.0.0.1] [--port <port>] [--log-level LEVEL] [--registry-dir PATH]` | Start gateway (default `stdio`; `--host/--port` only with `http\|sse`). Per-transport `/mcp` (separate apps, no fallback): `http` → `POST /mcp` only (6 routes; `GET` → 405 `Allow: POST`), `sse` → `GET /mcp` + `POST /mcp/messages` (7 routes; `POST` → 405 `Allow: GET`); probes shared; stdio keeps stdout pure NDJSON. Default `127.0.0.1`; `0.0.0.0` requires `MCP_GWAY_ALLOW_REMOTE=1`. v2.x → v3.0.0 breaking: [MIGRATION.md](MIGRATION.md) |
| `mcp-gway mcp [--log-level LEVEL] [--registry-dir PATH]`                                                                     | DEPRECATED hidden alias: equivalent to `serve --transport stdio` — same NDJSON loop and same args to `_serve_stdio`, except for the deprecation notice on stderr (only under `mcp`). Prefer `command: [mcp-gway, serve, --transport, stdio]` for OpenCode `type: local`                                                                                                                                                                             |
| `mcp-gway --version` / `-v`                                                                                                  | Print the package version                                                                                                                                                                                                                                                                                                                                                                                                                           |

> **Types:** only `--type local|remote` (`cli.py:50`). Legacy `http|stdio|sse|streamable-http` are rejected by click. There is no `--args` / `--docs-url`.

Options for `add` (OpenCode) — 13 flags (cli.py:45-95):

| Option                         | Description                                      |
| ------------------------------ | ------------------------------------------------ |
| `--type remote\|local`         | Server type (primary)                            |
| `--url <url>`                  | URL for `remote`                                 |
| `--header "KEY=VALUE"`         | HTTP header for `remote` (repeatable)            |
| `--command "<cmd>"`            | Command for `local` (e.g. `"npx -y my-mcp"`)     |
| `--env KEY=VALUE`              | Environment variable for `local` (repeatable)    |
| `--cwd <path>`                 | Working directory for `local`                    |
| `--oauth-client-id ID`         | Pre-registered OAuth client ID                   |
| `--oauth-client-secret SECRET` | Pre-registered OAuth client secret               |
| `--oauth-scope SCOPE`          | OAuth scope                                      |
| `--oauth-port <port>`          | Local port for OAuth callback (default 8989)     |
| `--timeout <ms>`               | Connection timeout in ms (default 5000)          |
| `--enabled / --no-enabled`     | Enable/disable without removal (default enabled) |
| `--tools <list>`               | Comma-separated tool filter (default `*` = all)  |

## Local Commands — Dynamic Allow-List (feat-006)

> **Dynamic-no-static:** no hardcoded binaries. Operators allow-list once via env; see [ADR-009](docs/architecture/adr-009-dynamic-local-commands.md).

**Allow-list:** `MCP_GWAY_ALLOW_LOCAL_COMMANDS` (CSV basenames; unset/blank → defaults `npx,bunx,uvx,pipx`); `*`/paths/invalid entries → deny + warn.

Recommended: `MCP_GWAY_ALLOW_LOCAL_COMMANDS="npx,uvx,python3,bunx"`.

```bash
# Allow-list (CSV basenames, `*` = invalid → deny + warn)
export MCP_GWAY_ALLOW_LOCAL_COMMANDS="npx,uvx,python3,bunx"
mcp-gway add fs --type local --command "npx -y @anthropic/mcp-filesystem" --cwd /srv/mcp/workdir
```

- CISO opt-in note: `bunx` is docs-recommended only (not a code default; empty allow-list still denies); opt-in only with pin + owner + 90-day re-gate; `bun` runtime stays out; denylist EXACT PATH,PATHEXT,SYSTEMROOT,COMSPEC,LD_PRELOAD,LD_LIBRARY_PATH,PYTHONPATH,PYTHONHOME,NODE_OPTIONS,NODE_PATH,NODE_EXTRA_CA_CERTS,NODE_TLS_REJECT_UNAUTHORIZED + PREFIXES DYLD_,NPM_CONFIG_,BUN_,UV_ + controlled PATH (`NODE_ENV` allowed, not denylisted); `*`, paths, and shell are prohibited.
- Internal tag `v2.0.0` — not published, no external announcement. After upgrading, delete the stale cache manually: `rm ~/.config/mcp-gway/catalog.json`.

- `unset` returns to allow-list mode.
- CLI `add`/`refresh` enforces the allow-list plus re-validation before persist.
- `cwd` must be absolute + real + `is_dir`, else `reason_code=invalid_cwd`. Env denylist (`PATH`, `LD_PRELOAD`, `PYTHONPATH`, …) → `reason_code=denied_env`.
- Spawn only resolved via PATH lookup (`shutil.which(basename)`); never `shell=True` / `cmd /c` / `sh -c`. Errors carry `reason_code` (`not_allowlisted`, `binary_not_found`, …).

## Code Mode

When connected, the gateway exposes 4 meta-tools:

| Tool              | Description                                      |
| ----------------- | ------------------------------------------------ |
| `listToolFiles`   | List all available `.pyi` stub files             |
| `readToolFile`    | Read function signatures from a stub             |
| `getToolDocs`     | Get detailed documentation for a tool            |
| `executeToolCode` | Execute code in a sandboxed Starlark interpreter |

## OAuth Authentication

For servers requiring OAuth (e.g., Supabase):

```bash
# Trigger the OAuth flow (preferred — keeps secrets out of shell history)
mcp-gway refresh supabase --auth

# Or store a token manually (fallback only; chmod 600 required)
mkdir -p ~/.config/mcp-gway/tokens
echo '{"access_token": "YOUR_TOKEN"}' > ~/.config/mcp-gway/tokens/supabase.json
chmod 600 ~/.config/mcp-gway/tokens/supabase.json
```

## Development

```bash
# Install dependencies
uv sync --all-groups  # installs dev group with pre-commit
uv run pre-commit install  # once per clone — hooks already configured in .pre-commit-config.yaml

# Run checks
uv run pre-commit run --all-files  # ruff + ruff-format + hygiene (trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files)
uv run pytest -v  # 570 tests — CLI, MCP, Code Mode, stdio, OAuth, observability
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Verification probes (no Node, no build)
curl -s http://127.0.0.1:8080/health | jq .status             # "ok"
curl -s http://127.0.0.1:8080/ready | jq .status              # "ready"
curl -s http://127.0.0.1:8080/metrics | head -n 5             # # HELP mcp_gway_...

# Local-first check
mcp-gway serve --transport http --host 0.0.0.0 2>&1 | grep -q "requires MCP_GWAY_ALLOW_REMOTE" && echo "gate ok"
```

Pre-commit is already in place (`.pre-commit-config.yaml` — `ruff` v0.16.4, `ruff-format`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-added-large-files`).

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        MCP Gateway v4.0.0                          │
├──────────────────────────────────────────────────────────────────────┤
│  CLI (click)              │  Gateway (Starlette + uvicorn, CSP)      │
│  - add remote/local       │  - POST /mcp (JSON-RPC)      [http]      │
│  - remove/inspect/list    │  - GET  /mcp (SSE endpoint event)  [sse] │
│  - refresh --auth         │  - POST /mcp/messages (alias) [sse]      │
│  - serve --host 127.0.0.1 │  - GET  /health                          │
│  (local-first default)    │  - GET  /ready, /live, /metrics           │
├──────────────────────────────────────────────────────────────────────┤
│  Code Mode (4 meta-tools)      │  Starlark Sandbox                    │
│  - listToolFiles               │  - Hermetic execution                │
│  - readToolFile                │  - Server injection                  │
│  - getToolDocs                 │                                      │
│  - executeToolCode             │                                      │
├──────────────────────────────────────────────────────────────────────┤
│  Registry (single source)      │  OAuth2 (RFC 7591, reutilizado)      │
│  - servers/*.pyi = signatures  │  - Dynamic registration              │
│  - servers/*.json = config     │  - PKCE + FileTokenStorage           │
│  - last-write-wins, atomic     │  - tokens/ never exposed via API     │
└──────────────────────────────────────────────────────────────────────┘
         │                │                │
    ┌────┴────┐      ┌────┴────┐      ┌────┴────┐
    │ Server1 │      │ Server2 │      │ Server3 │
    │ (remote)│      │ (local) │      │ (remote)│
    └─────────┘      └─────────┘      └─────────┘
```

## License

MIT
