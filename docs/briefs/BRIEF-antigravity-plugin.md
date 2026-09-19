# Product Brief: Antigravity CLI Plugin Parity — MCP Gateway

**ID:** BRIEF-ANTIGRAVITY-001
**Initiator:** montilla (CEO)
**Date:** 2026-09-19
**Status:** draft
**Execution_Mode:** multi-subagents (frozen at frame-intent per initiator 2026-09-19; all specs follow unless overridden per SPEC with CEO waiver, max 2 parallel lanes)
**Domains-Touched:** [engineering]
**Classification:** architectural-initiative (new plugin subsystem for Google Antigravity IDE, parity with `plugins/opencode/mcp-gateway.ts`)
**Framings-Considered:** F1 full parity port (Recommended) vs F2 rules-only shim vs F3 spike-first discovery; see Framings section below. YAGNI cut applied throughout.
**Approval:** file-approval — pending initiator yes

## Framings-Considered

- **F1 — Full parity port (Recommended):** new `plugins/antigravity/` scaffold mirroring `plugins/opencode/mcp-gateway.ts`: skill auto-load, context-injection hook, compression/compaction reinject with marker dedupe, gateway MCP remote registration, plus `/rules` folder with complete gateway-protocol guidance. Why lead: delivers the asked parity in one SPEC cycle; reuses proven MARKER + MCP_RULES + Starlark convention verbatim.
- **F2 — Rules-only shim:** only static `/rules` files, no hooks, no auto skill load. Trade-off: cheapest but breaks parity — context lost after compression, skill not automatic. Rejected as default; viable fallback if Antigravity hook API proves absent.
- **F3 — Spike-first discovery:** feasibility probe answering what Antigravity CLI actually supports (manifest, hooks, rules auto-load) before committing. Trade-off: de-risks F1 but delays value. Folded into F1 as SPEC discovery task, not a separate initiative.

YAGNI cut: no new gateway endpoints, no CLI changes, no dashboard/catalog revival, no multi-IDE abstraction, no auth redesign.

## Problem Statement

`mcp-gway` operators moving to Google Antigravity IDE lose the OpenCode parity they rely on: automatic `mcp-gway` skill load, gateway MCP registration, and system-prompt injection of the Gateway Protocol that survives context compression. Without it, agents guess tool names, skip `listToolFiles`/`readToolFile` order, assume cross-call state, and break Starlark calling convention. It matters now because the gateway is CLI-only headless local-first — the plugin is the only guidance surface.

## Desired Outcome

An Antigravity plugin with OpenCode parity: skill loads automatically, context + compression hooks reinject the Gateway Protocol card (deduped by marker), and a `/rules` folder carries the complete guidance on MCP use and tool calling. Success = fresh Antigravity session sees the protocol, survives compression, and calls `gateway_*` in mandatory order with brackets-not-dot evidence.

## Scope

### In Scope

- Antigravity plugin scaffold parity with `plugins/opencode/mcp-gateway.ts` (manifest, entry, gateway URL/token env resolution) [engineering]
- Skill auto-load equivalent of `ctx.skill.transform` for `skills/mcp-gway/SKILL.md` [engineering]
- Hooks: context-injection + compression/compaction reinject with `MARKER` dedupe (`MCP-GWAY v2.8.0`) [engineering]
- `/rules` folder: complete guidance — mandatory `gateway_*` order, Starlark convention, parallel discipline, anti-patterns table [engineering]
- Gateway MCP remote registration equivalent (`type remote`, `http://127.0.0.1:8080/mcp`, timeouts, optional Bearer header) [engineering]
- Docs INSTALL parity + verify matrix (health, session prompt contains marker, skill listed) [engineering]
- REQ→test→artifact evidence matrix for the gate [engineering]

### Out of Scope

- Gateway server / CLI / registry / transport changes (reuse as-is)
- Reviving dashboard/catalog retired in v2.0.0
- Non-loopback expose without `MCP_GWAY_ALLOW_REMOTE=1` + firewall/auth
- Secrets/tokens/creds in code, config, logs, examples, or rules
- Key rotation, prod patching, permission widening (owner remediates; we report severity + location)
- Multi-IDE abstraction beyond Antigravity + OpenCode

## Stakeholders

| Role | Agent | Involvement |
|------|-------|-------------|
| Sponsor | montilla | Decision authority, brief owner |
| Owner | vasquez (CTO) | Delivery ownership |
| Touched | barrera (CISO) path-cite condicional | Review only if new trust boundary / exfiltration surface introduced |

> Craft cited by path (no inline): `agents/c-level/vasquez.md` primary in `translate-to-spec`; `agents/c-level/barrera.md` conditional on trust-boundary delta.

## Constraints

- Budget: to confirm [dauhajre]
- Timeline: feasibility to confirm [vasquez]
- Regulatory: Ley 172-13 minimization — no PII in rules/hooks/logs; map flow source→store→log→third party if touched; PASS exports allowlisted evidence only
- Security (guardrails 1-15): deny default; no secret/token/credential/session in code/config/logs/examples/events; finding without proof (diff/scan/log) = REFUTED; least privilege per interface; `MCP_GWAY_ALLOW_LOCAL_COMMANDS` / `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL` not renamed; new hooks/endpoints = trust boundaries (STRIDE at review)
- Local-first: `127.0.0.1` default; `0.0.0.0` requires `MCP_GWAY_ALLOW_REMOTE=1` else `exit 2`; never expose without firewall/auth
- Brand/GTM: internal only, no external announcement (per AGENTS.md internal releases note)
- People/change: skill auto-loads, additive transforms only, never overwrite user values

## Open Questions

- [ ] Antigravity plugin manifest + hook names for context vs compression? (discover in SPEC) [vasquez]
- [ ] `/rules` auto-load vs manual include, exact folder path + file naming? [vasquez]
- [ ] Skill resolution bases in Antigravity (project canonical/directory equivalents)? [vasquez]
- [ ] Gateway env override names reused (`MCP_GWAY_URL` / `MCP_GWAY_TOKEN`) or Antigravity-namespaced? [vasquez]

---

# OKRs: Antigravity CLI Plugin Parity — MCP Gateway

**Period:** Q3 2026
**Owner:** montilla (CEO)

## Objective 1: Parity that survives real sessions

| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| KR-1.1 Protocol visible on fresh session | Antigravity: none | System prompt contains `MCP-GWAY` marker card | fresh-session repro + prompt excerpt cited file:line |
| KR-1.2 Protocol survives compression | lost on compact | Reinject on compression with dedupe, no duplicates | compression repro + marker count == 1 |
| KR-1.3 Skill auto-loads | manual | `mcp-gway` skill listed without manual import | skill-list repro cited |

## Objective 2: Correct tool calling by default

| Key Result | Baseline | Target | Measurement |
|------------|----------|--------|-------------|
| KR-2.1 Mandatory order followed | ad-hoc | `listToolFiles` → `readToolFile` → `getToolDocs?` → `executeToolCode` in `/rules` + hooks | rules content diff vs `plugins/opencode/mcp-gateway.ts` MCP_RULES |
| KR-2.2 Starlark convention correct | guesses | Brackets-not-dot, sync-only, kwargs, fresh-scope in guidance | rules excerpt + session evidence |
| KR-2.3 Suite green, no regression | 255 tests baseline | Full suite green + new plugin tests + ruff clean | `uv run pytest -v` + `ruff check` + `ruff format --check` |
