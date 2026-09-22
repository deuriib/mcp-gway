# Release Notes: v3.0.0 — Transport Separation (per-transport /mcp routes)

**Date:** 2026-09-22
**Release Manager:** orchestrator / operations owner function
**Specs Included:** SPEC-TRANSPORT-SEPARATION-001
**Domains-Touched:** [engineering, security]
**Ship Type:** rollout (breaking contract change on a deployed local-first service)

---

## Highlights

- **One process, one transport — no fallback.** `Gateway(registry, transport=...)` now builds mutually exclusive `/mcp` route sets. `serve --transport http` exposes `POST /mcp` only (6 routes; `GET /mcp` → `405 Allow: POST`; `/mcp/messages` → 404). `serve --transport sse` exposes `GET /mcp` (SSE) + `POST /mcp/messages` only (7 routes; `POST /mcp` → `405 Allow: GET`). Probes (`/health`, `/ready`, `/live`, `/metrics`) remain on both; `app.state.transport` is exposed for observability.
- **Honest 405s.** Gated methods answer JSON `detail` + RFC-correct `Allow` header (through the full middleware stack: CSP, metrics, logging, correlation), so a mispaired client learns exactly which transport to use instead of guessing at a plain-text error.
- **Verified full-wave.** 7 independent gate reviewers (readability, reliability, refuter, resilience, risk, QA, security — 1 subagent each); refuter's 6/6 attacks refuted; security: 0 Critical/High/Medium; suite 570 passed / 0 failed; ruff check + format clean.

---

## Changes

### Features

- `Gateway` accepts `transport: "http" | "sse"` (default `http`), rejects unknown values with `ValueError` before side effects (SPEC-TRANSPORT-SEPARATION-001, engineering) — `src/mcp_gway/gateway.py:181`
- `serve --transport http|sse` propagates the transport to the app and banner; `--transport` help documents per-transport routes (SPEC-TRANSPORT-SEPARATION-001, engineering) — `src/mcp_gway/cli.py:514`

### Fixes

- Contract tests migrated from the dual-app assumption: JSON-RPC via `POST /mcp`, SSE/alias/limit suites on `transport="sse"`, CLI fakes take the new param (SPEC-TRANSPORT-SEPARATION-001, engineering) — `tests/test_transport_separation.py` (9/9) + 6 migrated test files

### Domain Ships

- Engineering: gate OPEN with 7 reviews + C3 waiver record PASS ×3 — `docs/specs/50_archive/SPEC-TRANSPORT-SEPARATION-001/quality-gate/GATE_REPORT.md`
- Security: STRIDE review APPROVE, secrets scan 0 hits across all commits — `docs/specs/50_archive/SPEC-TRANSPORT-SEPARATION-001/quality-gate/review-security.md`

### Breaking Changes

- **`serve --transport http` no longer serves SSE.** A client that opened `GET /mcp` (SSE) or `POST /mcp/messages` against an http-mode gateway now gets `405`/`404`. — **Migration:** run `mcp-gway serve --transport sse` for SSE-only clients; streamable-HTTP (POST) clients are unaffected. Full guide: [MIGRATION.md](../../../MIGRATION.md); Antigravity troubleshooting row added in `plugins/antigravity/INSTALL.md`.
- **`serve --transport sse` no longer serves `POST /mcp`.** HTTP-only clients get `405 Allow: GET`. — **Migration:** pair the client with the matching transport; the 405 body states the fix.

---

## Known Issues

- Antigravity plugin's exact client protocol (streamable-HTTP vs SSE-only) is unprovable from the repo — INSTALL mitigation covers both branches; re-review next release (waiver R2, owner: engineering).
- Off-matrix methods (e.g. `DELETE /mcp`) fall through to Starlette's default `405` with its own `Allow` set — unspecified by contract, cosmetic inconsistency (owner: engineering backlog).
- ADR-010 exists only as a dangling reference; AC-05 amendment recorded inline in `AGENTS.md` + `API_CONTRACTS.md` — waiver expiry 2026-12-21: author the real ADR or drop the reference (owner: engineering).
- `uv.lock` still records the previous version (line 744 `mcp-gway` `version = "2.11.3"`) after PSR writes 3.0.0 — `sync_version.py` (the `[tool.semantic_release]` `build_command`) does not own `uv.lock`, so a post-release `chore(lock)` sync commit is required (precedent `7591fff`); `uv sync` regenerates the hash locally in the interim (owner: engineering).

## Rollback / Undo

- **Code:** `git revert -m 1 <merge-sha>` of the release merge commit (branch `feat/separate-mcp-transport`, 10 commits from `531cf3c`) restores the dual-app contract — no persisted state, registry schema, env vars, or config files are touched (verified by risk review). Recovery <10 min. Merge-commit merge (not squash/rebase) keeps the gate-cited SHAs `9dd938c`, `287efc9`, `0fbfbeb` reachable.
- **PyPI:** `pip install mcp-gway==2.11.3` pins the previous behavior for consumers.
- **Release:** PSR release is atomic on `master`; a failed run leaves version at 2.11.3 (no partial bump — `version_toml`/`version_variables` write in `build_command` only).
