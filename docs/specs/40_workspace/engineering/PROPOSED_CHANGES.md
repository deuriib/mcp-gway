# Proposed Changes: Engineering Specialist (Universal Casing & PascalCase)

**Spec Reference:** SPEC-CASING-001 (docs/specs/20_backlog/SPEC-CASING-001.md)  
**Agent:** vasquez (CTO / Engineering Specialist)  
**Date:** 2026-09-20  
**Execution_Mode:** multi-subagents (inherited from SPEC-CASING-001, frozen at frame-intent)  
**Domains-Touched:** [engineering, automation]  

---

## 1. Summary

Implement universal casing ingestion, auto-migration on refresh, and canonical PascalCase exposure across MCP Gateway:
1. Upgrade `to_pascal_case_identifier` in `code_mode.py` to handle all casing variants (`camelCase` boundary transitions, `snake_case`, `kebab-case`, `ALL_CAPS` / acronyms like `GITHUB` and `WEATHER_SERVICE`, delimiters, and leading digits).
2. Wire `_resolve_saved_name` across `cli.py` (`remove`, `inspect`, `update`, `refresh`) with dual matching (exact match, canonical PascalCase match, casefold match) to eliminate case-mismatch errors.
3. Leverage the upgraded normalizer in `cli.py:refresh` (`_canonicalize_saved_name`) to auto-rename existing legacy servers, configurations, and token stems to canonical PascalCase safely without data loss on collisions.
4. Expand test coverage in `tests/test_pascalcase_storage.py` and verify zero regressions.

---

## 2. Changes

| Target | Change Type | Description |
|--------|-------------|-------------|
| `src/mcp_gway/code_mode.py` | file-modify | Upgrade `to_pascal_case_identifier` with camelCase splitting regex (`[a-z][A-Z]`, `[A-Z]+[A-Z][a-z]`), delimiter splitting, and word capitalization (`w.capitalize()` / `w[:1].upper() + w[1:].lower()`) |
| `src/mcp_gway/cli.py` | file-modify | (1) Enhance `_resolve_saved_name` to check exact, canonical PascalCase, and casefold matches; (2) apply `_resolve_saved_name` in `remove`, `inspect`, and `update` commands |
| `tests/test_pascalcase_storage.py` | file-modify | Add test cases for all casing variants (`GITHUB`, `WEATHER_SERVICE`, `myServer`, `my-server`, `123server`), CLI case-insensitive commands (`remove`, `inspect`, `update`), and refresh migration |

---

## 3. Rationale

- **Single Source of Truth**: `to_pascal_case_identifier` in `code_mode.py` remains the single canonical normalizer imported by `cli.py` and used by Starlark sandbox injection.
- **Ergonomics Without Breaking Changes**: Normalizing on `add` and resolving case-insensitively on `remove`/`inspect`/`update`/`refresh` gives developers complete freedom in casing without altering tool semantics or storage integrity.
- **Safe Auto-Migration**: `refresh` uses existing `Registry.rename` with atomic write-then-unlink and collision detection (`FileExistsError` warns and preserves original), ensuring legacy servers migrate smoothly.
- **Strict Separation of Concerns**: Ingestion handles normalization; `models.py` continues enforcing identifier validity (`^[A-Za-z_][A-Za-z0-9_]{0,63}$`) without schema churn.

---

## 4. Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Keep ALL_CAPS words intact (e.g. `GITHUB` → `GITHUB`) | Inconsistent in Starlark and Code Mode where structs are expected in idiomatic PascalCase (`Github.tool()` vs `Filesystem.tool()`). |
| Case-insensitivity only in `refresh` | Leaves `mcp-gway remove my_server` or `mcp-gway inspect my-server` failing with `Server not found` after being saved as `MyServer`. |
| Relax `_validate_name_value` to allow hyphens | Breaks Python/Starlark identifier syntax where hyphens are syntax errors (`my-server.tool()` is evaluated as subtraction). |

---

## 5. Risk Assessment & Blast Radius

- **Systems Blast Radius:** Low.
  - Storage files are named `<PascalCase>.json` and `<PascalCase>.pyi`.
  - Atomicity guaranteed via `secure_atomic_write_text` in `Registry.rename`.
  - Collision safety: if `my_server` and `MyServer` both exist on disk, `refresh` warns and does not overwrite.
- **Team & Operator Blast Radius:** Minimal / positive.
  - Operators can use any casing in terminal commands without remembering exact capitalization.
- **Customers / Users:** None (local-first CLI tool for developer agent workflows).
- **Regulators / Compliance:** Zero impact. No PII involved; tokens renamed by file stem only, token contents never parsed or logged.
- **Revenue:** Zero impact.
- **Rollback Plan:** Fast and reversible (`git revert`). Pre-existing canonical files remain valid; renamed files remain valid.

---

## 6. Approvers

- [ ] Owning domain owner: vasquez (CTO / engineering)
- [ ] Automation owner: CI parity verification (`pytest`, `ruff`)

---

## 7. C2 Challenge Hook (REQ-002)

- **Trigger Checklist**:
  - Auth/Data/API/PII surface: No new API endpoints, token contents untouched.
  - Multi-domain scope: Engineering + Automation (within standard tooling scope).
  - Blast radius: Internal local-first developer environment.
- **Status**: No high-risk trigger tripped; ready for domain owner pre-implementation sign-off.
