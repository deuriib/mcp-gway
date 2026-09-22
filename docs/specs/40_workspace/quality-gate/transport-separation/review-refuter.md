# Review — REFUTER (adversarial): SPEC-TRANSPORT-SEPARATION-001

**Date:** 2026-09-22
**Scope:** commits `88f47fd` (src), `bd2d11a` (tests), `dedf480` (docs)
**Packet:** `docs/specs/40_workspace/transport-separation/{PROPOSED_CHANGES,IMPLEMENTATION_PLAN,TEST_MATRIX}.md`
**Role:** adversarial — attack every claim, no re-run of other reviewers' checklists, no charity, no manufactured findings.
**Environment:** Starlette 1.6.0 (uv runtime), `uv run pytest -q` → **570 passed**, `ruff check`/`ruff format --check` clean (independently re-run, not taken on trust).
**Scratch:** `/tmp/opencode/probe_refuter_transport.py`, `/tmp/opencode/probe_real_server.py` (repo untouched: `git status -- src/ tests/` → 0 entries; only this report added).

## VERDICT: APPROVE

No attack succeeded. All six attacks are REFUTED (claims SUSTAINED), with two honest edge observations that lie outside the spec's stated matrix (logged in A-01/A-03, neither is a guarantee violation).

---

## Attack log

### A-01 — "No cross-transport fallback" (claim 1) → ATTACK FAILED

**ATTACK:** Construct counterexamples via Starlette's two-`Route`-on-same-path routing: method-routed partial matches, HEAD/OPTIONS/DELETE/PUT/PATCH, trailing-slash redirects, and `/mcp/messages` under http — hunt for any request that reaches the *other* transport's handler.

**EVIDENCE (ASGI-level, `TestClient`, full 7-method × 4-path × 2-transport matrix + real `uvicorn` server on 127.0.0.1:8911):**

- http: every non-POST method on `/mcp` → **405 `Allow: POST`** (GET/HEAD → custom JSON `{"detail":"SSE transport not enabled..."}`; OPTIONS/DELETE/PUT/PATCH → Starlette auto-405 JSON, same `Allow`). Real server: `GET /mcp → 405 allow=POST body='{"detail":"SSE transport not enabled..."}'`, `DELETE /mcp → 405 allow=POST`. **`_mcp_sse` is not in the http route table at all** (`http mcp routes: [('/mcp',['POST']), ('/mcp',['GET','HEAD'])]`) — an SSE stream is unobtainable, even with `Accept: text/event-stream`.
- http: `/mcp/messages` → **404 for all 7 methods** (no route, no redirect match).
- sse: `POST /mcp` → **405 `Allow: GET`** (custom JSON), also with `?session_id=...` → 405. JSON-RPC is unreachable via `POST /mcp`.
- Trailing slash: `/mcp/` → **307 → `/mcp`** in both transports for all methods; the redirect target stays on the same transport's surface (http-followed `GET /mcp/ → 405 Allow: POST`; sse-followed `POST /mcp/ → 405 Allow: GET`). Same-path redirect ≠ cross-transport fallback.
- Construction order: `Gateway(reg, transport="stdio")` → `ValueError: unknown transport 'stdio'` raised **before** `registry.ensure()` (`gateway.py:181-182` vs `:274`) — no side effect before the gate.

