# SHIP — hexagonal-architecture-migration

## Release notes (user-facing)

mcp-gway now features a clean Hexagonal Architecture (Ports and Adapters). Core business models, server policies, and interface protocols are fully decoupled from transport mechanics and web frameworks. This ensures faster, hermetic unit testing without starting servers or opening network sockets, while maintaining 100% backward compatibility for all existing CLI commands and integration workflows.

## Version / tag

4.11.0

## Changelog

- refactor(domain): extract pure domain entities, models, and policy rules into `src/mcp_gway/domain/`.
- feat(ports): declare abstract domain ports for registry, sandbox execution, MCP proxies, token storage, and command policy.
- feat(application): introduce application use cases (`ManageServersUseCase`, `ExecuteCodeUseCase`, `ProxyToolCallUseCase`, `GatewayStatusUseCase`).
- feat(infrastructure): implement filesystem, Starlark sandbox, token storage, and policy adapters with explicit DI container in `src/mcp_gway/infrastructure/`.
- test(architecture): add AST boundary verification test guaranteeing zero framework or transport dependencies in domain layer.
- test(unit): add pure in-memory test suite verifying use cases in isolation without network or disk I/O.
- refactor(core): maintain 100% backward-compatibility facade in `src/mcp_gway/core/policy.py`.

## References

- FRAME: `00-frame.md`
- PROPOSE: `01-propose.md`
- BUILD: `02-build.md`
- VERIFY: `03-verify.md` (verdict: PASS)

## Follow-ups carried from VERIFY

None.

## Assigned team

- Domain: Backend Architect (Engineering) — verified clean architectural layers, compatibility facade, and release readiness.
- Process steward: Senior Project Manager — confirmed release notes, artifact changelog alignment, and two-gate lifecycle completion.

## Gates

- Domain gate: N/A — passed at VERIFY
- Process gate: Senior Project Manager — PASS
