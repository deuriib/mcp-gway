# Implementation Plan: SPEC-TRANSPORT-SEPARATION-001

**Agent:** Engineering Specialist
**Date:** 2026-09-22
**Approved By:** engineering owner (continuidad de rama feat/separate-mcp-transport)
**Execution Mode:** sequential degradation (same-thread per contract)
**Domains-Touched:** [engineering]

## Steps

| Step | Description | Target / Files | Evidence Location | Est. Effort |
|------|-------------|----------------|-------------------|-------------|
| 1 | Congelar contrato: `Gateway(transport)` valida `http\|sse`, rutas exclusivas, 405+`Allow`, `app.state.transport` (ya en working tree, verificar sin regresiones) | `src/mcp_gway/gateway.py` | `tests/test_transport_separation.py` | 0.5h |
| 2 | Propagar transporte desde CLI (`_serve_http(..., transport)`, banner, help) | `src/mcp_gway/cli.py` | `tests/test_serve_unified.py` | 0.25h |
| 3 | Migrar tests del contrato viejo: JSON-RPC → `POST /mcp` (http); alias `/mcp/messages`, SSE stream y límites 429 → gateway `transport="sse"` | `tests/test_gateway.py`, `tests/test_edgecases_gateway.py`, `tests/test_gateway_sse_limits.py`, `tests/test_obsfeat007.py`, `tests/test_p0_round2_hardening.py` | `uv run pytest -q` (14 FAIL actuales → 0) | 1h |
| 4 | Reescribir AC-05 de `test_serve_unified` (mismo entrypoint, app separada por transporte) + fakes con firma `+transport` | `tests/test_serve_unified.py` | `tests/test_serve_unified.py::test_serve_unified_http_sse_distinct_routes` | 0.25h |
| 5 | Actualizar contrato público (rutas por transporte, enmienda ADR-010) | `AGENTS.md`, `README.md`, `docs/specs/10_design/API_CONTRACTS.md`, `docs/specs/10_design/ARCHITECTURE.md` | diff docs + grep sin "comparten la app" | 0.5h |
| 6 | Quality checks + TEST_MATRIX | `tests/`, `docs/specs/40_workspace/transport-separation/TEST_MATRIX.md` | `ruff check` + `ruff format --check` + `pytest -q` | 0.25h |

## Order of Operations

1. Steps 1-2 (src) ya estabilizados en el working tree: son la fuente de verdad.
2. Step 3 primero en `test_gateway.py` (mayor volumen de rojos), luego edgecases y SSE.
3. Step 4 desbloquea la equivalencia CLI (http|sse pasan `transport`).
4. Step 5 solo después de que la suite esté verde (docs reflejan código real, no intención).
5. Step 6 cierra con evidencia.

## Rollback Points

- `git checkout HEAD -- src/mcp_gway/gateway.py src/mcp_gway/cli.py` revierte el contrato (punto de no retorno: paso 5, solo docs).
- Commits atómicos por step → revert individual por hash.
- Rama feature: ningún push a main sin gate.

## Quality Gates

- [x] Engineering: `uv run ruff check src/ tests/` clean
- [x] Engineering: `uv run ruff format --check src/ tests/` clean
- [x] Engineering: `uv run pytest -q` → 570 passed, 0 failed (desde 14 FAIL baseline)
- [x] Contract: `test_transport_separation.py` cubre REQ-TRANSPORT-001..004, 008
