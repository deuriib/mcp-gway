# Spec: Universal Casing Ingestion, Auto-Migration on Refresh & Canonical PascalCase Exposure

**ID:** SPEC-CASING-001  
**Owner:** vasquez (CTO)  
**Domains-Touched:** [engineering, automation]  
**Brief Reference:** BRIEF-CASING-001 (docs/briefs/BRIEF-casing-normalization.md)  
**Status:** approved  
**Priority:** P1  
**Execution_Mode:** multi-subagents (inherited from BRIEF-CASING-001, frozen at frame-intent)  

---

## 1. Context

Users provide MCP server names with varying conventions (snake_case, kebab-case, camelCase, ALL_CAPS, or lowercase).
While `SPEC-PASCALCASE-STORAGE-001` introduced basic PascalCase storage on `add` and rename on `refresh`, the word-splitting logic didn't normalize all-caps words (leaving `GITHUB` as `GITHUB` and `WEATHER_SERVICE` as `WEATHERSERVICE`), camelCase boundary transitions weren't cleanly parsed, and management commands (`remove`, `inspect`, `update`) required exact-casing matches, leading to 404 errors.

This specification unifies the PascalCase engine to support all casing variations, ensures `cli refresh` auto-migrates existing legacy servers to canonical PascalCase on disk and token storage, and enables case-insensitive server lookup across all CLI management commands.

---

## 2. Requirements

- **REQ-F-001**: `to_pascal_case_identifier` normalizes any casing variation into valid PascalCase:
  - Splits on non-alphanumeric delimiters (`-`, `_`, spaces, etc.).
  - Splits on camelCase boundaries (e.g., `myServer` → `MyServer`, `weatherServiceApi` → `WeatherServiceApi`).
  - Converts all-caps tokens to capitalized words (e.g., `GITHUB` → `Github`, `WEATHER_SERVICE` → `WeatherService`, `AWS_S3` → `AwsS3`).
  - Sanitizes leading digits with a leading underscore (e.g., `123server` → `_123Server`).
- **REQ-F-002**: `cli add` canonicalizes `name` via the upgraded normalizer before validation, collision checks, and storage; storage files (`servers/<Name>.json` and `servers/<Name>.pyi`) and `MCPServerConfig.name` are strictly PascalCase.
- **REQ-F-003**: `cli refresh` (invoked globally or with a specific server name) auto-migrates existing servers whose stem differs from its canonical PascalCase representation:
  - Atomically renames `<old>.json` and `<old>.pyi` to `<canonical>.json` and `<canonical>.pyi` via `Registry.rename`.
  - Updates `config.name` inside the JSON configuration.
  - Renames associated token files (`<old>.json` and `<old>_client.json` to `<canonical>.json` and `<canonical>_client.json`).
  - Guards against collisions (`FileExistsError`): warns and preserves original without data loss.
- **REQ-F-004**: CLI commands `remove`, `inspect`, `update`, and `refresh` resolve server names case-insensitively (exact match first, then casefold/canonical match against registered servers), eliminating `Server not found` errors due to casing mismatch.
- **REQ-F-005**: Code Mode and `mcp-gway list` expose and interact with canonical PascalCase names.
- **REQ-NF-001**: CI parity: 100% passing tests via `uv run pytest` and clean linting via `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`.
- **REQ-NF-002**: Local-first & Security: Zero secret exposure in logs, atomic writes via `secure_atomic_write_text`, collision protection.

---

## 3. Acceptance Criteria

- [ ] **AC-001**: `test_to_pascal_case_variants` verifies `snake_case`, `kebab-case`, `camelCase`, `ALL_CAPS`, `UPPER_SNAKE`, and mixed strings convert to expected PascalCase (`tests/test_pascalcase_storage.py`).
- [ ] **AC-002**: `mcp-gway add GITHUB --type local ...` stores `Github.json` and `Github.pyi` with `config.name == "Github"`.
- [ ] **AC-003**: `mcp-gway refresh` renames legacy non-canonical servers (e.g. `weather_service` → `WeatherService`) and associated tokens atomically.
- [ ] **AC-004**: `mcp-gway remove myserver` successfully removes `MyServer` without error.
- [ ] **AC-005**: `mcp-gway inspect myserver` and `mcp-gway update myserver` find and operate on `MyServer`.
- [ ] **AC-006**: Full test suite passes without regressions (`pytest`), ruff formatting and check clean.

---

## 4. Contracts & Interfaces

### Function: `to_pascal_case_identifier(name: str) -> str`
- **Location**: `src/mcp_gway/code_mode.py`
- **Input**: Any ASCII string.
- **Output**: Valid Python/Starlark identifier in PascalCase.

### CLI Name Resolution Helper: `_resolve_saved_name(registry: Registry, name: str) -> str`
- **Location**: `src/mcp_gway/cli.py`
- **Behavior**:
  1. Exact match in `registry.list()`.
  2. Canonical PascalCase match (`to_pascal_case_identifier(name)` in `registry.list()`).
  3. Casefold / case-insensitive match against `registry.list()`.
  4. If not found, returns `name` (caller handles `FileNotFoundError` as appropriate).

### Storage Contract:
- `servers/<ServerName>.json` (OpenCode format) + `servers/<ServerName>.pyi` (stubs) where `<ServerName>` is strictly `to_pascal_case_identifier(stem)`.

---

## 5. Out of Scope

- Upstream MCP tool name casing (tool names like `execute_query` remain unaltered).
- Web UI / Dashboard.
- Casing of server parameters or environment variable keys.

---

## 6. Dependencies

- `src/mcp_gway/code_mode.py` (normalizer function)
- `src/mcp_gway/registry.py` (`Registry.rename` atomic helper)
- `src/mcp_gway/cli.py` (commands: `add`, `remove`, `inspect`, `update`, `refresh`)
- `src/mcp_gway/models.py` (`_validate_name_value`, `MCPServerConfig`)

---

## 7. Traceability

| Requirement | Acceptance Criterion | Proposed Change | Evidence |
|-------------|---------------------|-----------------|----------|
| REQ-F-001 | AC-001 | `src/mcp_gway/code_mode.py` | `tests/test_pascalcase_storage.py::test_to_pascal_case_variants` |
| REQ-F-002 | AC-002 | `src/mcp_gway/cli.py`, `models.py` | `tests/test_pascalcase_storage.py::test_add_canonicalizes_*` |
| REQ-F-003 | AC-003 | `src/mcp_gway/cli.py` | `tests/test_pascalcase_storage.py::test_refresh_renames_*` |
| REQ-F-004 | AC-004, AC-005 | `src/mcp_gway/cli.py` | `tests/test_pascalcase_storage.py::test_cli_case_insensitive_*` |
| REQ-F-005 | AC-002, AC-003 | `src/mcp_gway/cli.py` | `tests/test_cli.py` |
| REQ-NF-001 | AC-006 | Repository-wide | `uv run pytest` + `uv run ruff check` |
| REQ-NF-002 | AC-002, AC-003 | `src/mcp_gway/registry.py` | `tests/test_pascalcase_storage.py::test_registry_rename_*` |
