# Release Notes: Server Capitalization Normalization & Antigravity Root Layout

**Date:** 2026-09-19  
**Release Manager:** vasquez (CTO, engineering chain owner)  
**Specs Included:** `SPEC-SERVER-CAPS-001` (Server Naming Capitalization Normalization), Antigravity Plugin Root Layout  
**Domains-Touched:** [engineering, security]  
**Ship Type:** feature + harness integration (core engine + IDE plugin)  

---

## Highlights

- **PascalCase Normalization (`to_pascal_case_identifier`)**: Connected MCP servers are exposed in Code Mode with capitalized PascalCase bindings (`Server.tool_name(param=value)`), handling hyphens, underscores, dots, and digits seamlessly.
- **Dual Binding Backward Compatibility**: `StarlarkSandbox` registers both the primary PascalCase identifier (`Server`) and the lowercase alias (`server`), guaranteeing 100% backward compatibility for existing code.
- **Dynamic Refresh Auto-Capitalization**: `CodeMode.refresh()` dynamically reconciles and binds both PascalCase and lowercase aliases when servers are added or removed at runtime.
- **Antigravity Plugin Root Layout Integration**: Integrated user manual changes migrating Antigravity IDE configuration directly to repository root (`plugin.json`, `mcp_config.json`, `hooks.json`, `rules/mcp-gway.md`), with updated test suite parity.

---

## Changes

### Features
- Added `to_pascal_case_identifier` helper in `src/mcp_gway/code_mode.py`.
- Updated `CodeMode._inject_tools` and `CodeMode.refresh` for automatic dual binding and capitalized alias management.
- Updated `Registry._generate_pyi` to format stub headers as `# Usage: {cap_name}.tool_name(param=value)`.
- Updated `gateway.py` tool schema docstrings for `listToolFiles` and `executeToolCode` to use capitalized `Server.tool_name` examples.
- Migrated Antigravity harness configuration to repository root per operator changes.

### Tests & Quality
- Added unit and integration tests in `tests/test_code_mode.py` and `tests/test_registry.py`.
- Updated `tests/test_antigravity_plugin.py` to assert bundle integrity on root layout.
- 546/546 pytest tests pass cleanly; ruff check and format 100% clean.

---

## Rollback / Undo

- **Commit Revert**: `git revert ce403b0` (for Antigravity root migration) and/or `git revert f66c0ea` (for server capitalization). Zero persistent database migrations or schema breakages.
