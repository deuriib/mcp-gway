# BUILD — rename-execute-tool

## Log (one row per FRAME criterion)

- [x] Zero hits for executeToolCode across src/, skills/, plugins/, and tests/ → src/mcp_gway/gateway.py, src/mcp_gway/code_mode.py, skills/, plugins/, tests/
- [x] Canonical name executeTool (and gateway_executeTool) exposed and documented → src/mcp_gway/gateway.py, rules/mcp-gway.md, docs/code-mode.md, README.md
- [x] 100% of existing and updated tests pass → tests/test_gateway.py, tests/test_admin_dashboard.py, tests/test_tools_cli.py (688 passed in CI)
- [x] CHANGELOG.md entry documents the breaking rename under unreleased/next release section → CHANGELOG.md

## Deviations from PROPOSE

- None.

## Artifacts produced (grouped by domain)

- Engineering:
  - `src/mcp_gway/gateway.py` — rename meta-tool to `executeTool` and update tool call dispatch
  - `src/mcp_gway/code_mode.py` — `execute_tool` method, validation error messages, and compatibility alias
  - `src/mcp_gway/registry.py` — virtual stub comment update
  - `src/mcp_gway/cli.py` — `tools_exec` docstring and execution call
  - `src/mcp_gway/admin/routes.py` — execution call update
  - `rules/mcp-gway.md` — rule card updated to `gateway_executeTool`
  - `plugins/opencode/mcp-gateway.ts` — plugin rule card updated
  - `plugins/antigravity/INSTALL.md` & `plugins/antigravity/scripts/reinject.mjs` — plugin rule guidance updated
  - `.pi/extensions/mcp-gateway.ts` — extension rule fallback updated
  - `skills/mcp-gway-cli/SKILL.md` & `skills/mcp-gway-mcp/SKILL.md` — skill surfaces updated
- Testing:
  - `tests/test_gateway.py` — updated tool names in `tools/list` and `tools/call` tests
  - `tests/test_edgecases_gateway.py` — updated `executeTool` parameter validation tests
  - `tests/test_call_many_meta.py` — updated `tools/list` set assertion
  - `tests/test_antigravity_plugin.py` — updated rule assertion
  - `tests/test_observability_instrumentation.py` — updated tool call assertion
  - `tests/test_p0_wave4_highs.py` — updated event loop offload test
  - `tests/test_registry.py` — updated stub comment assertion
  - `tests/test_admin_dashboard.py` — updated timeout mocking
  - `tests/test_tools_cli.py` — updated CLI exec mocking
  - `tests/pi_extension.test.mjs` — updated step assertion
- Product:
  - `README.md` — meta-tool list updated
  - `docs/code-mode.md` — documentation and discovery flow updated
  - `docs/architecture.md` — meta-tool listing updated
  - `docs/briefs/BRIEF-antigravity-plugin.md` — key result order updated
  - `docs/specs/10_design/ARCHITECTURE.md` — component responsibility updated
  - `docs/specs/10_design/CALL_MANY.md` — envelope reference updated
  - `docs/specs/12_adr/ADR-015-callmany-meta-tool.md` — alternatives reference updated
  - `docs/specs/30_delivery/IMPLEMENTATION-PLAN-CALLMANY.md` — delivery checklist updated
  - `docs/specs/30_delivery/PERF-FINDINGS-v2.4.0.md` — profiling targets updated
  - `docs/specs/30_delivery/RUNBOOK-perf.md` — perf runbook updated
  - `docs/specs/30_delivery/bench_perf.py` & `perf_config.yaml` — bench configuration updated
  - `CHANGELOG.md` — breaking change entry added under Unreleased

## Cross-domain handoffs

- Core dispatcher rename delivered to Testing — Done.
- Test suite updates delivered to Verification — Done.
- Documentation and changelog delivered to Product — Done.

## Assigned team

- Domain: Atlas (Engineering, Testing, Product) — implement rename and test updates.
- Process steward: Atlas (Process Steward) — confirm BUILD protocol adherence.

## Gates

- Domain gate: N/A — deferred to VERIFY
- Process gate: Atlas (Process Steward) — PASS
