# API Contracts: CLI Alias mgw + Antigravity Plugin + Universal Casing (v3)

**Owner:** vasquez (CTO)
**Version:** v3
**Last Updated:** 2026-09-22
**Spec:** SPEC-MGW-001, SPEC-ANTIGRAVITY-001, SPEC-CASING-001

## CLI Contract (packaging-only; no HTTP change)

- `mcp-gway <cmd> [flags]` ≡ `mgw <cmd> [flags]` for all `<cmd>` in `add/remove/list/inspect/refresh/serve/local-unrestricted` (+ hidden `mcp` alias path)
- `--help` output identical modulo prog name; exit 0
- `--version` identical; matches `pyproject.toml:project.version`
- Unknown flag / bad host behavior identical (`serve --host 0.0.0.0` without `MCP_GWAY_ALLOW_REMOTE=1` → `exit 2` under both names)
- No new flags, no changed defaults, no new env vars in this SPEC

## HTTP/SSE Contract (amended 2026-09-22 — transport separation; supersedes the previous "unchanged / no shape change / untouched" wording)

- `GET /health`, `/ready`, `/live`, `/metrics` — unchanged, present in both transports
- `/mcp` routes are per `Gateway(registry, transport=...)` — exactly one route set per process, no cross-transport fallback:
  - `transport="http"` (default): `POST /mcp` (JSON-RPC) + `GET /mcp` → `405 Allow: POST`; `/mcp/messages` does not exist (404) — 6 routes
  - `transport="sse"`: `GET /mcp` (SSE stream) + `POST /mcp` → `405 Allow: GET` + `POST /mcp/messages?session_id=...` alias of `_mcp_post` — 7 routes
- `app.state.transport` exposes the selected transport
- Admin dashboard (added v3.1.0 Unreleased): 7 page routes (`GET /`, `/admin`, `/admin/servers`, `/admin/servers/{name}`, `/admin/tools`, `/admin/observability`, `/admin/policy`) + 17 `/admin/partials/*` htmx endpoints (24 `Route` objects, mounted on both transports) — loopback-only (`403` when `app.state.serve_host` is not loopback) and CSRF-protected (`app.state.csrf_token`, header `X-CSRF-Token` or field `_csrf`) on every mutation; legacy `/dashboard`, `/api/*`, `/static` remain 404

## Sign-off

- Engineering: vasquez approves packaging diff (`pyproject.toml` + docs + tests)
- Security: barrera path-cite conditional — full `review-security` only if diff introduces new boundary/payload (not expected)

## Plugin Contract (v2 — SPEC-ANTIGRAVITY-001; no HTTP change)

- Bundle: `plugins/antigravity/{plugin.json, mcp_config.json, hooks.json,
  skills/mcp-gway/SKILL.md, rules/<rule>.md, INSTALL.md}` — additive only
- Manifest: `{"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
  "name": "mcp-gateway", "description": "...", "author": {...}, "repository": "...",
  "keywords": [...], "license": "MIT"}`
- MCP entry: `{"mcpServers": {"gateway": {"serverUrl": "http://127.0.0.1:8080/mcp"}}}`;
  `headers.Authorization` manual user-side edit only, never committed
- Hook I/O: stdin JSON (`invocationNum`, `transcriptPath`, common fields) → stdout
  `{injectSteps: [{ephemeralMessage: "<!-- MCP-GWAY v3.2.0 -->\n<card>"}]}` or
  `{injectSteps: []}` when MARKER present; handler `{type: "command", timeout ≤ 30}`
  invoked as `node ./plugins/antigravity/scripts/reinject.mjs` (Node ESM; no shell wrapper)
- Marker/card: `MCP-GWAY v3.2.0` verbatim; substance ≡ OpenCode MCP_RULES
  (`plugins/opencode/mcp-gateway.ts:5-33`)
- Env names: `MCP_GWAY_URL` / `MCP_GWAY_TOKEN` reused by default (no rename)

## Pi Agent Contract (v3.2.0 — extension + declarative MCP)

- Package: `package.json` declares `pi.{extensions,skills,prompts}` so the repo is
  loadable as a Pi package (`pi install ./mcp-gway`, or `pi -e ./` for one run).
- Card source: `.pi/extensions/mcp-gateway.ts` reads `rules/mcp-gway.md` at runtime —
  the single source shared with the Antigravity plugin, so harnesses cannot drift.
- Injection point: `before_agent_start` → `systemPromptOptions.sections["mcp-gateway"]`,
  deduped by MARKER or heading. Pi re-enters the agent loop after compaction
  (threshold/overflow/retry), so re-applying per run is what makes compression
  survival structural rather than a post-hoc repair.
- MCP registration is **declarative** via repo-root `.mcp.json`, NOT runtime
  `registerMcpServer()` from pi-mcp-adapter: that API forces `directTools: false`
  (proxy-only) and throws on a duplicate name, which would both downgrade and
  break a pre-existing `gateway` registration.
- Security: the extension reads one local file, opens no socket, spawns nothing, and
  swallows its own failures so it can never abort a turn. No secrets in `.mcp.json`;
  bearer auth uses the adapter's env-bound `bearerTokenEnv` so tokens stay in the env.

## Sign-off (v2 delta)

- Engineering: vasquez approves bundle diff (`plugins/antigravity/**` + tests + docs)
- Security: barrera path-cite conditional — full `review-security` STRIDE only if the
  proposal introduces a new trust boundary / exfiltration surface (hook shell commands
  get an explicit risk-lens confirm; not expected to escalate)

## Universal Casing & PascalCase Contract (v3 delta — SPEC-CASING-001)

- **Normalizer**: `to_pascal_case_identifier(name: str) -> str` transforms any string (`snake_case`, `kebab-case`, `camelCase`, `ALL_CAPS`, `mixed`) into a valid PascalCase identifier.
- **CLI `add`**: `mcp-gway add <name>` automatically canonicalizes `<name>` via `to_pascal_case_identifier` prior to registration. Saved config and stub files are strictly named `<CanonicalPascalCase>.json` and `<CanonicalPascalCase>.pyi`.
- **CLI Resolution**: `mcp-gway remove <name>`, `inspect <name>`, `update <name>`, and `refresh <name>` resolve `<name>` case-insensitively against active servers.
- **CLI `refresh` Migration**: `mcp-gway refresh` automatically detects any saved server whose stem differs from its canonical PascalCase representation and migrates it atomically (`.json`, `.pyi`, internal `config.name`, and token files).
- **Code Mode / List Exposure**: Server identifiers are exposed and bound exclusively in canonical PascalCase.

## Sign-off (v3 delta)

- Engineering: vasquez approves normalizer, CLI resolution, and refresh migration logic (`src/mcp_gway/code_mode.py`, `src/mcp_gway/cli.py`, `src/mcp_gway/registry.py`, `src/mcp_gway/models.py`).
- Automation: CI verification green across full suite.
