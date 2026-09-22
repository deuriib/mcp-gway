# Product Brief: Universal Casing Ingestion, Auto-Migration on Refresh & Canonical PascalCase Exposure

**ID:** BRIEF-CASING-001
**Initiator:** orchestrator
**Date:** 2026-09-20
**Status:** approved
**Execution_Mode:** multi-subagents (frozen at frame-intent; trivial <15 lines goes by CEO fast-path checkpoint-only, outside methodology)
**Domains-Touched:** [engineering, automation]
**Classification:** bounded-initiative
**Framings-Considered:**
- Framing A (Smart Split & Title + Refresh Auto-Migration + CLI case-insensitive resolution): Normalizes snake_case, kebab-case, camelCase, and ALL_CAPS into canonical PascalCase on add and refresh, with case-insensitive CLI command resolution. [Recommended & Selected]
- Framing B (Preserve all-caps acronyms): Preserves uppercase strings like GITHUB or AWS_S3. [Rejected: causes jarring inconsistency in Starlark and Code Mode]
- Framing C (Transform on add only): Only converts string in `mcp-gway add`. [Rejected: leaves remove, inspect, and existing servers broken]
**Approval:** chat-yes — deuriib 2026-09-20

---

## Problem Statement

Users add MCP servers using diverse naming conventions (e.g. `github`, `WEATHER_SERVICE`, `my-server`, `myServer`).
Currently:
1. The PascalCase identifier logic does not handle all-caps words or acronyms (e.g., `GITHUB` remains `GITHUB`, `WEATHER_SERVICE` becomes `WEATHERSERVICE`) nor camelCase word boundaries.
2. Saved servers from previous versions or added prior to normalization need a clean, zero-downtime migration path to canonical PascalCase without manual deletion and re-adding.
3. Management commands (`remove`, `inspect`, `update`) require exact-casing matches, failing with `Server not found` if the user supplies a different casing than stored.

## Desired Outcome

Deliver an intuitive and consistent experience where any server name casing is accepted on `add`, automatically transformed to canonical `PascalCase` internally, persisted as such (`.json`, `.pyi`), cleanly exposed in Code Mode / Starlark, and retroactively migrated on `refresh`, with case-insensitive resolution across all CLI commands.

## Scope

### In Scope

- **Smart PascalCase Normalizer**: Refine `to_pascal_case_identifier` to split delimiters (`-`, `_`, spaces), camelCase boundaries, and capitalize words cleanly (`GITHUB` → `Github`, `WEATHER_SERVICE` → `WeatherService`, `AWS_S3` → `AwsS3`, `my-custom-mcp` → `MyCustomMcp`). [engineering]
- **Ingestion & Models**: Normalization on `cli add` aligned with `MCPServerConfig` and `_validate_name_value` to enforce PascalCase canonicity in storage. [engineering]
- **Auto-Migration on `refresh`**: Update `cli refresh` so that running `mcp-gway refresh` (or `mcp-gway refresh <name>`) auto-renames existing non-canonical servers to PascalCase (including `.json`, `.pyi`, internal `config.name`, and token files), with collision guard. [engineering]
- **Case-Insensitive Resolution**: Enable case-insensitive lookup (exact first, then casefold/canonical match) across `remove`, `inspect`, `update`, and `refresh`. [engineering]
- **Testing & Verification**: Unit and integration test coverage across all casing variations, CLI commands, and refresh auto-migration. [automation]

### Out of Scope

- Individual tool name casing (tool names such as `read_file` remain unchanged as exposed by upstream servers).
- Web UI / Dashboard (removed in v2.0.0; CLI-only headless architecture).

## Stakeholders

| Role | Agent | Involvement |
|------|-------|-------------|
| Sponsor | orchestrator | Decision authority & process enforcement |
| Owner | vasquez (CTO) | Delivery ownership (engineering domain) |
| Touched | automation | CI / CLI verification |

## Constraints

- **Budget**: Standard engineering capacity.
- **Timeline**: Single SPEC delivery cycle.
- **Security & Local-First**: No secrets logged, local-first default (`127.0.0.1`), atomic writes (`secure_atomic_write_text`), never overwrite on collision (`FileExistsError` keeps original and warns).
- **Parity**: `pytest` 100% green, `ruff check` and `ruff format` clean.

## OKRs: Universal Casing & PascalCase Normalization

**Period:** Q3 2026
**Owner:** orchestrator

### Objective 1: Complete and seamless casing ergonomics across the CLI and Code Mode

| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| KR-1.1 | Inconsistent handling for acronyms (`GITHUB` → `GITHUB`) | 100% canonical PascalCase across all tested casing styles (`snake_case`, `kebab-case`, `camelCase`, `ALL_CAPS`) | Automated unit tests (`test_to_pascal_case_variants`) |
| KR-1.2 | `remove`, `inspect`, `update` require exact case match | 100% of CLI server commands succeed with any casing | CLI integration tests |
| KR-1.3 | Legacy casing in saved servers requires manual rename | 100% auto-migration of legacy server stems and tokens to PascalCase on `refresh` | Integration tests for `refresh` |
| KR-1.4 | 0 regressions | 100% suite green | `uv run pytest` + `uv run ruff check` |
