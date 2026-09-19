# API Contracts: CLI Alias mgw + Antigravity Plugin (v2)

**Owner:** vasquez (CTO)
**Version:** v2
**Last Updated:** 2026-09-19
**Spec:** SPEC-MGW-001, SPEC-ANTIGRAVITY-001

## CLI Contract (packaging-only; no HTTP change)

- `mcp-gway <cmd> [flags]` ≡ `mgw <cmd> [flags]` for all `<cmd>` in `add/remove/list/inspect/refresh/serve/local-unrestricted` (+ hidden `mcp` alias path)
- `--help` output identical modulo prog name; exit 0
- `--version` identical; matches `pyproject.toml:project.version`
- Unknown flag / bad host behavior identical (`serve --host 0.0.0.0` without `MCP_GWAY_ALLOW_REMOTE=1` → `exit 2` under both names)
- No new flags, no changed defaults, no new env vars in this SPEC

## HTTP/SSE Contract (unchanged, cited for non-regression)

- `GET+POST /mcp`, `GET /health`, `/ready`, `/live`, `/metrics` — no shape change
- `POST /mcp/messages?session_id=...` alias of `_mcp_post` — untouched

## Sign-off

- Engineering: vasquez approves packaging diff (`pyproject.toml` + docs + tests)
- Security: barrera path-cite conditional — full `review-security` only if diff introduces new boundary/payload (not expected)

## Plugin Contract (v2 — SPEC-ANTIGRAVITY-001; no HTTP change)

- Bundle: `plugins/antigravity/{plugin.json, mcp_config.json, hooks.json,
  skills/mcp-gway/SKILL.md, rules/<rule>.md, INSTALL.md}` — additive only
- Manifest: `{"$schema": "https://antigravity.google/schemas/v1/plugin.json",
  "name": "mcp-gateway", "description": "..."}`
- MCP entry: `{"mcpServers": {"gateway": {"serverUrl": "http://127.0.0.1:8080/mcp"}}}`;
  `headers.Authorization` manual user-side edit only, never committed
- Hook I/O: stdin JSON (`invocationNum`, `transcriptPath`, common fields) → stdout
  `{injectSteps: [{ephemeralMessage: "<!-- MCP-GWAY v2.8.0 -->\n<card>"}]}` or
  `{injectSteps: []}` when MARKER present; handler `{type: "command", timeout ≤ 30}`
- Marker/card: `MCP-GWAY v2.8.0` verbatim; substance ≡ OpenCode MCP_RULES
  (`plugins/opencode/mcp-gateway.ts:5-33`)
- Env names: `MCP_GWAY_URL` / `MCP_GWAY_TOKEN` reused by default (no rename)

## Sign-off (v2 delta)

- Engineering: vasquez approves bundle diff (`plugins/antigravity/**` + tests + docs)
- Security: barrera path-cite conditional — full `review-security` STRIDE only if the
  proposal introduces a new trust boundary / exfiltration surface (hook shell commands
  get an explicit risk-lens confirm; not expected to escalate)
