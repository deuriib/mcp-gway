# SHIP — rename-execute-tool

## Release notes (user-facing)

The MCP Gateway Code Mode execution tool has been renamed from `executeToolCode` to `executeTool` (and `gateway_executeTool`). This removes semantic ambiguity by clarifying that the tool's purpose is executing MCP tools through Starlark rather than general-purpose code execution. All rules, stubs, and plugins have been updated to reflect the canonical name.

## Version / tag

v5.0.0 (Issue #30 / branch 30-refactor-gateway-rename-executetoolcode-to-executetool-for-clarity)

## Changelog

- refactor(gateway): rename executeToolCode to executeTool in tool definitions and dispatch routing (fixes #30)
- refactor(code-mode): update CodeMode execution method to execute_tool with compatibility alias
- refactor(registry): update virtual stub usage comments to reflect executeTool
- refactor(cli): update mcp-gway tools exec command and docstring to reflect executeTool
- refactor(plugins): update antigravity and opencode rule cards to gateway_executeTool
- refactor(skills): update mcp-gway-cli and mcp-gway-mcp skills to executeTool
- test(gateway): update test suite assertions across gateway, admin dashboard, and CLI to executeTool
- docs(code-mode): update Code Mode architecture, protocol, and usage guides to executeTool

## References

- FRAME: `00-frame.md`
- PROPOSE: `01-propose.md`
- BUILD: `02-build.md`
- VERIFY: `03-verify.md` (verdict: PASS)

## Follow-ups carried from VERIFY

- None.

## Assigned team

- Domain: Atlas (Engineering & Product) — deliver rename and user-facing documentation.
- Process steward: Atlas (Process Steward) — confirm SHIP protocol and artifact bijection.

## Gates

- Domain gate: N/A — passed at VERIFY
- Process gate: Atlas (Process Steward) — PASS
