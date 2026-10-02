---
name: mcp-gway-core
description: Internals of the gateway (v3.1.0) — registry .pyi/.json, policy gates, sandbox, transports, OAuth. Use when debugging execution, auth, discovery, or the allow-list.
---

# mcp-gway core internals

## Registry — single source of truth (`registry.py`)

`servers/*.json` (OpenCode config: type/url/command/…) + `servers/*.pyi` (signatures only).
Writes are atomic (`.json` + `.pyi` together), last-write-wins for concurrent CLI writes.
Legacy `#` comments only for fallback migration. Kept by CLI (`add`/`refresh`/`update`) and read by Code Mode.

## Policy gates (`core/policy.py`, ADR-009)

- Allow-list `MCP_GWAY_ALLOW_LOCAL_COMMANDS` (CSV basenames, case-insensitive); unset/blank → `DEFAULT_ALLOW_LIST {npx,bunx,uvx,pipx}` (`policy.py:23`). Explicit value overrides. `*`/paths invalid → deny + warn. Do NOT rename `MCP_GWAY_ALLOW_LOCAL_COMMANDS` / `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL`.
- Break-glass: `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL=1` + marker `~/.config/mcp-gway/.local_unrestricted` (epoch, `0o600`, 72h TTL `UNRESTRICTED_TTL_SECONDS`). Env alone never activates; `local-unrestricted enable|disable|status` manages the marker explicitly.
- cwd/env gates: `--cwd` must be absolute (`check_cwd`); denylist EXACT `PATH,PATHEXT,SYSTEMROOT,COMSPEC,LD_PRELOAD,LD_LIBRARY_PATH,PYTHONPATH,PYTHONHOME,NODE_OPTIONS,NODE_PATH,NODE_EXTRA_CA_CERTS,NODE_TLS_REJECT_UNAUTHORIZED` + prefixes `DYLD_,NPM_CONFIG_,BUN_,UV_` + controlled `PATH` (`NODE_ENV` allowed). `*`, paths, shell prohibited. `bunx` is in `DEFAULT_ALLOW_LIST` (runner shim); widening the list needs pin + owner + 90d re-gate; `bun` runtime stays out.
- Every local spawn (`add`/`refresh`/`tools exec` → `client.py`/`server_factory.py`) runs `check_local_command(…, require_binary=True)` + `audit_local_action`. Denied → `PermissionError`/exit 1 with the policy message.

## Execution stack

- `code_mode.py` — `CodeMode(registry)` + `to_pascal_case_identifier`; `list_tool_files` / `read_tool_file` / `get_tool_docs` / `execute_tool_code`; Bifrost agent helpers (`classify_tool_calls`, `execute_agent_tool`, `auto_execute`). Tool ACL: `tools_to_execute` (`["*"]` = all).
- `server_factory.py` — per-server structs, sanitized identifiers (hyphens → underscores), `_check_tool_allowed`; `_call_tool_async` with per-config timeout + upstream telemetry; transport-phase retry only with opt-in `retry_on_transport_error` (never re-runs `call_tool`).
- `sandbox.py` — Starlark (`starlark-pyo3`), `struct(Server.tool=callable)`, fresh isolated scope per `execute()`, `result` assignment required, `print()` → logs, `SandboxTimeoutError` on deadline, degrade-visible skips (`code_mode_servers_skipped_total`).
- `core/transport.py` — remote auto-detect `streamable-http → sse → http`; `core/client.py` — `create_client_transport` (local|remote), `discover_tools`, `refresh_server`; `parsing.py` — `parse_headers`/`parse_envs` (`KEY=VALUE`).

## Remote + OAuth

- SSRF-guard (`models.py`): `remote --url` https-only, private/loopback/link-local/reserved/multicast rejected.
- OAuth flow (`oauth.py`): RFC 8707 resource discovery → server metadata → RFC 7591 dynamic registration → PKCE code flow → tokens in `~/.config/mcp-gway/tokens/` (`0o600` via `_secure_atomic_write`). Prefer `refresh --auth`; fail-closed (`PermissionError` when `force_auth` and no tokens). `refresh` tries anonymous first, falls back to OAuth only for remote with empty discovery.

## Observability (`observability/`)

Probes `/health`, `/ready`, `/live`, `/metrics`; JSON logs to stderr (`JSONFormatter`, `request_id` ContextVar); `Correlation`/`Metrics`/`Logging` middlewares; hand-rolled Prometheus exposition (`MetricsRegistry`). CLI writes emit `_log_cli_event` (WARN/ERROR always to stderr; INFO only with `MCP_GWAY_LOG_LEVEL`).

## Retired (do not serve)

Legacy dashboard (`/dashboard`, `/api/servers`, `/static`) and catalog (`/api/catalog`, `/dashboard/catalog`, Bifrost fetch, `~/.config/mcp-gway/catalog.json` — delete old cache manually). `/` is the admin index now, not the legacy dashboard.
