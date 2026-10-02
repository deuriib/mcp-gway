---
name: mcp-gway
description: Manage MCP servers with the mcp-gway CLI (v3.1.0) — index over cli/mcp/core skills. Use when operating the gateway; pick the focused skill below.
---

# mcp-gway — index (v3.1.0)

This skill is an index. The focused skills carry the detail — start there:

- **CLI + tool executions** → `mcp-gway-cli` (`skills/cli/SKILL.md`): `add/remove/update/list/inspect/refresh/local-unrestricted` plus `tools list|read|docs|exec` (Code Mode in the terminal, same `CodeMode` class as the gateway, policy-gated).
- **MCP + serve** → `mcp-gway-mcp` (`skills/mcp/SKILL.md`): `serve --transport stdio|http|sse`, the 4 meta-tool protocol, admin dashboard parity, loopback + CSRF + CSP.
- **Internals** → `mcp-gway-core` (`skills/core/SKILL.md`): registry `.pyi/.json`, `core/policy.py` gates (allow-list + break-glass 72h, do not rename env vars), sandbox Starlark, transports, OAuth, observability.

## Quick commands

```bash
mcp-gway add youtube --type remote --url https://api.example.com/mcp
mcp-gway tools list
mcp-gway tools exec --code 'result = Demo.ping()'
mcp-gway serve --transport stdio
```

## Guards (all three skills)

- `--type` only `local|remote`. No `--args`, no `--docs-url`.
- `local` obeys `MCP_GWAY_ALLOW_LOCAL_COMMANDS` (+ break-glass 72h); `tools exec` never bypasses `policy.py`.
- `serve` binds `127.0.0.1`; non-loopback needs `MCP_GWAY_ALLOW_REMOTE=1`.
- Never put real tokens in `--header` / `--oauth-client-secret`; prefer `refresh <name> --auth`.
