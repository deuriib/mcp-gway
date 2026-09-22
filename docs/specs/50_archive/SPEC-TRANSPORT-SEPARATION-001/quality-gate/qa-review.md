# QA REVIEW — SPEC-TRANSPORT-SEPARATION-001

**Reviewer domain:** Quality Assurance (test adequacy + verification evidence)
**Date:** 2026-09-22
**Scope:** commit `bd2d11a` (tests) + `88f47fd` (src)
**Packet:** `docs/specs/50_archive/SPEC-TRANSPORT-SEPARATION-001/{PROPOSED_CHANGES,IMPLEMENTATION_PLAN,TEST_MATRIX}.md` (reference-only, untouched)

## Verdict: **APPROVE**

All gates green, every REQ in TEST_MATRIX traces to an existing test that
passes, migration off the dual-app contract is complete. Findings are Medium
or lower — none blocks release; M-1/M-2/M-3 are recorded as residual risk for
the orchestrator to accept or ticket.

---

## 1. Gate outputs (run by this reviewer)

```
$ uv run ruff check src/ tests/
[]
(exit 0)

$ uv run ruff format --check src/ tests/
74 files already formatted
(exit 0)

$ uv run pytest -q
570 passed in 7.08s
(exit 0)

$ uv run pytest tests/test_transport_separation.py -v
...
tests/test_transport_separation.py::test_unknown_transport_rejected PASSED
tests/test_transport_separation.py::test_http_routes_and_post_works PASSED
tests/test_transport_separation.py::test_http_get_not_allowed PASSED
tests/test_transport_separation.py::test_http_messages_404 PASSED
tests/test_transport_separation.py::test_sse_routes_and_messages_works PASSED
tests/test_transport_separation.py::test_sse_post_not_allowed PASSED
tests/test_transport_separation.py::test_sse_stream_route PASSED
tests/test_transport_separation.py::test_no_cross_transport_fallback PASSED
tests/test_transport_separation.py::test_app_state_transport PASSED
============================== 9 passed in 0.16s ===============================
(exit 0)
```

Matrix-claimed target `570 passed, 0 failed` reproduced exactly.

## 2. REQ coverage table

Every test listed in TEST_MATRIX.md `Traceability` was confirmed to **exist**
and **pass** (full run green). Assertion quality noted per REQ.

| REQ-ID | Test(s) | Exists | Passes | Assertion quality | Status |
|---|---|---|---|---|---|
| REQ-TRANSPORT-001 | `test_transport_separation.py::test_unknown_transport_rejected` | ✅ | ✅ | `pytest.raises(ValueError)` over 4 bad values incl. `stdio` — behavioral | Covered |
| REQ-TRANSPORT-002 | `::test_http_routes_and_post_works`, `::test_http_get_not_allowed`, `::test_http_messages_404` | ✅ | ✅ | Real status codes (200 / 405 / 404) + real `Allow: POST` header + tool payload check | Covered (strong) |
| REQ-TRANSPORT-003 | `::test_sse_routes_and_messages_works`, `::test_sse_post_not_allowed`, `::test_sse_stream_route` | ✅ | ✅ | First two behavioral (200 + `Allow: GET` 405). `test_sse_stream_route` is **route introspection only** (`endpoint.__name__ == "_mcp_sse"`, no request) | Covered, **stream leg introspection-only in contract file → M-1** |
| REQ-TRANSPORT-004 | `::test_no_cross_transport_fallback` | ✅ | ✅ | Mixed: surface set + 4 real request/response pairs (405/`Allow`, 404 vs 200) | Covered (strong) |
| REQ-TRANSPORT-005 | `test_serve_unified.py::test_serve_unified_transport_option_gate`, `::test_serve_unified_http_sse_distinct_routes` | ✅ | ✅ | CliRunner behavioral (exit 2 gates, `called == {...transport: "http"}`, `calls == ["http","sse"]`) + `inspect.getsource` introspection; **banner/help-routes leg has no assertion** | Covered, banner leg gap **accepted in TEST_MATRIX notes → M-3** |
| REQ-TRANSPORT-006 | `test_edgecases_gateway.py::test_live_paths_health_ready_live_metrics`, `test_wave2_api.py::test_csp_header` | ✅ | ✅ | Real GETs, status + CSP header asserts — but both build the **default (http)** gateway; sse-side probes untested | Covered, single-transport **→ L-1** |
| REQ-TRANSPORT-007 | `tests/test_stdio.py` (31 tests) | ✅ | ✅ | Full NDJSON loop suite, no HTTP dependency | Covered |
| REQ-TRANSPORT-008 | `::test_app_state_transport` | ✅ | ✅ | Direct `app.state.transport` assert for both transports | Covered |

## 3. Findings

### M-1 — REQ-TRANSPORT-003 "GET /mcp → SSE stream" covered only by introspection inside the contract suite (Medium)
`tests/test_transport_separation.py:98-113` asserts the route table, never
issues a GET. Behavioral 200-SSE coverage exists outside the contract file
(`tests/test_obsfeat007.py:265`, `tests/test_gateway_sse_limits.py:48`) but
neither carries the REQ-ID, so the REQ trace points at an introspection test.
Mitigating: the endpoint-name assert pins `_mcp_sse`, and consuming the stream
in the contract test would reintroduce the hang risk the test deliberately
avoids (docstring lines 101-103). Recommend: cross-reference obsfeat007 in the
matrix artifact column, or tag one behavioral SSE test with the REQ-ID.

