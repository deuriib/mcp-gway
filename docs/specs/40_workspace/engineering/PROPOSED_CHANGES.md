# PROPOSED_CHANGES — Antigravity CLI Plugin Parity (SPEC-ANTIGRAVITY-001)

**Spec refs (reference-only):** `docs/specs/50_archive/SPEC-ANTIGRAVITY-001.md`, `docs/briefs/BRIEF-antigravity-plugin.md`, `docs/specs/15_requirements/REQ-antigravity-001.md`, `docs/specs/40_workspace/architecture/ARCHITECTURE-REVIEW-ANTIGRAVITY-001.md` (ADR-011 conditional approval), official Antigravity customization docs (`plugins`, `hooks`, `rules`, `mcp_servers`, `skills`).
**Execution mode:** `single` (engineering-only direct execution, no dispatch).
**DOMAINS:** `[engineering]`.
**Skills cited:** `frame-ship:using-frame-ship` + `frame-ship:translate-to-spec` + `frame-ship:propose-changes` (this proposal) → `frame-ship:review-architecture` (conditions C1-C5 satisfied) → `frame-ship:execute-spec` → `frame-ship:quality-gate` → `frame-ship:verify-handoff`.
**Date:** 2026-09-19.
**Owner:** vasquez (CTO, engineering chain owner).

---

## 1. Summary of Proposed Changes

Establish complete parity for the Google Antigravity IDE by providing a standard Antigravity plugin bundle in `plugins/antigravity/` mirroring the capabilities of `plugins/opencode/mcp-gateway.ts`.

### Defect Analysis of Current Implementation:
1. **`hooks.json` schema violation**: Current file uses an alien array structure `{"hooks": [{"event": "PreInvocation", ...}]}` which is rejected by Antigravity. Antigravity requires an object keyed by hook name, with event names as arrays of handler objects:
   ```json
   {
     "mcp-gateway-reinject": {
       "PreInvocation": [
         {
           "type": "command",
           "command": "sh ./scripts/reinject.sh",
           "timeout": 10
         }
       ]
     }
   }
   ```
2. **Missing `rules/` directory**: No rules file exists in `plugins/antigravity/rules/`. Per Antigravity specs, `plugins/antigravity/rules/AGENTS.md` must carry the persistent Gateway Protocol card with `<!-- MCP-GWAY v2.8.0 -->`, 4-step order, Starlark calling convention, and anti-patterns table.
3. **Missing `skills/` directory**: No skill file exists in `plugins/antigravity/skills/`. To achieve parity where the skill loads automatically with the plugin, `plugins/antigravity/skills/mcp-gway/SKILL.md` must be bundled.
4. **Missing `INSTALL.md`**: No installation guide, verify matrix, or rollback instructions for Antigravity operators.
5. **Missing automated tests**: No `tests/test_antigravity_plugin.py` to assert bundle integrity, manifest validity, loopback enforcement, secret-free config, hook execution, and dedupe behavior.

---

## 2. REQ-ID Traceability

| REQ-ID | Target File | Action | Description |
|---|---|---|---|
| **REQ-F-001** | `plugins/antigravity/` | Scaffold | Complete bundle containing manifest, mcp_config, hooks, skill, rules, and INSTALL |
| **REQ-F-002** | `plugins/antigravity/plugin.json` | Fix/Format | Valid manifest: `$schema`, `name: "mcp-gateway"`, `version: "2.8.0"`, descriptive text |
| **REQ-F-003** | `plugins/antigravity/skills/mcp-gway/SKILL.md` | Create | Full parity with root `skills/mcp-gway/SKILL.md` |
| **REQ-F-004** | `plugins/antigravity/rules/AGENTS.md` | Create | Complete Gateway Protocol guidance verbatim with marker `<!-- MCP-GWAY v2.8.0 -->` |
| **REQ-F-005** | `plugins/antigravity/hooks.json` & `scripts/reinject.sh` | Fix/Update | Valid Antigravity hook schema; robust reinject script with MARKER dedupe via `transcriptPath` |
| **REQ-F-006** | `plugins/antigravity/mcp_config.json` | Validate/Format | `gateway` remote `serverUrl: http://127.0.0.1:8080/mcp`, strictly secret-free |
| **REQ-F-007** | `plugins/antigravity/INSTALL.md` | Create | Workspace (`.agents/plugins/`) and global install paths, verify matrix, rollback |
| **REQ-NF-001** | `tests/test_antigravity_plugin.py` | Create | 100% pass on pytest suite, ruff check/format clean |
| **REQ-NF-002** | Entire repo | Verify | Additive only: `src/` untouched, `MCP_GWAY_ALLOW_*` untouched, loopback default |
| **REQ-NF-003** | `plugins/antigravity/` | Verify | No PII in rules/hooks/scripts (Ley 172-13) |

---

## 3. Files to Create and Modify

### Modified:
- `plugins/antigravity/plugin.json`: Formatted, verified JSON manifest.
- `plugins/antigravity/hooks.json`: Fixed to Antigravity hook schema.
- `plugins/antigravity/scripts/reinject.sh`: Hardened dedupe, executable permission.
- `plugins/antigravity/mcp_config.json`: Formatted, verified loopback remote config.

### Created:
- `plugins/antigravity/rules/AGENTS.md`: Full Gateway Protocol guidance with MARKER.
- `plugins/antigravity/skills/mcp-gway/SKILL.md`: Bundled CLI reference skill.
- `plugins/antigravity/INSTALL.md`: Setup guide, test steps, verification matrix.
- `tests/test_antigravity_plugin.py`: Comprehensive test suite verifying all functional & non-functional requirements.

---

## 4. Risk Assessment & Blast Radius

- **Systems**: Low. Changes are strictly additive under `plugins/antigravity/`, `tests/test_antigravity_plugin.py`, and documentation. Zero modifications to `src/mcp_gway/` or existing CLI commands.
- **Security**: Zero secrets in bundle files. Loopback `127.0.0.1:8080` only. Hook script executes local `sh` command with no network access, no file writes, and no privileges escalation.
- **Rollback**: Delete `plugins/antigravity/` and `tests/test_antigravity_plugin.py`. Reversible in seconds.
