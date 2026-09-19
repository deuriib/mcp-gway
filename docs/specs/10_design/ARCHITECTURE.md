# Architecture Contract: Professional Performance Audit — MCP Gateway

**Owner:** vasquez (CTO)
**Version:** v2
**Last Updated:** 2026-09-19
**Domains-Touched:** [engineering]

## Overview (v2 delta — SPEC-ANTIGRAVITY-001)

Antigravity IDE plugin parity subsystem: declarative bundle `plugins/antigravity/`
(`plugin.json` + `mcp_config.json` + `hooks.json` + `skills/mcp-gway/SKILL.md` +
`rules/*.md` + `INSTALL.md`) mirroring `plugins/opencode/mcp-gateway.ts` behavior through
native Antigravity surfaces — `rules/` for persistent guidance, `PreInvocation` hook
reinject with MARKER dedupe for compression survival, `mcp_config.json` remote `serverUrl`
for gateway registration. No gateway/CLI/transport change; additive bundle only.

## Overview

Auditoría de performance local-first para MCP Gateway v2.2.0 (CLI-only, headless, Code Mode + sandbox Starlark). Mide 5 paths vivos HTTP/SSE, overhead Code Mode/sandbox, recursos en 3 transportes, y produce SLO draft + runbook reproducible sin romper 255 tests ni seguridad.

Principio: medir con excelencia y dedicación; optimizar solo con datos.

## Components

| Component | Responsibility | Interface |
|-----------|---------------|-----------|
| `bench_perf.py` (nuevo, `docs/specs/30_delivery/`) | Orquesta carga concurrente contra 5 paths, perfila Code Mode/sandbox, mide recursos | CLI: `--target-url`, `--concurrency`, `--duration`, `--warmup`, `--output`; salida JSON + MD |
| `src/mcp_gateway/gateway.py` | HTTP/SSE server (Starlette + uvicorn): 7 Route entries, `/mcp` GET+POST, `/health`, `/ready`, `/live`, `/metrics` | ASGI app; `_mcp_post` handler único para POST `/mcp` y `/mcp/messages` |
| `src/mcp_gateway/code_mode.py` | 4 meta-tools orchestrator: `listToolFiles`, `readToolFile`, `getToolDocs`, `executeToolCode` | Starlark sandbox via `sandbox.py`; `Server.tool_name(param=value)` |
| `src/mcp_gateway/sandbox.py` | Starlark sandbox hermético (L1-L4 validation, timeout, ACL) | `execute(code: str) -> {"result": ..., "logs": [...]}` |
| `src/mcp_gateway/core/client.py` | `create_client_transport`, `discover_tools`, `refresh_server` | Auto-detección transporte: streamable-http → sse → http |
| `src/mcp_gateway/observability/metrics.py` | `MetricsRegistry` hand-rolled Prometheus (counter/gauge/histogram) | `/metrics` exposition; `X-Warning: exposed` gating |
| `src/mcp_gateway/observability/health.py` | `/health`, `/ready`, `/live`, `/metrics` probes | `GET` endpoints; `X-Warning` solo en `/metrics` |

## Data Flow

1. **Benchmark HTTP/SSE**: `bench_perf.py` → `httpx2` (dependencia directa, alineada con mcp v2 + starlette 1.6) → `gateway.py` routes → handlers → `MetricsRegistry` → `/metrics` exposition
2. **Benchmark Code Mode**: `bench_perf.py` → `core/client.py:discover_tools()` → `core/transport.py` auto-detect → `server_proxy.py` → `sandbox.py` → Starlark execution → result
3. **Benchmark Resources**: `bench_perf.py` → `psutil`/`tracemalloc`/`time` → `serve` subprocess (stdio|http|sse) → CPU/mem/startup samples
4. **Metrics Collection**: `MetricsRegistry` accumula counters/histograms → `/metrics` GET → Prometheus text format

## Invariants

- INV-001: `serve --host 127.0.0.1` por defecto; `0.0.0.0` exige `MCP_GWAY_ALLOW_REMOTE=1` o `exit 2` (local-first security)
- INV-002: `MCP_GWAY_ALLOW_LOCAL_COMMANDS` / `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL` no se renombran (feat-006 policy)
- INV-003: Sin secretos/tokens/creds en código/config/logs/ejemplos/eventos (guardrails 1, 5)
- INV-004: Hallazgo sin prueba (diff/scan/log) = REFUTED (guardrails 9)
- INV-005: 255 tests verdes + `ruff check` + `ruff format --check` en todo momento (Definition of Done)
- INV-006: `X-Warning: exposed` solo en `GET /metrics` → `403` cuando expuesto sin opt-in (observability/health.py:127-139)

## Plugin Subsystem (v2 — SPEC-ANTIGRAVITY-001)

| Component | Responsibility | Interface |
|-----------|---------------|-----------|
| `plugins/antigravity/plugin.json` | Plugin manifest (`mcp-gateway`, `$schema`) | Antigravity plugin loader; workspace `.agents/plugins/` or global `~/.gemini/config/plugins/` |
| `plugins/antigravity/rules/*.md` | Persistent Gateway Protocol card (mandatory order, Starlark convention, anti-patterns) | Always-on/glob/model-decision rules surface; MARKER `MCP-GWAY v2.8.0` verbatim |
| `plugins/antigravity/hooks.json` + reinject script | `PreInvocation`/`PostInvocation` reinject with MARKER dedupe (≡ `systemHasRules`/`pushRules`) | stdin JSON → stdout `{injectSteps: [{ephemeralMessage}]}` or `{injectSteps: []}` |
| `plugins/antigravity/skills/mcp-gway/SKILL.md` | Skill body parity with `skills/mcp-gway/SKILL.md` | name+description frontmatter auto-load |
| `plugins/antigravity/mcp_config.json` | Gateway remote registration (`serverUrl: http://127.0.0.1:8080/mcp`, secret-free) | Antigravity MCP surface (`mcpServers.gateway`) |
| `plugins/antigravity/INSTALL.md` | Install + verify matrix + rollback (parity with `plugins/opencode/INSTALL.md`) | Docs |

Data flow: session start → rules inject card (dedupe by MARKER) → pre-model invocation →
reinject script greps `transcriptPath` for MARKER → injects `ephemeralMessage` only if
absent → agent calls gateway tools in mandatory order via `mcp_config.json` registration.

Invariants (v2 additions):

- INV-007: `plugins/antigravity/` is additive-only; `src/`, gateway routes, CLI frozen
- INV-008: No secret/token/credential in the bundle; `headers.Authorization` is a manual
  user-side edit only, never committed (guardrail 1)
- INV-009: MARKER `MCP-GWAY v2.8.0` verbatim; card substance ≡ OpenCode MCP_RULES
- INV-010: `serverUrl` defaults to loopback; non-loopback follows local-first opt-in

## Non-Functional Requirements

- Performance: p99 `/mcp` POST local medido (hipótesis <150ms a validar, no compromiso); top-5 costos rankeados con traza
- Availability: `/health`, `/ready`, `/live` p99 < 50ms local (baseline a medir)
- Security: Deny default; least privilege por interfaz; `barrera` review condicional si nuevos endpoints/payloads/fronteras
- Observability: `/metrics` Prometheus hand-rolled expuesto; runbook reproducible versionado
- Reproducibilidad: Script único, máquina sagrada documentada, versión git, carga configurada, comandos exactos