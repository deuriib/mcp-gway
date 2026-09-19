# Spec: Antigravity CLI Plugin Parity — MCP Gateway

**ID:** SPEC-ANTIGRAVITY-001
**Owner:** vasquez (CTO)
**Domains-Touched:** [engineering]
**Brief Reference:** BRIEF-ANTIGRAVITY-001
**Status:** draft
**Priority:** P1
**Execution_Mode:** multi-subagents (inherited from BRIEF-ANTIGRAVITY-001, frozen 2026-09-19; max 2 parallel lanes; no per-SPEC override)

## 1. Context

BRIEF-ANTIGRAVITY-001 asks for OpenCode parity inside Google Antigravity IDE: automatic
`mcp-gway` skill load, gateway MCP registration, and Gateway Protocol injection that
survives context compression. The parity source is `plugins/opencode/mcp-gateway.ts:1-188`
(MARKER + MCP_RULES + `systemHasRules`/`pushRules` + `ctx.mcp`/`ctx.skill` transforms +
`context`/`compaction` hooks), the skill body `skills/mcp-gway/SKILL.md:1-106`, and the
install/verify pattern `plugins/opencode/INSTALL.md:1-137`.

Antigravity has no `Plugin.define` TypeScript API and no `context`/`compaction` session
hooks. SPEC discovery (official docs, fetched 2026-09-19) found the native parity mapping:
declarative plugin bundle (`plugin.json` + `mcp_config.json` + `hooks.json` + `skills/` +
`rules/`) where `rules/*.md` carry persistent guidance and `PreInvocation`/`PostInvocation`
hook handlers reinject via `injectSteps` (`ephemeralMessage`). Findings D1–D8 below are
the contract basis; assumptions A1–A5 gate `propose-changes`.

### Discovery findings (antigravity.google/docs, 2026-09-19)

- D1 — Plugin layout: `plugins/<name>/{plugin.json, mcp_config.json, hooks.json,
  skills/<skill>/SKILL.md, agents/<agent>.md, rules/<rule>.md}` (`/docs/plugins`).
- D2 — Manifest: `plugin.json` required; fields `name` (`^[a-zA-Z0-9-_]+$`, required on CLI)
  + `description`; `$schema: https://antigravity.google/schemas/v1/plugin.json` for validation.
- D3 — Install locations: workspace `.agents/plugins/` vs global `~/.gemini/config/plugins/`
  (`/docs/plugins` § manual installation).
- D4 — Skills: `<skill>/SKILL.md` with `name` + `description` frontmatter; agent reads
  name/description first, loads body on match; scopes: workspace `.agents/skills/`, global
  `~/.gemini/antigravity-cli/skills/`, plugin-bundled `plugins/<p>/skills/` (`/docs/skills`).
- D5 — Rules: `rules/*.md`; fire as always-on / glob / model-decision / @-mention; ~12,000
  char cap per surface (firecrawl/antigravity-skills summary; verify cap during repro).
- D6 — Hooks (`/docs/hooks`): events `PreToolUse`/`PostToolUse` (matcher = tool-name regex)
  + `PreInvocation`/`PostInvocation` (matcher ignored; output `injectSteps` with
  `toolCall | userMessage | ephemeralMessage`) + `Stop`; handler `{type: "command",
  command, timeout}` (default 30s); stdin JSON in / stdout JSON out (camelCase).
