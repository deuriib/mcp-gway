# IMPLEMENTATION_PLAN — Antigravity CLI Plugin Parity (SPEC-ANTIGRAVITY-001)

**Spec:** `docs/specs/50_archive/SPEC-ANTIGRAVITY-001.md`
**Proposal:** `docs/specs/40_workspace/engineering/PROPOSED_CHANGES.md`
**Execution Mode:** `single`
**Domains:** `[engineering]`
**Owner:** vasquez (CTO)

---

## Steps & Order

1. **Step 1: Manifest & Config** (REQ-F-001, REQ-F-002, REQ-F-006)
   - Update `plugins/antigravity/plugin.json` (valid schema, name `mcp-gateway`, version 2.8.0)
   - Format `plugins/antigravity/mcp_config.json` (serverUrl loopback, secret-free)

2. **Step 2: Hooks & Reinjection** (REQ-F-005)
   - Fix `plugins/antigravity/hooks.json` to Antigravity schema (`{"mcp-gateway-reinject": {"PreInvocation": [...]}}`)
   - Harden `plugins/antigravity/scripts/reinject.sh` for POSIX execution, transcript parsing, MARKER dedupe, chmod +x

3. **Step 3: Guidance & Rules** (REQ-F-004)
   - Create `plugins/antigravity/rules/AGENTS.md` containing `<!-- MCP-GWAY v2.8.0 -->`, 4-step order, Starlark calling convention, anti-patterns

4. **Step 4: Skill Bundling** (REQ-F-003)
   - Create `plugins/antigravity/skills/mcp-gway/SKILL.md` matching root skill

5. **Step 5: Documentation** (REQ-F-007)
   - Create `plugins/antigravity/INSTALL.md` with workspace/global installation, verify matrix, troubleshooting, rollback

6. **Step 6: Automated Testing & Verification** (REQ-NF-001, REQ-NF-002, REQ-NF-003)
   - Create `tests/test_antigravity_plugin.py` validating manifest, mcp_config, hooks, reinject dedupe, rules marker, skill, no secrets, no PII
   - Run `uv run pytest -v tests/test_antigravity_plugin.py`
   - Run full suite `uv run pytest` + `uv run ruff check` + `uv run ruff format --check`

7. **Step 7: Quality Gate & Handoff**
   - Update `TEST_MATRIX.md`
   - Produce Quality Gate Report and `HANDOFF.md`
