# Architecture Review: SPEC-ANTIGRAVITY-001

**Reviewer:** vasquez (CTO, engineering owner)
**Date:** 2026-09-19
**Verdict:** CONDITIONAL (direction approved; `execute-spec` gated on conditions below)
**Skills cited:** `frame-ship:using-frame-ship` + `frame-ship:review-architecture`
**Packet (reference-only):** SPEC `docs/specs/50_archive/SPEC-ANTIGRAVITY-001.md` + REQ `docs/specs/15_requirements/REQ-antigravity-001.md` + CONTRACTS `docs/specs/10_design/ARCHITECTURE.md` (v2) + `docs/specs/10_design/API_CONTRACTS.md` (v2) + HARD (max-2, local-first, deny-default, no secrets) + GATE (BRIEF-approved montilla 2026-09-19; SPEC closed 176afd4) + DOMAINS `[engineering]`

## Contract Compliance

| Invariant | Status | Notes |
|-----------|--------|-------|
| INV-001 local-first `127.0.0.1` default | pass | `serverUrl: http://127.0.0.1:8080/mcp`; non-loopback only via explicit operator override. `SPEC-ANTIGRAVITY-001.md:80-81,117`; `API_CONTRACTS.md:32` |
| INV-002 env names frozen | pass | `MCP_GWAY_ALLOW_*` untouched (REQ-NF-002/AC-006); `MCP_GWAY_URL`/`MCP_GWAY_TOKEN` reused by default, no rename (A4). `SPEC-ANTIGRAVITY-001.md:60-62,89,105-106`; `ARCHITECTURE.md:44-45` |
| INV-003 no secrets | pass (conditional C2) | Static secret-free `mcp_config.json`; `headers.Authorization` manual user-side edit only, never committed (A1). `SPEC-ANTIGRAVITY-001.md:54-55,118-119`; `ARCHITECTURE.md:68-70` |
| INV-004 proof or REFUTED | pass | AC matrix demands session/compression/skill-list repros + diff excerpts + CI logs, file:line cited. `SPEC-ANTIGRAVITY-001.md:95-108,153-166` |
| INV-005 suite green + ruff | pass (gate) | 255 baseline + new plugin tests; `ruff check` + `format --check` clean. `SPEC-ANTIGRAVITY-001.md:85-86,104`; `REQ-antigravity-001.md:24` |
| INV-006 `X-Warning` gating | pass (untouched) | No gateway/observability change; out of scope. `SPEC-ANTIGRAVITY-001.md:131-132`; `ARCHITECTURE.md:49` |
| INV-007 additive-only `plugins/antigravity/`; `src/`+routes+CLI frozen | pass | Bundle layout per D1; gateway/CLI/registry/transport out of scope; domain control restates freeze. `SPEC-ANTIGRAVITY-001.md:68,112-114,131-132`; `ARCHITECTURE.md:66-68`; `API_CONTRACTS.md:28-29` |
| INV-008 no secret in bundle | pass (conditional C2, same as INV-003) | `ARCHITECTURE.md:68-70` |
| INV-009 MARKER verbatim + card ≡ MCP_RULES | pass (conditional C3) | MARKER `MCP-GWAY v2.8.0` verbatim matches live source `plugins/opencode/mcp-gateway.ts:3`; card substance ≡ `mcp-gateway.ts:5-33`. Rules-cap D5 (~12k) may force multi-file split — substance stays verbatim across split. `SPEC-ANTIGRAVITY-001.md:73-76,123-124`; `ARCHITECTURE.md:71`; `API_CONTRACTS.md:37-38` |
| INV-010 loopback `serverUrl` default | pass | `API_CONTRACTS.md:32`; `ARCHITECTURE.md:72` |
| HTTP/SSE + CLI contracts unchanged | pass | `API_CONTRACTS.md:8-19` no-shape-change; plugin adds no endpoint/adapter/payload/port/permission |

Parity mapping is sound: Antigravity has no `Plugin.define`/session-hook equivalent → `rules/*.md` (persistent card) + `PreInvocation`/`PostInvocation` reinject with MARKER dedupe (≡ `systemHasRules`/`pushRules`, `mcp-gateway.ts:60-77`) + `mcp_config.json` remote `serverUrl` (D7: `serverUrl`, not OpenCode `type`+`url`). Data flow at `ARCHITECTURE.md:62-64`; hook I/O at `SPEC-ANTIGRAVITY-001.md:120-122`.

## ADR Required?

