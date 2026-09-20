# Architecture Review: SPEC-CASING-001

**Reviewer:** vasquez (CTO / Engineering Owner)  
**Date:** 2026-09-20  
**Verdict:** Approved  

## Contract Compliance

| Invariant | Status | Notes |
|-----------|--------|-------|
| INV-001 | Pass | Local-first default (`127.0.0.1`) untouched |
| INV-002 | Pass | `MCP_GWAY_ALLOW_*` policy variables untouched |
| INV-003 | Pass | No secrets or tokens logged or exposed |
| INV-004 | Pass | Evidence verified via automated test matrix |
| INV-005 | Pass | Test suite and linting integrity maintained |
| INV-011 | Pass | Server names stored and exposed in canonical PascalCase |
| INV-012 | Pass | CLI server lookup case-insensitive across all commands (`remove`, `inspect`, `update`, `refresh`) |
| INV-013 | Pass | Collision protection active; no overwrites on refresh |

## ADR Required?

- [x] Yes — ADR-013 created (docs/specs/12_adr/ADR-013-universal-casing-normalization.md)
- [ ] No — change is within existing contracts

## Conditions for Approval

1. Implementation files in `src/` must not introduce cyclic imports between `cli.py`, `code_mode.py`, and `registry.py`.
2. Tests must explicitly assert casing normalization for `snake_case`, `kebab-case`, `camelCase`, `ALL_CAPS`, `UPPER_SNAKE`, and digit prefixes.
3. Refresh migration must handle both server config files and associated OAuth token stems without reading token contents.

## Sign-off

- [x] engineering owner (vasquez / CTO) — Approved for implementation in `execute-spec`.
