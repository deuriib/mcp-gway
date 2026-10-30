# FRAME — hexagonal-architecture-migration

## Goal

Migrate mcp-gway to a hexagonal architecture (ports and adapters) by decoupling core business logic from transport (HTTP/SSE/stdio) and persistence/external systems, establishing a pure domain layer with zero framework dependencies to guarantee isolated unit testability and extensible adapter integration.

## Success criteria (measurable)

- [ ] Zero import dependencies on `fastapi`, `starlette`, or `mcp` transport libraries within `src/mcp_gway/domain/` (verified via AST / import analysis script).
- [ ] All external I/O (filesystem registry, network MCP clients, OAuth token storage) accessed strictly via domain port protocols.
- [ ] Core business logic and use cases testable via pure unit tests with in-memory port implementations, requiring zero network sockets or running HTTP servers.
- [ ] Package structure organized into explicit hexagonal layers: `domain/` (entities, value objects, ports), `application/` (use cases, service orchestration), and `infrastructure/` (transports, adapters, HTTP/SSE, registry persistence).
- [ ] 100% of existing test suite (680 tests) passes with zero regression (`mise run test`).

## Scope

- In: defining pure domain models and port protocols; creating application use cases for gateway operations, server management, and code mode; refactoring transport and storage into infrastructure adapters; establishing explicit dependency injection wiring; backward-compatible facade/entry-points for existing imports and CLI.
- Out: complete rewrite of all existing tests (tests updated/extended incrementally without breaking existing coverage); new protocol features or external transport protocols not present in current version.

## Domain profile

- Domains involved: Engineering, Testing
- Deliverable type: code
- Optional phases: research? no — measure? no

## Constraints

- Python 3.12+ strict typing (`from __future__ import annotations`, no `Any`, full type hints).
- Existing CLI commands (`mcp-gway`, `mgw`) and CLI flags must maintain 100% backward compatibility.
- Zero external architectural dependencies introduced (pure Python stdio/protocols for domain).
- All changes must pass `mise run ci` (ruff check, ruff format, and pytest suite).

## Assigned team

- Domain: Software Architect (Engineering) — designs clean hexagonal domain boundaries, port protocols, and package hierarchy.
- Domain: Backend Engineer (Engineering) — implements domain entities, application use-case interactors, and infrastructure adapters.
- Domain: Test Engineer (Testing) — verifies unit test isolation without I/O and maintains full regression test coverage.
- Process steward: Senior Project Manager — enforces Agency-Flow discipline, validates gate criteria, and manages subagent work orchestration.

## Gates

- Domain gate: Software Architect — PASS
- Process gate: Senior Project Manager — PASS (staffing feasible, scope bounded, all criteria verifiable)
