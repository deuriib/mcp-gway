# AGENTS.md

## Project Overview

**MCP Gateway** — A standalone Python CLI that aggregates multiple MCP servers behind a single headless HTTP/SSE endpoint with Code Mode, plus an admin web dashboard at `/` (htpy + htmx + Tailwind CDN, v3.1.0 Unreleased — reintroduces management UI; CLI sigue canónico, catalog permanece retirado).

> **Nota interna:** ver `CHANGELOG.md` (al día hasta v3.0.0, 2026-09-22). Releases internos no publicados — no anuncio externo.

## Tech Stack

- **Language**: Python 3.12+
- **Package Manager**: uv (with mise for tool versions)
- **CLI Framework**: click
- **HTTP Server**: Starlette + uvicorn
- **MCP SDK**: mcp v2.0.0
- **Sandbox**: starlark-pyo3
- **Testing**: pytest + pytest-asyncio (621 tests)
- **Linting**: ruff
- **Nota**: `htpy` reintroducido en v3.1.0 (Unreleased, `htpy==26.5.1`) como renderer del dashboard admin — retirado en v2.0.0, ahora re-admitido; `httpx` v1 eliminado en favor de `httpx2` (dependencia directa, alineada con mcp v2 y starlette 1.6).
- **Dashboard**: htpy (server rendering) + htmx 2.0.10 + Tailwind — ambos vía CDN (`cdn.jsdelivr.net`, `cdn.tailwindcss.com`); CSP relajado en la constante única `CSP` de `gateway.py` (`script-src` CDNs, `style-src 'unsafe-inline'`, `frame-ancestors 'none'`).

## Project Structure

