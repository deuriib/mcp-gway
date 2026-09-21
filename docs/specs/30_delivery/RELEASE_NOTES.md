# Release Notes: Universal Casing Ingestion & Canonical PascalCase Exposure

**Date:** 2026-09-20  
**Release Manager:** vasquez (CTO, engineering chain owner)  
**Specs Included:** `SPEC-CASING-001` (Universal Casing Ingestion, Auto-Migration on Refresh & Canonical PascalCase Exposure)  
**Domains-Touched:** [engineering, automation]  
**Ship Type:** feature (core CLI + Code Mode normalization)  

---

## Highlights

- **Universal Casing Ingestion (`to_pascal_case_identifier`)**:
  - Developers can add servers using any naming style (`snake_case`, `kebab-case`, `camelCase`, `ALL_CAPS`, `UPPER_SNAKE`, `mixed`).
  - `to_pascal_case_identifier` intelligently splits camelCase word boundaries (`myServer` → `MyServer`), delimiters (`my-server` → `MyServer`), acronyms / uppercase words (`GITHUB` → `Github`, `WEATHER_SERVICE` → `WeatherService`, `AWS_S3` → `AwsS3`), and protects leading digits (`123server` → `_123Server`).
- **Transparent Case-Insensitive CLI Management**:
  - `mcp-gway remove <name>`, `inspect <name>`, `update <name>`, and `refresh <name>` resolve server names case-insensitively (exact match first, then canonical PascalCase, then casefold). Users never encounter `Server not found` errors due to casing discrepancies.
- **Automated Refresh Migration**:
  - Running `mcp-gway refresh` automatically detects legacy or non-canonical server stems and migrates them (`.json`, `.pyi`, internal `config.name`, and token files) to canonical PascalCase atomically, with collision safety.
- **Verification & Parity**:
  - 562/562 unit and integration tests passing (`pytest`).
  - 100% clean formatting and linting (`ruff`).
  - Unconditional OPEN verdict across all 7 Quality Gate reviews.

---

## Changes

### Features
- Upgraded `to_pascal_case_identifier` in `src/mcp_gway/code_mode.py` to handle all casing variants.
- Enhanced `_resolve_server` in `src/mcp_gway/code_mode.py` to match canonical PascalCase identifiers.
- Enhanced `_resolve_saved_name` in `src/mcp_gway/cli.py` to support canonical PascalCase matching and wired it into `remove`, `inspect`, and `update`.
- Integrated automated migration on `mcp-gway refresh` via `_canonicalize_saved_name`.

### Tests & Quality
- Added 16 dedicated unit and integration tests in `tests/test_pascalcase_storage.py`.
- Isolated test environment in `tests/test_policy_local_commands.py` to prevent user config pollution.
- All 562 tests passing cleanly in CI.

---

## Rollback / Undo

- **Commit Revert**: `git revert c728cd7 412bc6f`.
- **Filesystem**: Existing PascalCase files remain fully backwards-compatible with older gateway releases.
