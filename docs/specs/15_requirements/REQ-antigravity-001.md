# Requirements Index: Antigravity CLI Plugin Parity

**Owner:** vasquez (CTO)
**Brief Reference:** BRIEF-ANTIGRAVITY-001
**Domains-Touched:** [engineering]

## Functional Requirements

| ID | Requirement | Priority | Source | Spec | Domain | Evidence Type |
|----|-------------|----------|--------|------|--------|---------------|
| REQ-F-001 | `plugins/antigravity/` scaffold (manifest, MCP config, hooks, skill, rules, INSTALL) | P0 | BRIEF-ANTIGRAVITY-001 | SPEC-ANTIGRAVITY-001 | engineering | review (bundle file list + install repro) |
| REQ-F-002 | `plugin.json` valid manifest (`mcp-gateway` + `$schema`) | P0 | BRIEF-ANTIGRAVITY-001 | SPEC-ANTIGRAVITY-001 | engineering | test (JSON schema validation) |
| REQ-F-003 | Skill `SKILL.md` parity with `skills/mcp-gway/SKILL.md` | P0 | BRIEF-ANTIGRAVITY-001 | SPEC-ANTIGRAVITY-001 | engineering | test (content diff) + skill-list repro |
| REQ-F-004 | `rules/` complete gateway guidance (order + Starlark + anti-patterns) | P0 | BRIEF-ANTIGRAVITY-001 | SPEC-ANTIGRAVITY-001 | engineering | test (MARKER + order assertions) + diff |
| REQ-F-005 | `hooks.json` reinject with MARKER dedupe, count == 1 | P0 | BRIEF-ANTIGRAVITY-001 | SPEC-ANTIGRAVITY-001 | engineering | test (script unit) + compression repro |
| REQ-F-006 | `mcp_config.json` gateway remote `serverUrl` loopback, secret-free | P0 | BRIEF-ANTIGRAVITY-001 | SPEC-ANTIGRAVITY-001 | engineering | test (no-secret grep) + health repro |
| REQ-F-007 | `INSTALL.md` parity (prereqs, install, verify matrix, rollback) | P1 | BRIEF-ANTIGRAVITY-001 | SPEC-ANTIGRAVITY-001 | engineering | review (doc diff file:line) |

## Non-Functional Requirements

| ID | Requirement | Category | Target |
|----|-------------|----------|--------|
| REQ-NF-001 | Suite green + lint/format clean + new plugin tests | Reliability | 255/255 + new; `ruff check` + `ruff format --check` clean |
| REQ-NF-002 | No new trust boundary / names unchanged / loopback default | Security | No new endpoint/adapter/payload; `MCP_GWAY_ALLOW_*` untouched; no secrets in diff |
| REQ-NF-003 | No PII in rules/hooks/logs/examples | Privacy (Ley 172-13) | PII grep over `plugins/antigravity/` clean |

## Domain Controls (only touched domains)

| Domain | Control | Owner |
|--------|---------|-------|
| engineering | Plugin bundle additive only (`plugins/antigravity/**` + tests + docs); `src/`, gateway routes, CLI untouched | vasquez |
| security | Conditional lens only — full STRIDE only if new boundary/exfiltration surface appears | barrera (path-cite) |
