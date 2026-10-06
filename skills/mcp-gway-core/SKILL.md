---
name: mcp-gway-core
description: Internals of the gateway (v4.2.0) — registry .pyi/.json, config files, every MCP_GWAY_* env var, local-command policy gates, sandbox, transports, OAuth, observability, admin backend. Use when debugging execution, auth, discovery, or the allow-list.
---

# mcp-gway core internals

How the gateway stores, gates, and runs things. CLI (`mcp-gway-cli`) and serve/MCP (`mcp-gway-mcp`) are the surfaces — this is what sits underneath them.

## Config files — where everything lives

All state is files under `~/.config/mcp-gway/` (honors a `HOME` override, so `HOME=/tmp/x` relocates everything — used by tests for isolation):

| Path | Contents | Managed by |
|------|----------|------------|
| `servers/<Name>.json` | Server config: `type`, `url`/`command`, `env`, `headers`, `tools`, `timeout`, `enabled`, OAuth refs | `add` / `refresh` / `update` (atomic `.json` + `.pyi` together, last-write-wins) |
| `servers/<Name>.pyi` | Signatures only — what Code Mode reads | `refresh` re-discovers; `inspect` prints |
| `tokens/<Name>.json` | OAuth access tokens | `refresh --auth` (`0o600` via `_secure_atomic_write`) |
| `tokens/<Name>_client.json` | Dynamic-registration client credentials (RFC 7591) | OAuth flow; deleted with `remove` |

`remove <name>` deletes the server entries AND both token files. Legacy `#` comments in `.pyi` exist only for fallback migration. Stale cache from the retired catalog (`~/.config/mcp-gway/catalog.json`) should be deleted manually — nothing reads it.

```bash
ls ~/.config/mcp-gway/servers/          # Context7.json  Context7.pyi  …
cat ~/.config/mcp-gway/servers/Context7.json | jq '{name,type,url,timeout,enabled}'
HOME=/tmp/isolated mcp-gway list        # same CLI, isolated registry
mcp-gway serve --transport http --registry-dir ./servers   # override servers dir per-run
```

A minimal remote entry looks like this — `resolved_transport` is filled in by auto-detection, not by hand:

```json
{
  "name": "Context7",
  "type": "remote",
  "enabled": true,
  "timeout": 5000,
  "is_code_mode_client": true,
  "tools_to_execute": ["*"],
  "url": "https://mcp.context7.com/mcp",
  "resolved_transport": "streamable-http"
}
```

## ENV vars — the complete table

Only six `MCP_GWAY_*` vars exist. Everything else is flags or files.

| Variable | Effect | Default | Used in |
|----------|--------|---------|---------|
| `MCP_GWAY_ALLOW_LOCAL_COMMANDS` | CSV basenames allowed for `local` spawns (case-insensitive). Explicit value **overrides** defaults. `*`/paths/invalid → deny + warn. **Do NOT rename.** | `{npx,bunx,uvx,pipx}` when unset/blank | `core/policy.py:28,77` |
| `MCP_GWAY_ALLOW_REMOTE` | `=1` permits `serve --host 0.0.0.0`. Anything else → exit 2 on non-loopback | unset (loopback-only) | `cli.py:627`, `observability/health.py:134` |
| `MCP_GWAY_LOG_LEVEL` | `trace/debug/info/warning/error/critical` (`warn` → `warning`). CLI INFO events emit only when set; WARN/ERROR always | `info` | `cli.py:67,529`, `--log-level` overrides it per-run |
| `MCP_GWAY_URL` | Gateway endpoint override (agent plugins) | `http://127.0.0.1:8080/mcp` | plugins, not the server |
| `MCP_GWAY_TOKEN` | Bearer token sent as `Authorization: Bearer …` (never written to `.mcp.json`) | unset (no auth header) | plugins, not the server |
| `HOME` | Relocates the whole `~/.config/mcp-gway/` tree (POSIX override; `Path.home()` ignores it on Windows) | real home | `core/policy.py:22` (`home_dir()`) |

