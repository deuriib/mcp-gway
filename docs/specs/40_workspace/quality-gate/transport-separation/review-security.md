# Security Review: SPEC-TRANSPORT-SEPARATION-001

**Reviewer:** security owner via security-reviewer (quality-gate subagent)
**Date:** 2026-09-22
**Verdict:** APPROVE (Approved)
**Scope:** commits 88f47fd (`src/mcp_gway/gateway.py` + `cli.py`), bd2d11a (tests), dedf480 (docs), d42085f (packet)
**Packet (reference-only):** `docs/specs/40_workspace/transport-separation/{PROPOSED_CHANGES,IMPLEMENTATION_PLAN,TEST_MATRIX}.md`

No Critical, no High, no Medium findings → no orchestrator escalation triggered (guardrails: Critical/High surface same session).

## Threat Model

### Attack Surface

| Surface | Entry Point | Trust Boundary |
|---------|-------------|----------------|
| `/mcp` route table (http mode) | `POST /mcp`; `GET /mcp` → 405 | external only if exposed; default loopback-only |
| `/mcp` route table (sse mode) | `GET /mcp` (SSE); `POST /mcp/messages`; `POST /mcp` → 405 | same |
| 405 gate handlers | `_mcp_get_not_allowed` / `_mcp_post_not_allowed` | same |
| CLI serve binding | `serve --transport http\|sse --host --port` | local (`127.0.0.1` default; `MCP_GWAY_ALLOW_REMOTE=1` opt-in) |
| Probes | `GET /health /ready /live /metrics` | same (unchanged) |

### STRIDE Analysis

| Threat | Applicable? | Mitigation / Evidence |
|--------|-------------|----------------------|
| Spoofing | Yes | No app-layer authn by design (pre-existing local-first posture); bind gate `cli.py:491-498` (`MCP_GWAY_ALLOW_REMOTE` + `sys.exit(2)`), default `--host 127.0.0.1` `cli.py:598`. The 405 `detail` discloses product/transport identity → S-001 (Low). The `Allow` header itself is RFC-mandated on 405, so transport mode is inferable regardless. |
| Tampering | Yes | `transport` validated against closed whitelist literal, `ValueError` fail-closed (`gateway.py:181-182`); route sets built from literals only, zero request input in routing (`gateway.py:320-330`); 405 bodies are static strings (`gateway.py:522-538`) → no injection surface. |
| Repudiation | Yes | 405s traverse the full middleware stack (order `gateway.py:341-346`: Correlation → Metrics → Logging → Security → router): INFO log with method/path/status `middleware.py:108-116`; metric `http_requests_total{...,status="405"}` `middleware.py:84-93`; `/mcp*` normalized by `path_template` `middleware.py:36-42` (no label cardinality, 405s counted under `path="/mcp"`); `X-Request-ID` on every response `middleware.py:54`. **Logged and counted — no gap.** |
| Information Disclosure | Yes | 405 body = static `detail` only — no stack, config path, or version (`gateway.py:522-538`). Compare `_safe_error_data` (`gateway.py:80-95`): allow-listed `[reason=...]` tokens + exception type, never raw messages — the 405 literal is static so it cannot leak dynamic secrets, though it is more descriptive than that posture (product fingerprint → S-001, Low). CSP/nosniff/DENY still applied to 405 responses via `_SecurityMiddleware` (`gateway.py:37-45`). |
| Denial of Service | Yes | **Improved by this change.** `POST /mcp` on sse hits `_mcp_post_not_allowed` (`gateway.py:323` → `530-538`), which never touches `request.stream()`/`request.body()` → returns 405 **before body read**: no JSON parse, no `post_sem` slot, no app-side buffering. Body read exists only in `_mcp_post` → `_read_limited_json` (`gateway.py:613-621`, `671-687`): Content-Length precheck → 413 (`674-676`), streamed cap `MAX_BODY_BYTES` → 413 (`677-681`), `POST_READ_TIMEOUT=5.0` → 408 (`616-621`), `post_sem` → 429 (`628-641`). Conversely `GET /mcp` on http (`gateway.py:329` → `522-528`) is an immediate static JSONResponse — no `_sse_lock`, no session creation (contrast `_mcp_sse` `gateway.py:543-551`). |
| Elevation of Privilege | Yes | Routes are constructed first (`gateway.py:331-340`), then `add_middleware` wraps the whole ASGI app (`gateway.py:343-346`) — so Security (CSP), Logging, Metrics, Correlation apply to every new route and every 405; no transport selection bypasses them. `post_sem` + body caps intact on the allowed POST path (unchanged). The 405 path bypasses `post_sem` but consumes only a static response — nothing to protect, no slot to hold. No new privileged path. |

### Residual Risk

