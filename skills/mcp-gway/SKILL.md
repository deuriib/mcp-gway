---
name: mcp-gway
description: Route to the right mcp-gway skill (v4.2.0) — mcp-gway-cli for terminal mgmt, mcp-gway-mcp for serve/protocol, mcp-gway-core for internals. Use when operating the gateway or wiring an agent to it; start here, then read the focused skill.
---

# mcp-gway — index (v4.2.0)

This skill routes. The focused skills carry the detail — read the one that matches your task:

| Your task | Read | It covers |
|-----------|------|-----------|
| Add/remove/refresh servers, run tool calls from the terminal or CI | `mcp-gway-cli` (`skills/mcp-gway-cli/SKILL.md`) | `add/remove/update/list/inspect/refresh/serve/--version` + `tools list\|read\|docs\|exec`, every flag, per-command examples |
| Start the gateway, wire an agent, run the 4-step discovery protocol, open the dashboard | `mcp-gway-mcp` (`skills/mcp-gway-mcp/SKILL.md`) | `serve --transport stdio\|http\|sse`, OpenCode/Claude/Pi wiring, `listToolFiles → readToolFile → getToolDocs → executeToolCode` with examples, probes, admin pages |
| Debug execution/auth/discovery/policy, read config files or env vars | `mcp-gway-core` (`skills/mcp-gway-core/SKILL.md`) | Registry `.pyi/.json`, all six `MCP_GWAY_*` vars, allow-list + cwd/env gates, sandbox, transports, OAuth, metrics, admin backend |

## Quick commands

```bash
mcp-gway add youtube --type remote --url https://api.example.com/mcp
mcp-gway tools list
mcp-gway tools exec --code 'result = Demo.ping()'
mcp-gway serve --transport stdio
```

Default habit across all three: `refresh` a server before trusting its stub — a signature with missing params is stale cache until re-discovered.

## Guards (all three skills)

- `--type` only `local|remote`. No `--args`, no `--docs-url`.
- `local` obeys the `MCP_GWAY_ALLOW_LOCAL_COMMANDS` allow-list; `tools exec` never bypasses `policy.py`.
- `serve` binds `127.0.0.1`; non-loopback needs `MCP_GWAY_ALLOW_REMOTE=1`.
- Never put real tokens in `--header` / `--oauth-client-secret`; prefer `refresh <name> --auth`.
