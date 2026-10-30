# PROPOSE — rename-execute-tool

## Approach

Perform a direct, clean breaking rename of `executeToolCode` to `executeTool` across gateway core dispatch, error messages, stub comments, client skills, agent plugins, documentation, and test suites. We explicitly reject introducing a backward-compatibility deprecation shim for `executeToolCode` because the gateway contract is explicitly versioned, internal callers and agent definitions are synchronized within this repository, and maintaining legacy aliases produces ongoing semantic ambiguity and dead code.

## Planned deliverables (grouped by domain)

- Engineering:
  - Meta-tool definition & dispatcher rename in `src/mcp_gway/gateway.py` and `src/mcp_gway/code_mode.py` — supports criterion 1 (zero hits for `executeToolCode`) and criterion 2 (canonical name `executeTool`).
  - Virtual stub commentary update in `src/mcp_gway/registry.py` and CLI docstring in `src/mcp_gway/cli.py` — supports criterion 1 and criterion 2.
  - Skill and plugin updates in `skills/`, `plugins/`, `.pi/extensions/`, and `rules/` — supports criterion 1 and criterion 2.
- Testing:
  - Updated test assertions in `tests/test_gateway.py`, `tests/test_edgecases_gateway.py`, `tests/test_call_many_meta.py`, `tests/test_antigravity_plugin.py`, `tests/test_observability_instrumentation.py`, `tests/test_p0_wave4_highs.py`, `tests/test_registry.py`, and `tests/pi_extension.test.mjs` — supports criterion 3 (100% tests pass).
- Product:
  - Updated documentation in `AGENTS.md`, `README.md`, `docs/code-mode.md`, `docs/architecture.md`, and `CHANGELOG.md` entry — supports criterion 2 and criterion 4 (`CHANGELOG.md` entry).

## Risks

- Downstream agent configs or client plugins calling `executeToolCode` directly fail with tool-not-found — Mitigation: Update all built-in rules, skills, and extensions in the same atomic commit. Severity: medium.
- Stale references remain in doc/spec files causing confusion — Mitigation: Run automated grep verification across all non-archived trees. Severity: low.

## Verification plan

- Criterion 1 (Zero hits for `executeToolCode` across `src/`, `skills/`, `plugins/`, `tests/`) → Verified via `git grep "executeToolCode"` by Testing.
- Criterion 2 (Canonical name `executeTool` exposed and documented) → Verified via `tools/list` inspection in tests and doc diff by Product.
- Criterion 3 (100% test pass rate) → Verified via `uv run pytest -v` by Testing.
- Criterion 4 (`CHANGELOG.md` documentation) → Verified via diff review of `CHANGELOG.md` by Product.

## Cross-domain dependencies

- Core dispatcher rename delivered before test suite updates. — Owner: Atlas (Engineering) — Due: 2026-10-06.
- Test suite updates delivered before final verify pass. — Owner: Atlas (Testing) — Due: 2026-10-06.
- Documentation and changelog aligned with new tool naming. — Owner: Atlas (Product) — Due: 2026-10-06.

## Assigned team

- Domain: Atlas (Engineering, Testing, Product) — execute implementation, update test suites, and maintain documentation.
- Process steward: Atlas (Process Steward) — confirm plan completeness and cross-domain dependency compliance.

## Gates

- Domain gate: Atlas (Engineering) — PASS
- Process gate: Atlas (Process Steward) — PASS
