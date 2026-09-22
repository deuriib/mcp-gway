# Handoff: Engineering Specialist (transport separation)

**Spec Reference:** SPEC-TRANSPORT-SEPARATION-001
**Agent:** engineering lane (orchestrator-synthesized)
**Date:** 2026-09-22
**Status:** complete
**Domains-Touched:** [engineering, security]

**Packet:** `SPEC:docs/specs/50_archive/SPEC-TRANSPORT-SEPARATION-001/{PROPOSED_CHANGES,IMPLEMENTATION_PLAN,TEST_MATRIX}.md#REQ-TRANSPORT-001..008 / HARD:subagents + sequential-degradation + frozen-src-contract / GATE:OPEN (6 pass + 1 conditional→resolved, C3 PASS ×3) / DOMAINS:[engineering, security]`

## Deliverables

| Artifact | Location / Evidence | Status |
|----------|---------------------|--------|
| Implementation | `src/mcp_gway/gateway.py` (transport param, exclusive `mcp_routes`, 405+`Allow` handlers, `app.state.transport`), `src/mcp_gway/cli.py` (`_serve_http(..., transport)`, banner, help) — commit `14ff7a1` (`feat!`, BREAKING CHANGE footer → 3.0.0) | done |
| Tests / Evidence | `tests/test_transport_separation.py` (9 contract tests, REQ-001..004+008) + migrated suites (`test_gateway`, `test_edgecases_gateway`, `test_gateway_sse_limits`, `test_obsfeat007`, `test_p0_round2_hardening`, `test_serve_unified`) — commit `35ba3fb`; `uv run pytest -q` → **570 passed, 0 failed**; `ruff check` + `ruff format --check` clean | done |
| Docs | `AGENTS.md`, `README.md`, `docs/specs/10_design/API_CONTRACTS.md`, `docs/specs/10_design/ARCHITECTURE.md` (per-transport contract, ADR-010 AC-05 inline amendment) — commit `1fbe76f`; `CHANGELOG.md` Unreleased breaking entry | done |
| Domain artifact | Quality gate: `docs/specs/50_archive/SPEC-TRANSPORT-SEPARATION-001/quality-gate/GATE_REPORT.md` (OPEN) + 7 reviewer artifacts — commits `9dd938c`, `287efc9` | done |
| Packet | `docs/specs/50_archive/SPEC-TRANSPORT-SEPARATION-001/` (PROPOSED_CHANGES, IMPLEMENTATION_PLAN gates checked, TEST_MATRIX REQ→test trace) — commit `0fbfbeb` | done |

## Definition of Done Checklist

- [x] Acceptance criteria satisfied (REQ-TRANSPORT-001..008 all Covered — TEST_MATRIX + `qa-review.md` REQ table)
- [x] Tests/evidence linked per REQ-ID (C4: all 9 contract-test links resolve via `grep def <test>` + `pytest tests/test_transport_separation.py` → 9 passed; REQ-005/006/007 links resolve in `test_serve_unified.py`, `test_wave2_api.py`, `test_edgecases_gateway.py`, `test_stdio.py`; zero dead links, attestation-alone not used)
- [x] Load evidence present (`skill(frame-ship:quality-gate)` + `skill(frame-ship:verify-handoff)` loaded; mode `subagents`; 1 subagent per reviewer; packet intact above)
- [x] Domain checks passing (Common + engineering appendix: lint zero warnings `[]`, type checks N/A — no mypy/pyright in repo CI (ruff only, per AGENTS.md), coverage: both 405 handlers + both route lists hit ≥1 test (QA M-1..M-3 logged non-blocking), no TODO/FIXME in touched files — scan exit 1 = no matches)
- [x] Security checks passing (security-reviewer APPROVE, 0 Critical/High/Medium; secrets scan across 6 commits = 0 hits; boundaries validated — `ValueError` fail-fast, route sets exclusive, middleware covers new routes)
- [x] Documentation / filing / comms updated (4 contract docs + CHANGELOG breaking entry + Antigravity INSTALL mitigation)

## C4 — REQ→evidence presence check (security-owned)

Zero C4 FAILs: every REQ-001..008 row in `TEST_MATRIX.md` carries a resolvable test link (verified this session, output in DoD above). No attestation-only REQ. Residual-risk on non-FAIL items: QA gaps M-1 (REQ-003 GET leg introspection-only in contract file, behavioral coverage exists untagged in `test_obsfeat007.py:265`), M-2 (`test_p0_round2_hardening.py:104` lacks `wait_for` — hang-on-regression risk), M-3 (REQ-005 banner unasserted) — all recorded in `qa-review.md` and accepted in `GATE_REPORT.md` residual-risk; owner: engineering.

## Blockers / Open Questions

None blocking. Open (recorded, non-blocking): (1) decide before release that `feat!` drives 3.0.0 — semantic-release parses the footer (`14ff7a1`), verify on the release PR; (2) R5 waiver expiry 2026-12-21: author a real ADR-010 or drop the dangling reference; (3) Antigravity real-client protocol unprovable from repo — INSTALL mitigation covers both branches, re-review next release.

## PII checkpoint (REQ-SEC-003/004 + REQ-P-006 co-sign)

Zero PII/secrets/tokens/credentials/sessions in handoff text, evidence links, or exports: deliverables are code/tests/contract-prose only; evidence = file:line + command output (allowlisted). Ley 172-13 minimization: no personal data processed by this change (route gating only). Co-sign: security-reviewer ✅ + orchestrator ✅. Masking reminder: apply to any future export of this handoff.

## Next Agent

**frame-ship:ship-release** — verified work, gate OPEN. Needs: release notes emphasizing BREAKING (SSE-only clients → `--transport sse`), confirm semantic-release emits **3.0.0** from the `feat!` + BREAKING CHANGE footer (branch `feat/separate-mcp-transport`, local only — push + PR to trigger Tests → Release), rollback = `git revert` of the 7 commits (no persisted state touched).