- D7 — MCP config (`/docs/mcp`): `{mcpServers: {<id>: {serverUrl | command, args?, env?,
  cwd?, headers?, authProviderType?, oauth?, disabled?, disabledTools?}}}`; remote transport
  is `serverUrl` (not OpenCode's `type: "remote"` + `url`); OAuth DCR automatic, manual
  `oauth: {clientId, clientSecret}`, tokens in `~/.gemini/antigravity/mcp_oauth_tokens.json`.
- D8 — No `context`/`compaction` session-hook equivalent exists; parity mapping is
  `rules/*.md` (persistent card) + `PreInvocation` reinject script with MARKER dedupe
  (mirrors `systemHasRules`/`pushRules`, `plugins/opencode/mcp-gateway.ts:60-77`).

### Assumptions (carry into propose-changes)

- A1 — `mcp_config.json` env-var expansion is unverified → ship static config with NO token;
  INSTALL documents manual `headers` edit. Never bake secrets (guardrail 1).
- A2 — Marker dedupe runs in a hook script that greps MARKER in `transcriptPath`
  (input field per `/docs/hooks`); emits `injectSteps: []` when present.
- A3 — Rules auto-load exact semantics (always-on vs glob) verified by fresh-session repro
  (KR-1.1); fallback F2 (rules-only shim) if hooks prove unavailable.
- A4 — Env override names default to reuse: `MCP_GWAY_URL` / `MCP_GWAY_TOKEN`
  (mirrors `plugins/opencode/mcp-gateway.ts:50-58`); Antigravity-namespaced rename only
  with CEO waiver.
- A5 — `agents/c-level/vasquez.md` (cited in brief § Stakeholders) is absent from the repo;
  engineering-owner role taken from the session delegation prompt instead.

## 2. Requirements

- REQ-F-001: Scaffold `plugins/antigravity/` with `plugin.json`, `mcp_config.json`,
  `hooks.json`, `skills/mcp-gway/SKILL.md`, `rules/` guidance files, `INSTALL.md`
- REQ-F-002: `plugin.json` valid manifest (`name: mcp-gateway`, description, `$schema` key)
- REQ-F-003: Skill `SKILL.md` content parity with `skills/mcp-gway/SKILL.md` (name +
  description frontmatter + CLI command reference + local-first guards)
- REQ-F-004: `rules/` carries complete gateway guidance verbatim in substance: mandatory
  `gateway_*` order, Starlark calling convention (brackets-not-dot, sync-only, kwargs,
  fresh-scope), parallel discipline, anti-patterns table (≡ MCP_RULES,
  `plugins/opencode/mcp-gateway.ts:5-33`); per-file size within the rules cap (split if needed)
- REQ-F-005: `hooks.json` reinjects the Gateway Protocol card on `PreInvocation`
  (+ `PostInvocation`) via a script that dedupes by MARKER (`MCP-GWAY v2.8.0` verbatim);
  marker count == 1 after compression cycle
- REQ-F-006: `mcp_config.json` registers `gateway` as remote `serverUrl:
  http://127.0.0.1:8080/mcp` (local-first default); no token/secret baked in (A1)
- REQ-F-007: `INSTALL.md` parity with `plugins/opencode/INSTALL.md`: prereqs (gateway on
  localhost first), workspace + global install paths, verify matrix (health, marker in
  prompt, skill listed), troubleshooting, rollback
- REQ-NF-001: No regression — full suite green + `ruff check` + `ruff format --check` clean,
  plus new plugin tests (manifest JSON valid, rules contain MARKER + mandatory order,
  `mcp_config.json` has no secret-like values)
- REQ-NF-002: No new trust boundary — no new gateway endpoint/adapter/payload/port/permission;
  `MCP_GWAY_ALLOW_LOCAL_COMMANDS` / `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL` untouched;
  `127.0.0.1` default preserved
- REQ-NF-003: Ley 172-13 minimization — no PII in rules/hooks/logs/examples

## 3. Acceptance Criteria

- [ ] AC-001: Fresh Antigravity session prompt contains the `MCP-GWAY` marker card —
  evidence: session repro + prompt excerpt cited file:line (KR-1.1)
- [ ] AC-002: Protocol survives compression cycle with marker count == 1, no duplicates —
  evidence: compression repro log (KR-1.2)
- [ ] AC-003: `mcp-gway` skill listed without manual import — evidence: skill-list repro
  cited (KR-1.3)
- [ ] AC-004: `rules/` content diff vs MCP_RULES (`plugins/opencode/mcp-gateway.ts:5-33`)
  shows substantive parity (order + convention + anti-patterns) — evidence: diff excerpt (KR-2.1/2.2)
- [ ] AC-005: `uv run pytest -v` green (255 baseline + new), `ruff check src/ tests/` +
  `ruff format --check src/ tests/` clean — evidence: CI output (KR-2.3)
- [ ] AC-006: No secret/token/credential in diff; `MCP_GWAY_ALLOW_*` strings untouched —
  evidence: `git diff` + grep
- [ ] AC-007: Gateway + MCP live over loopback (`curl -s http://127.0.0.1:8080/health`) —
  evidence: verify-matrix log in INSTALL

## 4. Contracts & Interfaces

- Bundle layout (per D1): `plugins/antigravity/{plugin.json, mcp_config.json, hooks.json,
  skills/mcp-gway/SKILL.md, rules/<rule>.md, INSTALL.md}` (+ optional hook scripts
  colocated, e.g. `scripts/reinject.sh`)
- Manifest: `{"$schema": "https://antigravity.google/schemas/v1/plugin.json",
  "name": "mcp-gateway", "description": "..."}` (D2)
- MCP entry: `{"mcpServers": {"gateway": {"serverUrl": "http://127.0.0.1:8080/mcp"}}}`;
  optional `headers: {Authorization: "Bearer ..."}` documented as manual user edit only,
  never committed (D7 + A1 + guardrail 1)
- Hook I/O: stdin JSON (`invocationNum`, `transcriptPath`, common fields) → stdout JSON
  (`{injectSteps: [{ephemeralMessage: "<!-- MARKER -->\n<card>"}]}` or `{injectSteps: []}`);
  handler `{type: "command", command, timeout ≤ 30}` (D6 + A2)
- Marker: `MCP-GWAY v2.8.0` string reused verbatim (`plugins/opencode/mcp-gateway.ts:3`);
  card substance ≡ MCP_RULES (`:5-33`)
- Env names: `MCP_GWAY_URL` / `MCP_GWAY_TOKEN` reused by default (A4); install script (if any)
  reads env at install time, never writes secrets to the repo
- Canonical consolidation: `docs/specs/10_design/ARCHITECTURE.md` (v2, plugin section) +
  `docs/specs/10_design/API_CONTRACTS.md` (v2, plugin contract section), updated in place

## 5. Out of Scope

- Gateway server / CLI / registry / transport changes (reuse as-is)
- Dashboard/catalog revival (retired v2.0.0)
- Non-loopback expose without `MCP_GWAY_ALLOW_REMOTE=1` + firewall/auth
- Secrets/tokens/creds in code, config, logs, examples, or rules
- Key rotation, prod patching, permission widening (owner remediates)
- Multi-IDE abstraction beyond Antigravity + OpenCode
- `agents/` subagent definitions (not in brief scope; add only if parity repro demands)

## 6. Dependencies

- Upstream: BRIEF-ANTIGRAVITY-001 (read-only; never modified here)
- Parity sources: `plugins/opencode/mcp-gateway.ts`, `skills/mcp-gway/SKILL.md`,
  `plugins/opencode/INSTALL.md`
- External (docs only, no code dep): antigravity.google `/docs/plugins`, `/docs/hooks`,
  `/docs/mcp`, `/docs/skills` (fetched 2026-09-19; re-verify at implement time)
- Downstream: `PROPOSED_CHANGES.md` (next stage), then `plugins/antigravity/**` +
  `tests/test_antigravity_plugin.py` + docs edits
- Security: `barrera` path-cite conditional — full `review-security` STRIDE only if the
  proposal introduces a new trust boundary / exfiltration surface (not expected; hooks run
  local shell commands, which the risk lens must confirm as non-escalating)

## 7. Traceability

| Requirement | Acceptance Criterion | Proposed Change | Evidence |
|-------------|---------------------|-----------------|----------|
| REQ-F-001 | AC-001, AC-003, AC-007 | PROPOSED_CHANGES.md § scaffold | bundle file list + install repro |
| REQ-F-002 | AC-001 | PROPOSED_CHANGES.md § manifest | `plugin.json` + schema validation |
| REQ-F-003 | AC-003 | PROPOSED_CHANGES.md § skill | skill-list repro + content diff |
| REQ-F-004 | AC-004 | PROPOSED_CHANGES.md § rules | rules diff vs MCP_RULES |
| REQ-F-005 | AC-002 | PROPOSED_CHANGES.md § hooks | compression repro, marker count == 1 |
| REQ-F-006 | AC-007 | PROPOSED_CHANGES.md § mcp_config | health check + MCP list repro |
| REQ-F-007 | AC-007 | PROPOSED_CHANGES.md § docs | INSTALL diff file:line |
| REQ-NF-001 | AC-005 | n/a (gate) | `pytest` + `ruff` logs |
| REQ-NF-002 | AC-006 | n/a (gate) | `git diff` + grep for env names/secrets |
| REQ-NF-003 | AC-006 | n/a (gate) | PII grep over `plugins/antigravity/` |