```
src/mcp_gway/
├── __init__.py          # Package version (3.1.0)
├── models.py            # Pydantic models (MCPServerConfig OpenCode-only local|remote, ToolInfo, OAuthConfig)
├── registry.py          # .pyi file CRUD (servers/ directory) — única fuente de verdad
├── sandbox.py           # Starlark sandbox (hermetic execution)
├── server_proxy.py      # MCP server wrapper for sandbox
├── server_factory.py    # Server structs + sync call wrappers for the sandbox
├── code_mode.py         # 4 meta-tools orchestrator
├── gateway.py           # HTTP/SSE server (JSON-RPC 2.0), local-first 127.0.0.1 + CSP — rutas /mcp por transporte (gateway.py:320-340, mcp_routes condicional; app.state.transport; sin fallback): http = POST /mcp (GET → 405 Allow: POST) + /health, /ready, /live, /metrics → 6 entradas; sse = GET /mcp (SSE) + POST /mcp → 405 Allow: GET + /mcp/messages (alias POST al handler _mcp_post, no endpoint independiente) + probes → 7 entradas
├── cli.py               # CLI commands (add/remove/update/list/inspect/refresh/serve --transport stdio|http|sse/mcp-hidden/--version --host 127.0.0.1)
├── admin/               # Admin dashboard: theme, components, icons (SVG authored), layout, data, routes + pages/{status,overview,servers,tools,observability,policy} (htpy+htmx, CDN)
├── oauth.py             # OAuth2 support (dynamic registration, token storage); usa httpx2 (dependencia directa)
├── transport.py         # Shim deprecado → mcp_gway.core.transport (DeprecationWarning; eliminar en next major)
├── stdio.py             # SERVIDOR-side NDJSON: lee JSON-RPC 2.0 de stdin, responde por stdout (`mcp-gway serve --transport stdio`; `mcp` alias deprecado)
├── stdio_transport.py   # CLIENT-side: filtered_stdio_client conecta a niños MCP y filtra ruido no-JSON de su stdout
├── core/
│   ├── __init__.py      # Re-exports (create_client_transport, detect_transport, discover_tools, parse_envs/headers, refresh_server)
│   ├── transport.py     # Auto-detección de transporte remote (streamable-http → sse → http)
│   ├── policy.py        # Allow-list local (ADR-009), cwd/env gates, audit
│   ├── parsing.py       # parse_headers / parse_envs (KEY=VALUE)
│   ├── install.py       # Discovery + persist helpers (semáforo 3, oauth fallback)
│   └── client.py        # create_client_transport (local|remote), discover_tools, refresh_server
└── observability/
    ├── __init__.py      # Re-exports (JSONFormatter, MetricsRegistry, request_id_ctx, setup_logging)
    ├── logging.py       # JSONFormatter (stderr), request_id ContextVar, setup_logging
    ├── middleware.py    # Correlation (X-Request-ID), Metrics, Logging middlewares
    ├── metrics.py       # MetricsRegistry hand-rolled Prometheus exposition (counter/gauge/histogram)
    └── health.py        # /health, /ready, /live, /metrics (X-Warning: exposed gating)

> **Retirado en v2.0.0 (no servir):** dashboard legacy (`/dashboard`, `/api/servers`, `/static`) y catalog (`/api/catalog`, `/dashboard/catalog`, Bifrost fetch, `~/.config/mcp-gway/catalog.json`). El alias `/` fue reactivado en v3.1.0 como índice del admin (`/admin*`) — superficie nueva, no el dashboard legacy.

tests/
├── conftest.py                 # Fixtures compartidos
├── test_models.py              # Model validation tests (+ SSRF guard)
├── test_registry.py            # Registry CRUD tests (path traversal/symlink)
├── test_sandbox.py             # Sandbox execution tests
├── test_server_proxy.py        # Server proxy tests
├── test_server_factory.py      # Server factory structs + call wrappers
├── test_code_mode.py           # Code mode tests
├── test_gateway.py             # HTTP/SSE server tests
├── test_admin_dashboard.py     # Admin dashboard (pages, partials, CSRF, loopback gate, parity mutations)
├── test_cli.py                 # CLI command tests
├── test_integration.py         # End-to-end flow tests
├── test_transport.py           # Transport auto-detection tests
├── test_stdio.py               # Server-side NDJSON (mcp-gway mcp) tests
├── test_stdio_transport.py     # Client-side filtered stdio tests
├── test_policy_local_commands.py  # feat-006 allow-list policy tests
├── test_policy_local_commands.py  # feat-006 allow-list policy tests
├── test_feat006_harden.py      # feat-006 hardening tests (PATCH bypass, regates)
├── test_p0_fixes.py            # P0 regression fixes
├── test_wave2_api.py           # Wave-2 API asserts (CSP header etc.)
└── test_observability_*.py     # metrics / logging / probes / instrumentation

docs/
├── specs/SPEC-UI-001.md (+ SCENARIOS/ACCEPTANCE)  # SUPERSEDED 2026-09-10 (retirado; headless, CLI-only) — reversado parcial 2026-09-23: admin UI nueva en `/` + `/admin*` (v3.1.0 Unreleased, spec distinta)
├── adr/ADR-007-release-workflow-hybrid.md, ADR-008-catalog-mcp-001.md
├── architecture/adr-009-dynamic-local-commands.md, adr-010-unified-serve.md (referenciado, ausente en repo; enmienda ADR-010 AC-05 2026-09-22: http/sse comparten el entrypoint `_serve_http`, NO la app — rutas `/mcp` separadas por transporte, sin fallback)
├── sbtdd/specs/feat-006-dynamic-local-commands/   # spec + scenarios + acceptance + verify
├── superpowers/plans/                             # Planes fechados (históricos)
└── superpowers/specs/2026-08-2X-*                 # Specs de diseño (históricos)
```

## Commands

