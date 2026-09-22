# Proposed Changes: Transport Separation — feat/separate-mcp-transport

**Spec Reference:** SPEC-TRANSPORT-SEPARATION-001
**Agent:** engineering lane
**Date:** 2026-09-22
**Execution_Mode:** sequential degradation (same-thread, subagents full-wave)
**Domains-Touched:** [engineering]

## Summary

Separa `GET /mcp` (SSE) y `POST /mcp` (Streamable HTTP) en dos apps de rutas
mutuamente excluyentes, seleccionadas por `Gateway(registry, transport=...)`.
Antes ambos métodos coexistían en el mismo `Starlette` app y `serve --transport
http|sse` levantaba exactamente las mismas 7 rutas. Ahora el transporte decide
las rutas expuestas en `/mcp` y no hay fallback cruzado.

## Changes

| Target | Change Type | Description |
|--------|-------------|-------------|
| `src/mcp_gway/gateway.py` | file-modify | `Gateway.__init__(..., transport)` valida `http|sse`, construye `mcp_routes` exclusivos, handlers `_mcp_get_not_allowed` / `_mcp_post_not_allowed` (405 + `Allow`), expone `app.state.transport` |
| `src/mcp_gway/cli.py` | file-modify | `_serve_http(..., transport)` propaga el transporte al `Gateway` y al banner; help de `--transport` documenta las rutas por transporte |
| `tests/test_transport_separation.py` | file-create | Contrato REQ-TRANSPORT-001..004, 008 (rutas, 405+Allow, sin fallback, ValueError) |
| `tests/test_gateway.py` | file-modify | JSON-RPC via `POST /mcp` (http); cobertura de rutas por transporte |
| `tests/test_edgecases_gateway.py` | file-modify | Alias `/mcp/messages` y límites sobre gateway `sse` |
| `tests/test_gateway_sse_limits.py`, `tests/test_obsfeat007.py`, `tests/test_p0_round2_hardening.py` | file-modify | Escenarios SSE (`GET /mcp`) sobre gateway `transport="sse"` |
| `tests/test_serve_unified.py` | file-modify | Fakes con firma `+transport`; AC-05 reescrito: mismo entrypoint, app **separada** por transporte |
| `docs/specs/40_workspace/transport-separation/IMPLEMENTATION_PLAN.md` | file-create | Pasos, orden, rollback |
| `docs/specs/40_workspace/transport-separation/TEST_MATRIX.md` | file-create | Trazabilidad REQ → test → artifact |
| `AGENTS.md`, `README.md`, `docs/specs/10_design/API_CONTRACTS.md`, `docs/specs/10_design/ARCHITECTURE.md` | file-modify | Contrato público: rutas por transporte (ya no "7 Route entries compartidas") |

## Rationale

1. **Superficie mínima por proceso:** un gateway en modo http no debe servir un
   stream SSE que nadie pidió (y viceversa) — deny-by-default de rutas.
2. **Semántica 405 honesta:** el spec MCP permite 405 en `GET /mcp` cuando el
   server no ofrece stream; el `Allow` header le dice al cliente qué sí aplica.
3. **Elimina la ambigüedad de ADR-010 AC-05:** "comparten la app" era
   cierto a nivel de entrypoint (`_serve_http`), falso a nivel de superficie
   expuesta — ahora queda explícito en ambos niveles.

## Alternatives Considerated

| Alternative | Reason Rejected |
|-------------|-----------------|
| Mantener ambas rutas y filtrar por query param | Expone las dos superficies siempre; el gate depende de runtime, no de configuración |
| Default `transport="sse"` | Streamable HTTP es el transporte moderno del spec MCP; stdio (default de serve) no usa rutas HTTP |
| Un flag `--dual-transport` | Scope creep sin caso de uso; superficie x2 sin requerimiento |

## Approval Required From

- [x] Engineering owner: continuidad de la rama ya iniciada (diff previo en working tree)
- [ ] Architecture: cambio de contrato público de rutas → ADR-010 nota de enmienda en docs