- [x] Yes — **ADR-011 (accepted, recorded as contract v2 delta)**: Antigravity parity via declarative bundle, additive-only. Decision encoded in `ARCHITECTURE.md` v2 § Plugin Subsystem (`ARCHITECTURE.md:51-72`, INV-007–010) + `API_CONTRACTS.md` v2 § Plugin Contract (`API_CONTRACTS.md:26-46`), committed as `176afd4`. No standalone `docs/architecture/ADR-*.md` file created — repo keeps contracts as updated-in-place singletons and that directory does not exist on disk; this review file is the ADR record by reference.
- [ ] No invariant break approved. INV-007–010 hold; no waiver granted.

## Conditions for Approval (execute-spec gated)

1. **C1 — Proposal singleton:** `execute-spec` must reconcile against the antigravity-lane `PROPOSED_CHANGES.md` singleton before writing files. NOTE: the on-disk canonical `docs/specs/40_workspace/engineering/PROPOSED_CHANGES.md` currently describes the OpenCode plugin lane, not Antigravity — the ses_ proposal payload cited in the dispatch packet was not attached. Review was conducted against SPEC §4 + REQ + contract v2; any deviation in the actual proposal (new files outside `plugins/antigravity/**` + `tests/test_antigravity_plugin.py` + docs, any `src/` touch) re-opens this verdict to CLOSED.
2. **C2 — No-secret enforcement:** new plugin tests assert manifest valid, rules contain MARKER + mandatory order, `mcp_config.json` has no secret-like values; INSTALL documents `headers` as manual user edit only; `git diff` + secret grep evidence at gate (AC-005/AC-006).
3. **C3 — Verbatim parity:** rules diff vs `plugins/opencode/mcp-gateway.ts:5-33` shows substantive parity (order + Starlark convention + anti-patterns); if D5 cap forces a split, each file stays within cap and combined substance stays verbatim; marker count == 1 after compression repro (AC-002/AC-004).
4. **C4 — Security path-cite:** hook reinject script runs a local shell command — `review-risk` lens confirms non-escalating at quality-gate; full `review-security` STRIDE via montilla → barrera ONLY if a new trust boundary / exfiltration surface appears. No direct dispatch to `security` (INV-03).
5. **C5 — Contract already closed:** `ARCHITECTURE.md` v2 + `API_CONTRACTS.md` v2 (commit `176afd4`) are the ADR record; `execute-spec` must not modify contracts without a new ADR + this owner re-sign.

## Risks

- **R1 — Proposal payload absent (High/probable):** ses_ proposal return not attached; on-disk singleton is a different lane. Mitigation: C1. Owner remediates at execute-spec entry; unresolved deviation → CLOSED + escalate montilla.
- **R2 — Rules cap (Medium/conditional):** D5 ~12k char cap unverified against full MCP_RULES card; forced split risks drift. Mitigation: C3 + fresh-session repro (A3, KR-1.1); fallback F2 rules-only shim per SPEC A3.
- **R3 — Hook availability (Medium/conditional):** `PreInvocation`/`PostInvocation` + `injectSteps` semantics sourced from docs fetched 2026-09-19; unverified at runtime. Mitigation: re-verify at implement time per SPEC §6; fallback F2.
- **R4 — Hook shell surface (Low/conditional):** reinject script greps `transcriptPath`; least-privilege command, no new gateway boundary. Mitigation: C4 risk-lens confirm.
- **R5 — Env expansion (Low/accepted):** `mcp_config.json` env-var expansion unverified → static secret-free config per A1. Residual accepted: manual `headers` edit documented in INSTALL.

## Assumptions

- A1–A5 from `SPEC-ANTIGRAVITY-001.md:54-64` carry unchanged (static config/no token; MARKER grep dedupe; rules semantics verified by repro with F2 fallback; env names reused absent CEO waiver; engineering-owner role from delegation prompt per A5).
- Marker frozen at `MCP-GWAY v2.8.0` (`plugins/opencode/mcp-gateway.ts:3` verified); any upstream marker bump requires re-gate of INV-009.
- Multi-subagents max-2, local-first, deny-default, no-secrets HARD constraints bind execute-spec lanes.

## Cross-domain

- No sideways dispatch. Conditional security item briefed to montilla by reference: barrera path-cite at quality-gate per C4; full STRIDE only on new trust boundary (not expected).

## Sign-off

- [x] vasquez (CTO) — architecture review CONDITIONAL (conditions C1–C5 above)
- [ ] barrera (CISO) — path-cite conditional only (C4); no gate held here
