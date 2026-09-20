# ADR-013: Universal Casing Ingestion, Refresh Auto-Migration & Canonical PascalCase Exposure

**Date:** 2026-09-20  
**Deciders:** engineering owner (vasquez / CTO), orchestrator  
**Status:** accepted  

## Context

Users add MCP servers using diverse naming conventions (e.g. `github`, `WEATHER_SERVICE`, `my-server`, `myServer`).
Prior implementations:
1. Left acronyms/all-caps words unchanged (e.g. `to_pascal_case_identifier("GITHUB")` produced `"GITHUB"` and `"WEATHER_SERVICE"` produced `"WEATHERSERVICE"`).
2. Did not cleanly handle `camelCase` boundary transitions.
3. Exposing or managing servers via `remove`, `inspect`, and `update` required exact case matches, leading to 404 errors when users typed lowercase or alternate casing.
4. Legacy servers stored with old casing required an automated, safe migration path.

## Decision

1. **Smart PascalCase Engine**: Refine `to_pascal_case_identifier` in `src/mcp_gway/code_mode.py` to be the single source of truth for identifier conversion. It splits on delimiters (`-`, `_`, whitespace), splits on `camelCase` transitions, and title-cases tokens (`GITHUB` → `Github`, `WEATHER_SERVICE` → `WeatherService`, `AWS_S3` → `AwsS3`, `my-custom-mcp` → `MyCustomMcp`).
2. **Canonical Storage**: `cli add` canonicalizes `name` before validation and storage. Server stub (`.pyi`) and configuration (`.json`) files are strictly named in canonical `PascalCase`.
3. **Case-Insensitive Resolution**: `_resolve_saved_name` is enhanced and wired into `remove`, `inspect`, `update`, and `refresh`, matching exact first, then canonical PascalCase, then casefold, ensuring user operations succeed regardless of casing.
4. **Auto-Migration on `refresh`**: `mcp-gway refresh` automatically detects saved servers whose stems are non-canonical and migrates them (`.json`, `.pyi`, internal `config.name`, and token files) to canonical PascalCase, logging collision warnings and skipping if target already exists to prevent data loss.

## Consequences

### Positive
- High developer ergonomics: zero friction when adding or managing servers with different casing conventions.
- Clean, idiomatic Starlark sandbox structs (`Github.tool()`, `Filesystem.tool()`).
- Seamless backward compatibility and automated upgrade path for existing configurations.
- Invariants INV-011, INV-012, and INV-013 upheld.

### Negative
- A server originally stored as `my_server` will migrate to `MyServer`; external tools directly inspecting the filesystem directory must look for the canonical PascalCase stem.