```bash
# Development
uv sync --all-groups                     # Install dependencies (dev group includes pre-commit)
uv run pre-commit install                # Install git hooks (once per clone)
uv run pre-commit run --all-files        # Run hooks on all files
uv run pytest -v                         # Run tests (621 tests)
uv run ruff check src/ tests/            # Lint (CI parity)
uv run ruff format --check src/ tests/   # Format check (CI parity)

# CLI — OpenCode format (primary)
# Alias: `mgw` is a 1:1 shortcut for `mcp-gway` (same `cli.main`); examples use canonical.
mcp-gway add <name> --type remote --url <url> [--header "KEY=VALUE"] [--oauth-client-id ID] [--oauth-client-secret SECRET] [--oauth-scope SCOPE] [--timeout 5000] [--enabled] [--oauth-port 8989]
# Shell-history warning: no secretos reales en --header/--oauth-client-secret; preferir `refresh --auth`.
mcp-gway add <name> --type local --command "npx -y my-mcp" [--env KEY=VALUE] [--cwd /path] [--tools "*"]
# Local allow-list: `local` requiere MCP_GWAY_ALLOW_LOCAL_COMMANDS (CSV basenames); unset/blank → DEFAULT_ALLOW_LIST npx,bunx,uvx,pipx; `*` inválido → deny + warn.
# feat-006 allow-list (ADR-009 docs/architecture/adr-009-dynamic-local-commands.md,
#   src/mcp_gway/core/policy.py): MCP_GWAY_ALLOW_LOCAL_COMMANDS (unset/blank → DEFAULT_ALLOW_LIST npx,bunx,uvx,pipx);
#   CSV basenames, `*` inválido. No renombrar MCP_GWAY_ALLOW_LOCAL_COMMANDS.
# Full options: 13 flags (cli.py:45-95): --type/--url/--command/--header/--env/--cwd/--oauth-client-id/--oauth-client-secret/--oauth-scope/--timeout/--enabled/--oauth-port/--tools
# Only --type local|remote (cli.py:50). No --args, no --docs-url. Legacy http|stdio|sse|streamable-http rejected by click.
mcp-gway remove <name>
mcp-gway list
mcp-gway inspect <name>
mcp-gway refresh [<name>] [--auth] [--oauth-port <port>]
mcp-gway serve [--transport stdio|http|sse] [--host 127.0.0.1] [--port 8080] [--log-level LEVEL] [--registry-dir PATH]  # default --transport stdio; --host/--port only with http|sse (con stdio → exit 2); 0.0.0.0 requiere MCP_GWAY_ALLOW_REMOTE=1
# mcp-gway mcp [--log-level LEVEL] [--registry-dir PATH]  # DEPRECATED hidden alias: avisa '[mcp] deprecated, use serve --transport stdio' y delega a _serve_stdio(); stdout puro NDJSON (usable como OpenCode type: local con command: [mcp-gway, serve, --transport, stdio])
mcp-gway --version | -v  # print package version
```

> **Local-first warning:** `serve` bindea `127.0.0.1` por defecto. `--host 0.0.0.0` sin `MCP_GWAY_ALLOW_REMOTE=1` → `exit 2` + `Error: binding to non-loopback ...`. Con `MCP_GWAY_ALLOW_REMOTE=1` → `WARNING: server exposed on non-loopback` en log; `X-Warning: exposed` solo en `GET /metrics` → `403` cuando se expone sin opt-in. No exponer `0.0.0.0` sin firewall/auth delante.

## Code Conventions

- Type hints on all public functions
- `from __future__ import annotations` in all modules
- Docstrings on classes and public methods
- ruff for linting and formatting
- No comments unless explicitly requested

## Testing

- Tests in `tests/` mirror `src/mcp_gway/` structure
- Use `tmp_path` fixture for file system tests
- Use `monkeypatch` for mocking
- Async tests with `@pytest.mark.asyncio`
- Mock MCP clients for unit tests

## Deployment

- **Release**: tag-only `.github/workflows/release.yml` — `git tag vX.Y.Z && git push --follow-tags` is the single release decision. Pipeline: tag==version gate → `bump-version --check` → full suite (ruff + pytest) → `uv build` → PyPI publish (OIDC, `pypi` environment) → GitHub Release with CHANGELOG notes + `dist/*` artifacts. No `workflow_run` (it double-published every release), no semantic-release.
- **Version**: `4.3.0` owned by `scripts/bump-version.mjs` (`pyproject.toml:project.version` is source of truth, `package.json` in lockstep, `--write` propagates to all sync surfaces, `--check` gates CI). CHANGELOG.md is hand-written — the workflow reads it, never writes it.
- **Build**: `uv_build` backend — sin Node en CI (`ruff` único linter)

## Key Patterns

### Endpoints vivos + Retiro dashboard/catalog

