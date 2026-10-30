# FRAME — rename-execute-tool

## Goal

Rename the MCP meta-tool `executeToolCode` to `executeTool` across gateway surfaces (code, skills, agent rules, and docs) to eliminate semantic confusion with arbitrary code execution while keeping all MCP dispatch functionality intact.

## Success criteria (measurable)

- [ ] Zero hits for `executeToolCode` across `src/`, `skills/`, `plugins/`, and `tests/`.
- [ ] Canonical name `executeTool` (and `gateway_executeTool`) is exposed by Code Mode tools and documented in `AGENTS.md`.
- [ ] 100% of existing and updated tests pass (`pytest` exit code 0, 688+ tests passing).
- [ ] `CHANGELOG.md` entry documents the breaking rename under the unreleased / next release section.

## Scope

- In: Rename `executeToolCode` to `executeTool` in `src/mcp_gway/code_mode.py`, `skills/`, `plugins/`, `tests/`, `AGENTS.md`, and docs.
- Out: No changes to Starlark execution model, sandbox execution, budget accounting, `call_many` / `callMany`, or underlying MCP server dispatch logic.

## Domain profile

- Domains involved: Engineering, Testing, Product
- Deliverable type: code
- Optional phases: research? no — measure? no

## Constraints

- Zero breaking regression in existing MCP tool calling capabilities or Starlark sandbox security constraints.
- Test suite pass rate: 100% (pytest passing with 0 failures).
- Python 3.12+ compatibility maintained per `pyproject.toml`.

## Assigned team

- Domain: Atlas (Engineering & Testing) — implement rename across core gateway, update test assertions, and ensure clean CI pass.
- Process steward: Atlas (Process Steward) — verify compliance with Agency-Flow methodology and two-gate model.

## Gates

- Domain gate: Atlas (Engineering) — PASS
- Process gate: Atlas (Process Steward) — PASS