### M-2 — Hang risk: unbounded SSE read in migrated limit test (Medium)
`tests/test_p0_round2_hardening.py:104` — `tasks = [client.get("/mcp") for _ in range(5)]`
on a session-full gateway with **no `asyncio.wait_for`**. If the 429
enforcement ever regresses, each `client.get` opens the infinite SSE stream and
the suite hangs forever instead of failing. Its sibling
`tests/test_gateway_sse_limits.py:48` does it correctly (`asyncio.wait_for(..., timeout=3.0)`
+ `pytest.fail("RED: /mcp hung...")`). Bounded-timeout wrapper should be added
to the round2 test (test-only change, out of scope for this gate's no-touch rule).

### M-3 — REQ-005 banner/help-routes leg unasserted (Medium, documented)
No test asserts the serve banner prints the selected transport or that
`--help` documents the per-transport routes. `test_serve_unified.py:18-21`
only checks `--transport`/`stdio` appear in help. TEST_MATRIX.md:55-58 already
records this as accepted for P1. Residual, accepted — no action required.

### L-1 — REQ-006 "CSP + probes en ambos transportes" tested on http only (Low)
`test_live_paths_health_ready_live_metrics` and `test_csp_header` both build
`Gateway(...)` with the default `transport="http"`. The sse app never has
`/health`/`/metrics`/CSP asserted directly. Risk is low because probes live in
the shared base-route list (only `mcp_routes` differ per
`gateway.py:320-340`) and the sse app is constructed in 6 test files.

### L-2 — Sleep-based timing, all bounded (Low, no action)
- `tests/test_obsfeat007.py:271,299` — poll loops `time.sleep(0.02)` ×100
  (≤2s cap) after `MAX_IDLE_SECONDS=0.05` monkeypatch; bounded, not fixed-order.
- `tests/test_gateway_sse_limits.py:48` — `wait_for(timeout=3.0)` then explicit
  fail; correct anti-hang pattern.
- `tests/test_gateway.py:154` — `asyncio.sleep(0.05)` to prove last_activity
  advances; low flake risk (monotonic delta, not wall-clock equality).
- Contract file `tests/test_transport_separation.py`: **zero** sleeps, zero
  stream consumption, no ordering dependencies — deterministic.

## 4. Migration completeness (dual-app contract leftovers)

`grep -rn "/mcp/messages" tests/` — 13 hits, all accounted for:

| Location | Builds transport? | Verdict |
|---|---|---|
| `test_edgecases_gateway.py:250` | `_gw(tmp_path, transport="sse")` (line 247) | ✅ sse |
| `test_edgecases_gateway.py:260` | `alias_gw = _gw(..., transport="sse")` (line 257) | ✅ sse |
| `test_transport_separation.py:76` | http gateway, asserts **404** (negative case) | ✅ intentional |
| `test_transport_separation.py:84,128,129,137,138` | explicit http-404 / sse-200 pairing | ✅ intentional |
| `test_edgecases_observability.py:128`, `test_observability_probes.py:98` | pure `path_template()` string asserts, no gateway | ✅ no dual-app assumption |

`grep -rn 'get("/mcp")' tests/` — 4 hits:

| Location | Transport | Verdict |
|---|---|---|
| `test_transport_separation.py:66` | http, expects 405 (negative) | ✅ intentional |
| `test_transport_separation.py:133` | http, expects 405 (negative) | ✅ intentional |
| `test_gateway_sse_limits.py:48` | `Gateway(reg, transport="sse")` (line 36) | ✅ sse |
| `test_p0_round2_hardening.py:104` | `Gateway(reg, transport="sse")` (line 92) | ✅ sse (but see M-2) |

Plus `test_obsfeat007.py:265` `c.stream("GET", "/mcp")` builds
`transport="sse"` (line 262) ✅.
No test in the repo still assumes the dual-app contract.

## 5. 80% floor on critical paths

- **http 405 handler** (`GET /mcp → 405 Allow: POST`): hit by
  `test_http_get_not_allowed` (line 66) **and** `test_no_cross_transport_fallback`
  (line 133). ✅
- **sse 405 handler** (`POST /mcp → 405 Allow: GET`): hit by
  `test_sse_post_not_allowed` (line 93) **and** `test_no_cross_transport_fallback`
  (line 135). ✅
- **http route list**: computed + asserted (no `/mcp/messages` pair) in
  `test_no_cross_transport_fallback:129`, behaviorally in
  `test_http_messages_404`. ✅ (≥1 test)
- **sse route list**: exact single `GET /mcp → _mcp_sse` assert in
  `test_sse_stream_route:112-113` + `("/mcp/messages","POST")` membership in
  `test_no_cross_transport_fallback:128`. ✅ (≥1 test)

All four critical surfaces have at least one direct test. Floor met.

---

**Verdict: APPROVE** — gates green (570/0, ruff clean, format clean),
full REQ trace verified, migration complete. Residual: M-1 (trace label
quality), M-2 (hang-on-regression in one migrated test), M-3 (accepted),
L-1/L-2 (observation only).