```bash
# Variant 1 — defaults (runner shims only, loopback, info logs)
unset MCP_GWAY_ALLOW_LOCAL_COMMANDS
mcp-gway serve --transport http --port 8080

# Variant 2 — widen local runners for a project
export MCP_GWAY_ALLOW_LOCAL_COMMANDS="npx,uvx,python3,bunx"
mcp-gway add fs --type local --command "npx -y @modelcontextprotocol/server-filesystem /srv/data"

# Variant 3 — expose + debug (firewall + auth required in front)
MCP_GWAY_ALLOW_REMOTE=1 MCP_GWAY_LOG_LEVEL=debug \
  mcp-gway serve --transport http --host 0.0.0.0 --port 8080

# Variant 4 — client-side endpoint/token without touching files
MCP_GWAY_URL=http://127.0.0.1:9090/mcp MCP_GWAY_TOKEN=secret-xyz pi -e ./
```

## Policy gates — allow-list + cwd/env (`core/policy.py`, ADR-009)

Three gates run on every local spawn (`add` / `refresh` / `tools exec` → `client.py` / `server_factory.py` via `check_local_command(…, require_binary=True)` + `audit_local_action`). Denied → `PermissionError` / exit 1 with the policy message and a `reason_code` — never silent.

**Gate 1 — command allow-list.** Basename must be in the set from `get_allow_list()`; lookup is `basename.lower()`; binary must resolve via `shutil.which` (`require_binary=True`). Command shape: 1–8 tokens, basename only (no `/`, `\`, `:`), args match `^[A-Za-z0-9_./:@-]{1,80}$`. No `shell=True` / `cmd /c` / `sh -c` anywhere.

```bash
export MCP_GWAY_ALLOW_LOCAL_COMMANDS="npx,uvx,python3"
mcp-gway add ok --type local --command "npx -y my-mcp"          # allowed
mcp-gway add bad --type local --command "./evil-mcp"           # denied [not_allowlisted — path]
mcp-gway add bad2 --type local --command "python -m x"         # denied unless python3/python in list
export MCP_GWAY_ALLOW_LOCAL_COMMANDS="*"                       # wildcard → deny + warn, nothing allowed
```

**Gate 2 — cwd.** `--cwd` must be absolute, real, and a directory (`check_cwd`), else `reason_code=invalid_cwd`.

```bash
mcp-gway add t --type local --command "npx -y my-mcp" --cwd /srv/mcp/workdir   # ok
mcp-gway add t --type local --command "npx -y my-mcp" --cwd rel/path           # Error: invalid_cwd
```

**Gate 3 — env.** `--env KEY=VALUE` rejects denylisted names (`reason_code=denied_env`). Exact: `PATH,PATHEXT,SYSTEMROOT,COMSPEC,LD_PRELOAD,LD_LIBRARY_PATH,PYTHONPATH,PYTHONHOME,NODE_OPTIONS,NODE_PATH,NODE_EXTRA_CA_CERTS,NODE_TLS_REJECT_UNAUTHORIZED`. Prefixes: `DYLD_*,NPM_CONFIG_*,BUN_*,UV_*`. `PATH` itself is controlled, not pass-through. `NODE_ENV` is allowed. `bunx` ships in `DEFAULT_ALLOW_LIST` as a runner shim; widening the list needs pin + owner + 90-day re-gate; the `bun` runtime stays out.

## Execution stack — CodeMode → factory → sandbox

`code_mode.py` — `CodeMode(registry)` + `to_pascal_case_identifier` (names normalize to PascalCase; hyphens in upstream tool names become underscores in the sandbox). Methods: `list_tool_files` / `read_tool_file` / `get_tool_docs` / `execute_tool_code` (+ agent helpers `classify_tool_calls`, `execute_agent_tool`, `auto_execute`). Tool ACL comes from `tools_to_execute` (`["*"]` = all) — `update <name> --tools` rewrites it without re-discovery.

`server_factory.py` — per-server structs with sanitized identifiers, `_check_tool_allowed` (ACL enforcement), `_call_tool_async` with per-config timeout + upstream telemetry (`upstream_tool_calls_total{server,tool,status}`, `upstream_tool_duration_seconds{server,tool}`). Retry is transport-phase only and opt-in (`--retry-on-transport-error`): exactly one retry when connect fails, never after `call_tool` starts (ADR-012).

`sandbox.py` — Starlark via `starlark-pyo3`: `struct(Server.tool=callable)`, fresh isolated scope per `execute()`, `result` assignment required, `print()` → logs, `SandboxTimeoutError` on deadline, degrade-visible skips counted in `code_mode_servers_skipped_total{reason}`.

`core/transport.py` + `core/client.py` — remote auto-detect `streamable-http → sse → http` (`detect_transport`); `create_client_transport` (local|remote), `discover_tools`, `refresh_server`; `parsing.py` — `parse_headers`/`parse_envs` (`KEY=VALUE`, repeatable flags).

## Remote + OAuth (`oauth.py`, `models.py`)

SSRF-guard on every `remote --url` (`models.py`): only `http|https`; private/loopback/link-local/reserved/multicast hosts rejected. Example live value: `https://api.example.com/mcp`.

OAuth flow, in order: RFC 8707 protected-resource discovery → authorization-server metadata → RFC 7591 dynamic client registration → PKCE authorization-code flow → tokens in `tokens/` (`0o600`). `refresh` tries anonymous discovery first and falls back to OAuth only for remote servers with empty discovery; `--auth` forces re-auth even with tokens; fail-closed (`PermissionError` when `force_auth` and no tokens).

```bash
mcp-gway refresh supabase --auth                      # preferred — secrets stay out of shell history
mcp-gway refresh supabase --auth --oauth-port 9999    # custom callback port
# Fallback only: hand-place a token, then lock it down
mkdir -p ~/.config/mcp-gway/tokens
echo '{"access_token": "YOUR_TOKEN"}' > ~/.config/mcp-gway/tokens/supabase.json
chmod 600 ~/.config/mcp-gway/tokens/supabase.json
```

## Observability (`observability/`) — probes, logs, metrics

Probes (always on for `http|sse`): `/health` (`{"status","version","checks","uptime_seconds"}`), `/ready` (200/503), `/live` (200, no FS I/O, <5ms), `/metrics` (hand-rolled Prometheus text via `MetricsRegistry` — no `prometheus_client`). JSON logs to stderr (`JSONFormatter`, `request_id` ContextVar); `Correlation`/`Metrics`/`Logging` middlewares echo `X-Request-ID` (or `X-Correlation-ID`, sanitized `^[A-Za-z0-9_-]{1,64}$`, auto-`uuid4` when absent) on every response. CLI writes emit `_log_cli_event` (WARN/ERROR always; INFO only with `MCP_GWAY_LOG_LEVEL`).

```bash
curl -s http://127.0.0.1:8080/health | jq
curl -s http://127.0.0.1:8080/metrics | head -n 20
curl -s -H "X-Request-ID: demo123" http://127.0.0.1:8080/health -D - | grep -i X-Request-ID
```

Key series: `http_requests_total{method,path,status}`, `http_request_duration_seconds` (buckets 0.005…5), `mcp_tool_calls_total{server,tool,status}`, `discovery_duration_seconds`, `sandbox_execute_total{status}`, `registry_operations_total{op}`, `gateway_sessions_active`, `build_info{version}`, `process_start_time_seconds`, `uptime_seconds` (30s heartbeat), `lifetime_seconds` + JSON shutdown summary, stdio `stdio_requests_total{method,status}`, upstream `upstream_retries_total{server}`, `code_mode_servers_skipped_total{reason}`. Label cardinality is hard-capped (`_MAX_LABEL_COMBOS=200`, overflow → `_other`); slow requests (>1000ms) add a `slow request` JSON line. `/metrics` never leaks secrets; on exposed hosts it returns 403 with `X-Warning: exposed`.

## Admin backend — the routes the dashboard calls

`/` index (= `/admin` alias) + 6 pages + 14 htmx partials under `/admin/partials/*` — 21 admin routes on both transports, appended to the same Gateway app. Loopback gate (403 unless serve host is loopback — fails closed even when bound to `0.0.0.0`), per-process CSRF token on every mutation (`X-CSRF-Token` or `_csrf`), headers/OAuth masked in detail views, OAuth as background task with `refresh --auth` parity, single relaxed `CSP` constant for the Tailwind/htmx CDNs.

| Page | What the operator does there |
|------|------------------------------|
| `/admin/servers[/{name}]` | Add / inspect / enable-disable / remove / refresh / re-auth one server |
| `/admin/tools` | Code Mode explorer: list → read → docs → execute forms |
| `/admin/observability` | Health, probes, live metrics |
| `/admin/policy` | Read-only view of `MCP_GWAY_ALLOW_LOCAL_COMMANDS` + `MCP_GWAY_ALLOW_REMOTE` as the process sees them |

## Retired — do not serve or rebuild

Legacy dashboard (`/dashboard`, `/api/servers`, `/static`) and catalog (`/api/catalog`, `/dashboard/catalog`, `catalog.json`) are removed since v2.0.0. `/` is the admin index now, not the legacy dashboard. No `local-unrestricted` — removed in v4.0.0, no bypass exists.