**Honest edge observations (NOT violations — outside the spec's stated matrix):**
- `HEAD /mcp` on **sse → 200 `text/event-stream`**: Starlette auto-adds HEAD to GET routes, so HEAD invokes `_mcp_sse`. HEAD⊆GET is RFC-consistent (headers mirror GET); not a cross-transport leak. The spec only claims GET→stream and POST→405 for sse.
- sse `DELETE/OPTIONS/PUT/PATCH /mcp` → 405 `Allow: GET, HEAD` (Starlette partial-match auto-405 from the first-partial route; set-join order is per-process). Unspecified combos, still deny-by-default 405, still no fallback.

**REFUTED.** No method/path/redirect combination reaches the other transport's handler on either transport, at ASGI level and on a real uvicorn server.

### A-02 — "http = 6 entries, sse = 7 entries" (claim 2) → ATTACK FAILED

**ATTACK:** Count `gateway.app.routes` for both transports; check for hidden routes or middleware inflating the count.

**EVIDENCE (runtime):**
```
http n= 6 ['/health', '/ready', '/live', '/metrics', '/mcp', '/mcp']
sse  n= 7 ['/health', '/ready', '/live', '/metrics', '/mcp', '/mcp', '/mcp/messages']
```
`Starlette.app.routes` is `Router.routes` — the 4 middlewares (`Correlation`, `Metrics`, `Logging`, `_Security`, `gateway.py:343-346`) are not route entries. The duplicate `/mcp` paths are the intentional method-gated pairs (`gateway.py:320-330`).

**REFUTED.** Counts are exactly 6 / 7 as claimed.

### A-03 — "405 + Allow header" matrix (claim 3) → ATTACK FAILED

**ATTACK:** Verify status + `Allow` for every method/path/transport combination (pushed beyond the spec's 3×2×2 to 7 methods × 4 paths × 2 transports), at ASGI level **and** on a real production server (h11 body suppression, middleware header stripping).

**EVIDENCE — spec'd cells (both ASGI and real uvicorn agree):**

| Path | Method | http | sse |
|---|---|---|---|
| `/mcp` | GET | **405 `Allow: POST`** ✓ | **200 `text/event-stream`** ✓ |
| `/mcp` | POST | **200 JSON-RPC** ✓ | **405 `Allow: GET`** ✓ |
| `/mcp/messages` | GET | 404 ✓ | 405 `Allow: POST` (unspecified; correct — path exists POST-only) |
| `/mcp/messages` | POST | **404** ✓ | **200 JSON-RPC** ✓ |
| `/health` | GET | 200 + `CSP: default-src 'self'` ✓ | 200 + `CSP: default-src 'self'` ✓ |

Real-server excerpt: `http GET /mcp → 405 allow=POST`, `http HEAD /mcp → 405 allow=POST` (h11 suppresses the body, header intact), `sse POST /mcp → 405 allow=GET`, `sse GET /mcp → 200` with `event: endpoint\ndata: /mcp/messages?session_id=...`, probes 200 on both. Off-matrix cells (OPTIONS/DELETE/PUT/PATCH) → 405 with `Allow`, or 404/307 — never the other surface (full table in `/tmp/opencode/probe_refuter_transport.py` output).

**REFUTED.** Every specified cell matches exactly, at ASGI and production level; CSP confirmed present on both transports (REQ-TRANSPORT-006 spot-check — note `tests/test_wave2_api.py::test_csp_header` exercises only the http fixture, but the middleware is built unconditionally for both).

### A-04 — "stdio unaffected" (claim 4) → ATTACK FAILED

**ATTACK:** Grep the stdio path for HTTP-route dependencies; hunt for signature breakage from `_serve_http(..., transport)` and `Gateway(..., transport)` changes.

**EVIDENCE:**
- `src/mcp_gway/stdio.py` has **zero** references to `.app`, `Route`, `app.routes`, or `Request`; the NDJSON loop depends only on `self._gateway._handle_method` (`stdio.py:120`) and `self._gateway._handle_post` (`stdio.py:138`) — pure handler methods, route-table-independent.
- `_serve_stdio` (`cli.py:399-421`) builds `Gateway(registry)` (default `transport="http"` — routes constructed but never served); the stdio branch (`cli.py:639`) and the `mcp` alias (`cli.py:919-922`) are byte-identical to pre-change (`git show 88f47fd` touches only `_serve_http`, the `serve` dispatch call, and the `--transport` help string).
- Only caller of `_serve_http` in the tree is `cli.py:641` (updated); no `Gateway(...)` call anywhere passes a third positional arg that could be swallowed as `transport`.
- `tests/test_stdio.py`, `test_edgecases_stdio.py`, `test_stdio_transport.py` all green in the 570.

**REFUTED.** The stdio path has no HTTP-route dependency and no behavioral delta from these commits.

### A-05 — Docs statements now false (claim 5) → ATTACK FAILED

**ATTACK:** Grep AGENTS.md / README.md / API_CONTRACTS.md / ARCHITECTURE.md (plus the whole repo, widened) for stale claims: `7 Route entries`, `comparten la app`, `share.*same app`, `GET+POST /mcp`, `no shape change`, stale line refs `gateway.py:194-200`.

**EVIDENCE:**
- Zero stale hits in the four named files. `dedf480` replaced them: AGENTS.md:32/:148 (per-transport sets, 6/7 counts, line ref `gateway.py:320-340` — verified accurate: conditional block 320-330, app build to 340), AGENTS.md:177-178 (SSE section), README.md:159 (table) + README.md:278-282 (diagram `[http]`/`[sse]` tags), API_CONTRACTS.md:16-23 (amended contract — `transport="http"` default ✓ matches `gateway.py:172`; 6/7 routes ✓), ARCHITECTURE.md:28 (accurate per-transport row).
- The only remaining `comparten` in scope is AGENTS.md:78: "comparten el entrypoint `_serve_http`, **NO la app**" — the amendment itself, correct wording.
- `find . -name 'adr-010*'` → nothing: AGENTS.md:78's "referenciado, ausente en repo" claim is TRUE.
- `GET+POST /mcp` survives only in `docs/briefs/BRIEF-performance.md` and `docs/specs/50_archive/**` — dated briefs and frozen archives (per HANDOFF convention "historical docs intentionally untouched"), outside the four files and outside this spec's change set.
- Weak spots checked and **not** false: README.md:74 ("One `Gateway(registry, host)` process serves `/mcp` ... on the same `Starlette` app") — still true for one process/one app, and the call form remains valid with the defaulted `transport`; ARCHITECTURE.md:19/27 "5 paths" — path count is unchanged by method gating.
- Pre-existing staleness (NOT introduced by this spec, out of gate scope): README.md:61-63 `serve --port 8080` quickstart needs `--transport http|sse` (stdio default predates this change); AGENTS.md Testing "(255 tests)" was already stale at the 548 baseline.

**REFUTED.** No statement in the four named docs is made false by the change; all repo-wide leftovers are frozen historical records.

### A-06 — Migration integrity: weakened or dropped assertions (claim 6) → ATTACK FAILED

**ATTACK:** Diff every old vs new test body in `bd2d11a`; find any original assertion deleted, loosened, or silently dropped.

**EVIDENCE (`git show bd2d11a`, line-by-line):**
- **Deleted (2 total):**
  1. `test_gateway.py::test_sse_endpoint` — old body only asserted `"/mcp" in routes` and `"/mcp/messages" in routes` on the default (now http) gateway. Replaced by **stronger** coverage: `test_sse_stream_route` asserts exactly one GET `/mcp` route bound to endpoint `_mcp_sse` (identity + uniqueness), `test_sse_routes_and_messages_works` asserts alias behavior (`result == {}`), `test_http_messages_404` asserts absence under http (new direction). Documented in TEST_MATRIX row `test_sse_endpoint → aserción por transporte (movido a test_transport_separation)`.
  2. `test_serve_unified_http_sse_same_app` (AC-05) → rewritten as `test_serve_unified_http_sse_distinct_routes`. **All three source-inspection asserts retained verbatim** (`"_serve_http" in src`, `"gateway.app" in http_src`, `"uvicorn.run" in http_src` — current file lines 117-121) and `len(calls) == 2` **strengthened** to `calls == ["http", "sse"]` (value + order proves transport propagation). The semantic change (same-app → distinct-routes) is the spec's intent and is explicitly recorded in TEST_MATRIX migration row 44 — an amended contract, not a silent drop.
- **Path changes only:** 7 JSON-RPC tests switched `/mcp/messages` → `/mcp`; every assertion byte-identical (protocolVersion, `result`, `youtube.pyi`, `"42"`, `error in data`...).
- **Signature changes only:** 5 tests added `transport="sse"` (1-line diffs); assertions untouched.
- **Split:** `test_mcp_post_alias_and_limits` — all three originals preserved across two gateways (`result == {}`, `400` on not-json, `413` on 1 MiB+1) — verified in current `tests/test_edgecases_gateway.py:256-278`.
- **Strengthened:** `test_serve_unified_transport_option_gate` now also asserts `transport` propagation (`called == {..., "transport": "http"}`).
- Suite independently re-run: **570 passed, 0 failed** — matches the packet's claim.

**REFUTED.** No original assertion was weakened or dropped; the two intentional contract rewrites are documented in the packet and both are net-stronger.

---

## Summary

| # | Attack | Result |
|---|--------|--------|
| A-01 | Cross-transport fallback (methods, redirects, HEAD/OPTIONS/DELETE, /mcp/messages) | REFUTED — claim **sustained** |
| A-02 | Route counts 6/7 | REFUTED — claim **sustained** (exactly 6 / 7) |
| A-03 | 405 + Allow matrix (ASGI + real uvicorn) | REFUTED — claim **sustained** |
| A-04 | stdio HTTP-route dependency / signature breakage | REFUTED — claim **sustained** |
| A-05 | False docs statements in the four named files | REFUTED — claim **sustained** |
| A-06 | Weakened/dropped assertions in migration | REFUTED — claim **sustained** |

**Attacks succeeded: 0 / 6. Verdict: APPROVE.**

Residual observations for the record (none blocks the gate): (1) `HEAD /mcp` on sse returns 200 event-stream via Starlette's implicit HEAD⊆GET — RFC-consistent, unspecified by spec; (2) Starlette's auto-405 `Allow` set-join order (`GET, HEAD` vs `HEAD, GET`) is hash-order dependent on off-matrix methods — cosmetic, deny-by-default still holds; (3) pre-existing doc staleness (README serve quickstart transport flag, AGENTS "255 tests") predates this change and belongs to a different lane.