1. **No authn/authz at app layer** — pre-existing design (local-first). Remote exposure still requires `MCP_GWAY_ALLOW_REMOTE=1` + external firewall/auth (AGENTS.md local-first warning). Untouched by this change. Owner: engineering/ops.
2. **Unread bodies on 405 paths** are drained or the connection closed at the uvicorn/h11 layer — server-level behavior, identical to the pre-change 404-for-unrouted-method case; the app never buffers them. Owner: engineering (accepted).
3. **S-001 fingerprinting** accepted for local-first posture; revisit if a public deployment ever fronts the gateway. Owner: engineering.

## Checks (evidence-backed)

| Check | Result | Evidence |
|-------|--------|----------|
| Secrets scan (`git show 88f47fd bd2d11a dedf480 d42085f \| grep -iE "token\|secret\|password\|api[_-]?key"`) | **PASS — 0 secrets.** 2 hits, both benign prose: (a) AGENTS.md structure line "oauth.py … token storage" (dedf480 context), (b) d42085f checklist "Sin PII/secrets en el diff (… sin credenciales)". No credential values anywhere. | diffs of the 4 commits |
| Local-first `--host/--port` + `MCP_GWAY_ALLOW_REMOTE` unchanged | **PASS.** Gate `cli.py:491-498` (`allowed_remote`, `is_loopback`, `sys.exit(2)`), warning `cli.py:506-508`, banner `cli.py:567-569`, default `cli.py:598` (`127.0.0.1`), `--host/--port` restriction `cli.py:631-638` (`sys.exit(2)`). All outside 88f47fd hunks (`@@ -458`, `-503`, `-548`, `-584`, `-629` — none cover 491-498 or 598); diff only touches `_serve_http` signature, `Gateway(...)` call, banner label, help text. | `git show 88f47fd -- src/mcp_gway/cli.py` |
| Exclusive route sets, deny-by-default | **PASS.** `if transport == "sse"` / `else` build disjoint lists (`gateway.py:320-330`); invalid transport → `ValueError` (`gateway.py:181-182`); contract tests: cross-path 404 `tests/test_transport_separation.py:72-77,137`, cross-method 405+Allow `:62-69,89-95,133-136`, ValueError `:38-47`. | tests + source |
| No new endpoint/payload beyond gated ones | **PASS.** Probes unchanged (`gateway.py:332-336`); the diff replaces only the three `/mcp*` entries with the per-transport sets; `/mcp/messages` does not exist under http (404 asserted `tests/test_transport_separation.py:137`). | `git show 88f47fd` |
| Transport selection exposed on `app.state` (no secret/config payload) | **PASS.** `app.state.transport` = the literal `"http"`/`"sse"` only (`gateway.py:349`), asserted `tests/test_transport_separation.py:141-144`. | source + tests |

## Findings

| ID | Severity | Finding | Evidence (file:line) | Owner | Remediation |
|----|----------|---------|----------------------|-------|-------------|
| S-001 | **Low** | The 405 `detail` strings disclose product CLI syntax + configured transport mode (`"SSE transport not enabled (serve --transport sse)"` / `"Streamable HTTP transport not enabled (serve --transport http)"`), fingerprinting the deployment beyond the RFC-required `Allow` header. **Justification for Low:** bodies are static — no secrets, config paths, or versions; transport mode is already inferable from `Allow`; and `serve` defaults to `127.0.0.1` (`cli.py:598`) with non-loopback binding requiring `MCP_GWAY_ALLOW_REMOTE=1` (`cli.py:491-498`), so an unauthenticated remote probe only exists after explicit opt-in. | `gateway.py:525`, `gateway.py:534` | engineering | **Non-blocking.** Optional: generic `"Method not allowed"` detail (keep `Allow`) if/when a publicly-fronted deployment is supported. |
| S-002 | **Low** | Pre-existing, **not introduced by this change**: Starlette auto-adds `HEAD` to any `GET` route, so `HEAD /mcp` maps to `_mcp_sse` under sse (session churn under a HEAD flood, bounded by `MAX_CONCURRENT_SSE=128` at `gateway.py:544`). This diff is neutral-to-better: the removed pre-change route `Route("/mcp", self._mcp_sse, methods=["GET"])` behaved identically on every deployment, while under http HEAD now hits the 405 gate instead of spawning an SSE session. | `.venv/.../starlette/routing.py:238` (`self.methods.add("HEAD")`), `gateway.py:322`, `git show 88f47fd` removed-lines | engineering | **Backlog, non-blocking:** register an explicit `HEAD → 405` route if HEAD floods ever matter. No action required for this spec's approval. |

## Conditions for Approval

None — **APPROVE**. S-001 and S-002 are non-blocking advisories with owners recorded above.

## Sign-off

- [x] security owner (security-reviewer subagent — STRIDE complete, every finding evidence-backed)
- [ ] engineering owner (if architecture-impacting) — architecture lane covers the ADR-010 amendment separately
