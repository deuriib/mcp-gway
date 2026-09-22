# Quality Gate Review — RELIABILITY — SPEC-TRANSPORT-SEPARATION-001

**Reviewer:** Reliability domain reviewer (frame-ship quality gate)
**Date:** 2026-09-22
**Scope:** commits `88f47fd` (src), `bd2d11a` (tests), `dedf480` (docs)
**Domain:** correctness, error handling, failure modes, edge cases, test-proves-behavior.
Out of scope: readability style, risk policy (other domain owners).

## Verdict: APPROVE

No Critical/High/Medium findings. Three Low observations logged below with evidence;
none blocks the gate.

## Suite evidence

`uv run pytest -q` → **570 passed, 0 failed** (matches `TEST_MATRIX.md:50` claim;
baseline was 548 passed / 14 failed per `TEST_MATRIX.md:4`).

## Findings

### F-1 (Low) — Starlette's automatic 405 uses a different `Allow` value than the custom handler for non-GET/POST methods

- Evidence (empirical, starlette 1.6.0 installed):
  - `DELETE /mcp` on `transport="sse"` → `405` with `Allow: HEAD, GET`
    (Starlette partial-route fallback, first route `methods={"GET"}` auto-extended with `HEAD`),
    while the contract handler for `POST /mcp` returns `Allow: GET` (`gateway.py:530-538`).
  - `DELETE`/`OPTIONS /mcp` on `transport="http"` → `405 Allow: POST` (from the POST route partial).
- Why not blocking: the spec contract (`TEST_MATRIX.md:12-13`) only defines GET/POST
  behavior; those are both FULL-matched by the custom handlers and return the exact
  contracted values (`Allow: POST` / `Allow: GET`, verified empirically). The
  inconsistency is between two *unspecified* code paths (`HEAD, GET` vs `GET`) on
  methods no MCP client sends. No test asserts on it, so no test is at risk.
- Path out (optional, non-blocking): normalize by routing all non-contracted methods
  through the custom handlers, or accept as-is and document.

### F-2 (Low) — `_serve_stdio` constructs an `http`-routed Gateway it never serves

- Evidence: `cli.py:421` `gateway = Gateway(registry)` uses the default
  `transport="http"` (`gateway.py:172`); the stdio path only uses
  `gateway._handle_method` / `gateway._handle_post` / `gateway.metrics`
  (`stdio.py:120,138`) and never `gateway.app` or any route.
- Why not blocking: no functional dependence on HTTP routes — REQ-TRANSPORT-007 holds
  (full `tests/test_stdio.py` suite green; NDJSON loop untouched by this change).
  The route table is built and discarded: dead construction, not a failure mode.
  A future `transport="stdio"` Gateway value would break `__init__` validation
  (`gateway.py:181`), so the implicit default here is load-bearing — worth a comment
  someday, not a gate item.

### F-3 (Low) — SSE-mode `POST /mcp` 405 responds without reading the request body

- Evidence: `_mcp_post_not_allowed` (`gateway.py:530-538`) returns `JSONResponse`
  without consuming `request.stream()`; contract test sends a body
  (`tests/test_transport_separation.py:93` `c.post("/mcp", json=_PING)`).
- Why not blocking: TestClient (ASGI, no socket) always passes; under real
  HTTP/1.1 the client receives the complete 405 + `Allow: GET` response, after which
  the server may close the connection due to the unread body — standard-compliant and
  harmless for JSON-RPC-sized payloads. Not covered by any test (TestClient has no
  socket semantics), so it is an *untested-on-real-socket* edge, not a demonstrated
  defect. Under `transport="http"` this path never triggers (POST is fully handled).
  Logged for the record; a real-socket smoke test would close it.

### Non-findings (verified, stated so the absence is evidence-backed)

- **405 handlers do NOT bypass middleware.** They are ordinary `Route` endpoints
  inside the same Starlette app (`gateway.py:320-340`) with the full stack
  Correlation→Metrics→Logging→Security (`gateway.py:343-346`). Empirical proof on
  `GET /mcp` (http): response carries `content-security-policy`,
  `x-content-type-options: nosniff`, `x-frame-options: DENY`, `x-request-id`, and
  `/metrics` shows `mcp_gway_http_requests_total{method="POST",path="/mcp",status="405"} 1`.