- **Vivos (v2.4.0; rutas `/mcp` por transporte, enmienda 2026-09-22):** probes `/health`, `/ready`, `/live`, `/metrics` siempre presentes; `/mcp` según `Gateway(registry, transport=...)` (`gateway.py:320-340`, `mcp_routes` condicional): **http** → `POST /mcp` (JSON-RPC) con `GET /mcp` → 405 `Allow: POST` = 6 entradas, `/mcp/messages` no existe (404); **sse** → `GET /mcp` (SSE) con `POST /mcp` → 405 `Allow: GET` + `POST /mcp/messages` alias POST al mismo handler `_mcp_post`, no endpoint independiente = 7 entradas. Sin fallback cruzado; `app.state.transport` expuesto. **+ 24 rutas admin** (`/` índice, `/admin` alias, `/admin/servers[/{name}]`, `/admin/tools`, `/admin/observability`, `/admin/policy`, `/admin/partials/*`) en ambos transports → 30 entradas (http) / 31 (sse); admin es loopback-only + CSRF por proceso, CSP único `CSP` en `gateway.py`. Gestión CLI + dashboard admin.
- **Retirados (no servir):** dashboard (`/dashboard`, `/api/servers`, `/static`, `/` alias) y catalog (`/api/catalog`, `/dashboard/catalog`, Bifrost fetch, `~/.config/mcp-gway/catalog.json` — borrar caché vieja manualmente).

### Registry (.pyi + .json) — Única fuente

- `.pyi` = signatures only; `servers/*.json` = OpenCode config (type/url/command etc). Legacy `#` comments only for fallback migration.
- Used by Code Mode para descubrir tools.
- Escrituras atómicas (`*.json` + `*.pyi` juntos), last-write-wins para concurrencia entre escrituras CLI.

### Local-First Security

- `serve --host 127.0.0.1` default. Desvío requiere `MCP_GWAY_ALLOW_REMOTE=1`; si no → `sys.exit(2)`.
- `remote --url` con SSRF-guard (`models.py:115-163`): hosts privados/loopback/link-local rechazados; ejemplo vivo `https://api.example.com/mcp`.
- Admin dashboard (`/`, `/admin*`): `_gate` en `admin/routes.py` — 403 si `app.state.serve_host` no es loopback (aunque el bind sea `0.0.0.0`), CSRF obligatorio en toda mutación (header `X-CSRF-Token` o campo `_csrf`, token por proceso `app.state.csrf_token`), valores de headers/OAuth enmascarados en la vista detalle, OAuth nunca corre inline (task en background con paridad `refresh --auth`), CSP único relajado (constante `CSP` en `gateway.py`).
- Si `host not in (127.0.0.1, ::1, localhost)` → log `warning` + banner consola; `X-Warning: exposed` solo en `GET /metrics` → `403` (observability/health.py:127-139).
- feat-006 allow-list (`src/mcp_gway/core/policy.py`, ADR-009):
  - Allow-list: `MCP_GWAY_ALLOW_LOCAL_COMMANDS` CSV basenames; unset/blank → `DEFAULT_ALLOW_LIST {"npx","bunx","uvx","pipx"}` (policy.py:23, docstring "Replaces the old default-deny"); valor explícito sobresuelve.
  - CSV basenames case-insensitive, `*`/paths inválidos → deny + warn.
  - Nota CISO opt-in: `bunx` está en `DEFAULT_ALLOW_LIST` (runner shim); ampliar el allow-list exige pin + owner + regate 90d; `bun` runtime fuera; denylist EXACT PATH,PATHEXT,SYSTEMROOT,COMSPEC,LD_PRELOAD,LD_LIBRARY_PATH,PYTHONPATH,PYTHONHOME,NODE_OPTIONS,NODE_PATH,NODE_EXTRA_CA_CERTS,NODE_TLS_REJECT_UNAUTHORIZED + PREFIXES DYLD_,NPM_CONFIG_,BUN_,UV_ + PATH controlado (`NODE_ENV` permitido, no denylisted); prohibido `*`, paths o shell.
  - No renombrar `MCP_GWAY_ALLOW_LOCAL_COMMANDS`.

### OAuth Flow

1. Discover Protected Resource Metadata (RFC 8707)
2. Discover OAuth metadata from authorization server
3. Dynamic client registration (RFC 7591)
4. PKCE authorization code flow
5. Token storage in `~/.config/mcp-gway/tokens/` (`0o600` via `_secure_atomic_write`, ver `oauth.py:run_oauth_flow`; preferir `refresh --auth`, manual solo con `chmod 600`)

### SSE Transport

- Solo con `serve --transport sse` (`transport="sse"`): `GET /mcp` → SSE stream with `endpoint` event (bajo `http`, `GET /mcp` → 405 `Allow: POST`)
- `POST /mcp/messages?session_id=...` → JSON-RPC messages (alias de `_mcp_post`; bajo `transport="http"` la ruta no existe → 404; sin fallback cruzado)
- Session management via asyncio.Queue
