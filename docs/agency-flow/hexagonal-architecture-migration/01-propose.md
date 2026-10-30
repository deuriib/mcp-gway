# PROPOSE — hexagonal-architecture-migration

## Approach

Implement a hexagonal architecture (ports and adapters) following an incremental Strangler pattern that decouples domain models, policies, and port protocols from transport and I/O infrastructure. Application use cases will orchestrate domain operations through pure interfaces, wired via an explicit Dependency Injection container, while maintaining backwards-compatible facades at top-level modules. The rejected alternative was an immediate big-bang replacement and rename of all existing modules and test fixtures; this was rejected because it would invalidate 680 existing tests simultaneously, risk high regression in CLI and admin flows, and violate ENG-15 (Strangler Fig over big-bang rewrites).

## Planned deliverables (grouped by domain)

- Engineering:
  - `src/mcp_gway/domain/` — pure domain models, policies, and port protocols with zero framework dependencies — supports criterion 1 (pure domain layer) and criterion 2 (port interfaces).
  - `src/mcp_gway/application/` — use cases for server management, code execution, and proxy routing — supports criterion 2 (I/O via ports) and criterion 4 (hexagonal layers).
  - `src/mcp_gway/infrastructure/` — adapters for filesystem registry, Starlark sandbox, MCP client proxies, Starlette HTTP/SSE transports, and DI container — supports criterion 4 (hexagonal layers) and criterion 5 (existing test compatibility).
  - Top-level backward compatibility facade re-exports in `mcp_gway.registry`, `mcp_gway.gateway`, `mcp_gway.models`, `mcp_gway.code_mode` — supports criterion 5 (zero regressions).
- Testing:
  - Isolated domain unit test suite `tests/unit/test_domain_hexagonal.py` verifying business logic and use cases with in-memory port stubs without I/O or HTTP servers — supports criterion 3 (isolated unit testability).
  - Architectural AST verification script/test `tests/architecture/test_hexagonal_boundaries.py` enforcing zero imports of `fastapi`, `starlette`, or `mcp` inside `domain/` — supports criterion 1 (pure domain layer).
  - Full regression execution validating all 680 existing tests pass — supports criterion 5 (zero regressions).

## Risks

- Facade delegation circular imports — resolve via strict downward import directions (Infrastructure -> Application -> Domain) and explicit DI container wiring. Severity: medium.
- Runtime type-checking breaks or pydantic serialization differences — retain exact Pydantic V2 schemas and validator logic within domain models. Severity: low.
- Performance overhead from additional abstraction layers — protocol dispatch in Python is zero-overhead via standard typing protocols or lightweight classes. Severity: low.

## Verification plan

- Criterion 1 (pure domain layer) → AST import analyzer test `test_hexagonal_boundaries.py`, verified by Testing.
- Criterion 2 (port interfaces for all I/O) → Interface compliance test validating adapters against Domain Protocols, verified by Engineering.
- Criterion 3 (isolated unit testability) → In-memory mock unit tests in `test_domain_hexagonal.py` executing use cases with zero sockets/disk, verified by Testing.
- Criterion 4 (hexagonal layer folder structure) → Verification of `domain/`, `application/`, `infrastructure/` package structure and clean exports, verified by Engineering.
- Criterion 5 (zero test regressions) → Complete `mise run test` suite execution (all 680 existing tests passing), verified by Testing.

## Cross-domain dependencies

- Engineering provides domain port protocols before Testing completes in-memory mocks. — Owner: Backend Engineer. — Due: 2026-10-30.
- Engineering completes infrastructure adapters before Testing runs full regression suite. — Owner: Backend Engineer. — Due: 2026-10-30.
- Testing provides boundary AST verification test to enforce architectural constraints. — Owner: Test Engineer. — Due: 2026-10-30.

## Assigned team

- Domain: Backend Engineer (Engineering) — develops domain layers, ports, application interactors, infrastructure adapters, and facades.
- Domain: Test Engineer (Testing) — builds isolated in-memory unit tests, AST boundary tests, and executes regression verification.
- Process steward: Senior Project Manager — verifies dependency formats, criterion coverage, and task gating.

## Gates

- Domain gate: Backend Engineer — PASS
- Process gate: Senior Project Manager — PASS (all criteria mapped, dependencies formatted with owners and dates, rejected alternative documented)