- **No route reachable under the wrong transport.** starlette 1.6.0
  `Router.__call__` iterates *all* routes, returning on the first `Match.FULL` and
  only falling back to a stored `Match.PARTIAL` if no FULL exists anywhere
  (verified from installed source). Therefore:
  - sse: `POST /mcp` → PARTIAL on the GET route, then FULL on
    `Route("/mcp", self._mcp_post_not_allowed, methods=["POST"])` → custom 405,
    never Starlette's default 405 and never 404. Empirically confirmed:
    `405`, `allow=GET`, body `{"detail": "Streamable HTTP transport not enabled…"}`.
  - http: `GET /mcp` → PARTIAL on the POST route, FULL on
    `_mcp_get_not_allowed` → `405 allow=POST`.
  - http: `POST /mcp/messages` → no route at all → 404 (`test_http_messages_404`).
  - `/mcp` vs `/mcp/messages` are distinct exact paths (no prefix/param match),
    order between them is irrelevant; the GET/POST order within each list is also
    irrelevant because both methods always FULL-match some route.
- **`Gateway.__init__` fails fast, truly before side effects.** `ValueError` at
  `gateway.py:181-182` precedes `CodeMode(registry)` (line 186) and
  `registry.ensure()` (line 274). `test_unknown_transport_rejected`
  (`tests/test_transport_separation.py:38-47`) covers `("stdio","bogus","HTTP","")`
  — including case-sensitivity and the valid-serve-but-invalid-Gateway value.
- **Default `"http"` is safe at every construction site.**
  - `src/`: exactly two `Gateway(` sites — `cli.py:514` passes `transport`
    explicitly (guarded by `transport in ("http","sse")` at `cli.py:640`, so the
    ValueError path is unreachable from the CLI); `cli.py:421` is F-2 above.
  - `tests/`: 40 sites audited. Every SSE-dependent test passes `transport="sse"`
    explicitly (`test_gateway_sse_limits.py:37`, `test_obsfeat007.py:262`,
    `test_p0_round2_hardening.py:95`); all remaining default sites exercise
    `POST /mcp` (valid under http), probes (`/health`,`/metrics` — listed before
    `*mcp_routes`, `gateway.py:332-337`, transport-independent), or internal
    methods (`_handle_post`, `_create_session`, `_mcp_sse` called directly). The
    green 570-test run corroborates.
- **`_serve_stdio` (default transport) still works.** It never touches HTTP routes
  (see F-2 evidence); `run_stdio_async` → `StdioAdapter.handle_line` →
  `_handle_post`/`_handle_method` only. REQ-TRANSPORT-007 trace
  (`tests/test_stdio.py` full suite) passes.
- **Migrated tests preserve the ORIGINAL assertions — no weakening.** Each test
  touched by `bd2d11a` diffed against its parent:
  - `test_gateway.py`: only path swap `/mcp/messages` → `/mcp`; all value
    assertions intact (`protocolVersion`, 4 tool names, `youtube.pyi`, `"42"`,
    `error in data`, `"query" in text`). Deleted `test_sse_endpoint` (asserted both
    paths on the old dual app) is superseded *and strengthened* by
    `test_transport_separation.py:128-129` (per-transport presence/absence) and
    `:112-113` (`_mcp_sse` binding).
  - `test_edgecases_gateway.py::test_mcp_post_session_not_found`: transport swap
    only; same URL, same `-32001` assert (`:246-253`). `::test_mcp_post_alias_and_limits`
    split into alias(sse)+limits(http); `result == {}`, `400`, `413` all preserved
    byte-for-byte (`:256-277` vs parent).
  - `test_gateway_sse_limits.py`, `test_obsfeat007.py`, `test_p0_round2_hardening.py`:
    one-line `transport="sse"` each; every assertion (429, `Retry-After`, timeout
    RED guard, `len(gw._sessions) == 128`) unchanged.
  - `test_serve_unified.py`: fake signatures gained `transport`; assertions got
    *stronger*, not weaker — `called == {…, "transport": "http"}` (was host/port
    only) and `calls == ["http","sse"]` (was `len(calls) == 2`). AC-05 rewrite is
    the intended contract change (ADR-010 amendment), recorded in the packet.
