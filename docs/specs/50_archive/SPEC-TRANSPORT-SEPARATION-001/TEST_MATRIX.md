# TEST MATRIX: SPEC-TRANSPORT-SEPARATION-001

**Date:** 2026-09-22
**Baseline:** 548 passed / 14 failed (contrato viejo en suite)
**Target:** 0 failed + tests nuevos de contrato

## Requirements

| REQ-ID | Requirement | Priority |
|--------|-------------|----------|
| REQ-TRANSPORT-001 | `Gateway(transport)` acepta solo `http`\|`sse`; otro valor → `ValueError` en construcción | P0 |
| REQ-TRANSPORT-002 | `transport="http"`: `POST /mcp` sirve JSON-RPC; `GET /mcp` → 405 + `Allow: POST`; `/mcp/messages` → 404 | P0 |
| REQ-TRANSPORT-003 | `transport="sse"`: `GET /mcp` → stream SSE; `POST /mcp` → 405 + `Allow: GET`; `POST /mcp/messages` sirve JSON-RPC | P0 |
| REQ-TRANSPORT-004 | Sin fallback cruzado entre transportes (superficie mutuamente excluyente) | P0 |
| REQ-TRANSPORT-005 | `serve --transport http\|sse` propaga transporte al `Gateway` y al banner; help documenta rutas | P1 |
| REQ-TRANSPORT-006 | Probes compartidos intactos: `/health`, `/ready`, `/live`, `/metrics` + CSP en ambos transportes | P1 |
| REQ-TRANSPORT-007 | `serve --transport stdio` (default) no depende de rutas HTTP; loop NDJSON sin cambio | P1 |
| REQ-TRANSPORT-008 | `app.state.transport` expuesto para observability/tests | P2 |

## Traceability: REQ → Test → Artifact

| REQ-ID | Test | Artifact |
|--------|------|----------|
| REQ-TRANSPORT-001 | `tests/test_transport_separation.py::test_unknown_transport_rejected` | `src/mcp_gway/gateway.py:Gateway.__init__` |
| REQ-TRANSPORT-002 | `tests/test_transport_separation.py::test_http_routes_and_post_works`, `::test_http_get_not_allowed`, `::test_http_messages_404` | `src/mcp_gway/gateway.py:mcp_routes (http)` |
| REQ-TRANSPORT-003 | `tests/test_transport_separation.py::test_sse_routes_and_messages_works`, `::test_sse_post_not_allowed`, `::test_sse_stream_route` | `src/mcp_gway/gateway.py:mcp_routes (sse)` |
| REQ-TRANSPORT-004 | `tests/test_transport_separation.py::test_no_cross_transport_fallback` | `src/mcp_gway/gateway.py:_mcp_*_not_allowed` |
| REQ-TRANSPORT-005 | `tests/test_serve_unified.py::test_serve_unified_transport_option_gate`, `::test_serve_unified_http_sse_distinct_routes` | `src/mcp_gway/cli.py:_serve_http` |
| REQ-TRANSPORT-006 | `tests/test_edgecases_gateway.py::test_live_paths_health_ready_live_metrics`, `tests/test_wave2_api.py::test_csp_header` | `src/mcp_gway/gateway.py:routes base` |
| REQ-TRANSPORT-007 | `tests/test_stdio.py` (suite completa) | `src/mcp_gway/cli.py:_serve_stdio` |
| REQ-TRANSPORT-008 | `tests/test_transport_separation.py::test_app_state_transport` | `src/mcp_gway/gateway.py:app.state.transport` |

## Migración de tests del contrato viejo (14 FAIL baseline)

| Test | Contrato viejo | Contrato nuevo |
|------|----------------|----------------|
| `test_gateway.py::test_initialize/test_tools_list/test_tools_call_*/test_unknown_method/test_execute_code_with_server_struct_via_gateway` | `POST /mcp/messages` sobre app dual | `POST /mcp` sobre gateway http |
| `test_gateway.py::test_sse_endpoint` | asume 7 rutas fijas | aserción por transporte (movido a test_transport_separation) |
| `test_edgecases_gateway.py::test_mcp_post_session_not_found/test_mcp_post_alias_and_limits` | `/mcp/messages` + límites en app dual | gateway `sse` (alias) + gateway `http` (límites `POST /mcp`) |
| `test_gateway_sse_limits.py::test_create_session_full_returns_429` | `GET /mcp` en app dual | gateway `sse` |
| `test_obsfeat007.py::test_ac005_sse_disconnect_counted` | `GET /mcp` en app dual | gateway `sse` |
| `test_p0_round2_hardening.py::test_round2_concurrent_129_returns_429` | `GET /mcp` en app dual | gateway `sse` |
| `test_serve_unified.py::test_serve_unified_transport_option_gate` | fake `_serve_http` sin `transport` | firma `+transport` |
| `test_serve_unified.py::test_serve_unified_http_sse_same_app` | AC-05 "misma app" (ADR-010) | reescrito: mismo entrypoint, rutas separadas por transporte |

## Quality Gates

- [x] `uv run ruff check src/ tests/` clean
- [x] `uv run ruff format --check src/ tests/` clean
- [x] `uv run pytest -q` → 570 passed, 0 failed
- [x] Sin PII/secrets en el diff (diff: rutas, tests, docs — sin credenciales)

## Notes

- REQ-005 gap menor (según subagente de tests): banner/help no tienen aserción
  explícita de transporte — el help sí lo documenta vía `--transport` choice y la
  propagación está cubierta por `test_serve_unified_transport_option_gate`;
  aceptado como suficiente para P1.