- **New contract tests exercise routes, not just introspection, and cannot hang.**
  Real `TestClient` requests cover: http POST 200, http GET 405+`Allow`+JSON detail,
  http messages 404, sse messages 200, sse POST 405+`Allow`, plus the cross-fallback
  matrix (`test_no_cross_transport_fallback:131-138`). The two introspection-only
  tests are the route-table surface diff and `test_sse_stream_route` — the latter's
  docstring (`:99-103`) explicitly justifies it: consuming an open SSE stream in a
  sync test would hang forever. That gap is covered by bounded live-stream tests
  elsewhere: `test_obsfeat007.py:265` (`MAX_IDLE_SECONDS=0.05` → stream self-closes)
  and both 429 tests (sessions pre-filled → handler returns 429 *before* opening the
  stream, with `wait_for(…, 3.0)` RED-guard in `test_gateway_sse_limits.py:48`).
  No test in the new file performs an unconsumed `GET /mcp` on an sse gateway —
  hang audit clean.
- **Docs commit `dedf480` matches the code.** Route counts verified: http = 4 probes
  + `POST /mcp` + `GET /mcp` = 6 entries; sse = 4 probes + `GET /mcp` +
  `POST /mcp` + `POST /mcp/messages` = 7 entries. `AGENTS.md` cites
  `gateway.py:320-340` — exactly where `mcp_routes` conditional lives.

## Checklist

| # | Checklist item | Verdict | Evidence |
|---|----------------|---------|----------|
| 1 | `Gateway.__init__` fail-fast on unknown transport | PASS | gateway.py:181-182 (before CodeMode:186, before registry.ensure:274); tests/test_transport_separation.py:38-47 |
| 2 | Default `"http"` safe for all `Gateway(` construction sites | PASS | src: cli.py:514 explicit / cli.py:421 → F-2 (stdio never serves routes); tests: 40 sites audited, SSE sites explicit (test_gateway_sse_limits.py:37, test_obsfeat007.py:262, test_p0_round2_hardening.py:95); 570 green |
| 3 | 405 handlers: JSON body + correct `Allow` ("POST"/"GET") | PASS | gateway.py:522-538; empirical `GET /mcp`→`Allow: POST`, `POST /mcp` (sse)→`Allow: GET` + JSON detail; tests/test_transport_separation.py:66-69, 93-95 |
| 4 | 405 handlers bypass metrics/logging middleware? | PASS (no bypass) | routes inside app (gateway.py:331-340), stack gateway.py:343-346; empirical: CSP/nosniff/DENY/X-Request-ID on 405, `http_requests_total{…,status="405"}` counted |
| 5 | Wrong-transport route reachability (Starlette order subtleties) | PASS | starlette 1.6.0 Router iterates to first FULL, PARTIAL only as last resort (installed source); empirical: sse POST /mcp → custom 405 not 404/default-405; http GET /mcp → custom 405; http POST /mcp/messages → 404; F-1 covers non-GET/POST residue |
| 6 | `_serve_stdio` (default) independent of HTTP routes | PASS | cli.py:399-457 → stdio.py:120,138 (`_handle_method`/`_handle_post` only, never `gateway.app`); tests/test_stdio.py suite green |
| 7 | Migrated tests preserve original assertions (no weakening) | PASS | bd2d11a vs parent, test-by-test: path swaps only, asserts byte-identical; 2 renamed/rewritten tests gained *stronger* assertions (`calls == ["http","sse"]` vs `len==2`); deleted `test_sse_endpoint` superseded by stronger per-transport coverage |
| 8 | Contract tests exercise routes (not just introspection), no hang | PASS | 6/9 tests are real requests; 2 introspection tests justified (surface diff, stream-binding no-hang by design); hang audit: no unconsumed sse GET anywhere; bounded-stream guards at test_obsfeat007.py:262-265 and wait_for 3.0 RED-guard at test_gateway_sse_limits.py:48 |
| 9 | Suite evidence | PASS | `uv run pytest -q` → **570 passed** (TEST_MATRIX target met) |

## Residual risk

F-1/F-2/F-3 accepted as Low with owners: engineering (F-1/F-3 optional follow-up,
F-2 comment-only). No silent PASS — all three are visible above with evidence.
