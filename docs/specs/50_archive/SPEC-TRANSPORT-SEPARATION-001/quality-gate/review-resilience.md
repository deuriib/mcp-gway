# Quality Gate — RESILIENCE Review

**Spec:** SPEC-TRANSPORT-SEPARATION-001
**Domain:** Resilience — failure behavior under load/adversity (concurrency, timeouts, degradation, cleanup). Style and risk policy out of scope.
**Scope:** commit `88f47fd` (src/mcp_gway/gateway.py + cli.py), commit `bd2d11a` (tests)
**Reviewer:** resilience domain owner (subagent, quality-gate full-wave)
**Date:** 2026-09-22

## Verdict: **APPROVE**

No Critical/High findings. The refactor touches only route construction and adds two
stateless 405 handlers; every load/limit/cleanup mechanism (`post_sem`, body limits,
slow-loris timeout, SSE session lock, queue drop, idle reaper, heartbeat) is untouched
and its tests pass at HEAD (128/128 in the resilience-relevant subset). Four Low/Info
findings below — none block ship; R-2 and R-3 are cheap coverage notes.

## Findings

### R-1 (Info): 405 gate handlers run OUTSIDE the POST guards — correct and strictly safer

- Handlers `_mcp_get_not_allowed` (gateway.py:522-528) and `_mcp_post_not_allowed`
  (gateway.py:530-538) are plain `Route` handlers returning `JSONResponse` immediately.
  They never touch `_post_sem` (gateway.py:192), never call `_read_limited_json`
  (gateway.py:671-687), and never pass through `POST_READ_TIMEOUT` (gateway.py:612-621).
  Route binding: gateway.py:320-330.
- Neither handler reads the body (no `request.stream()` / `await request.body()`), and
  Starlette does not auto-read bodies for route handlers — the 405 short-circuits
  **before** any body consumption. An attacker POSTing a stalled body to `POST /mcp`
  on `transport="sse"` therefore **cannot hold a `post_sem` slot** (acquisition only
  happens inside `_mcp_post`, gateway.py:628-641, which is never invoked on this path)
  and cannot consume read-timeout budget (no read is attempted).
- Resource exposure: a stalled body still occupies a uvicorn connection/socket fd at
  the ASGI-server layer until teardown — but that is transport-level, predates this
  refactor, and applies identically to every endpoint (probes included). Compared to
  the old dual-app behavior — where `POST /mcp` on an sse-serving process entered
  `_mcp_post` and read the body for up to 5s before responding — the new gate is a
  strict reduction in exposure: instant response, no semaphore, no timeout budget,
  no app-layer task held. Short-circuit-before-body-read is the desired design.

### R-2 (Low): probes proven on `http` only — degradation path for `sse` is structural, not tested

- Probes `/health`, `/ready`, `/live`, `/metrics` are unconditional in the route table
  (gateway.py:333-336); `*mcp_routes` is appended after (gateway.py:337), so both
  transports carry them by construction. Degradation path is sound in code.
- But REQ-TRANSPORT-006's cited tests run only on the default transport:
  `test_edgecases_gateway.py:57-68` (`_gw(tmp_path)` defaults to `http`) and
  `test_wave2_api.py:18-19` (bare `Gateway(registry)`). No test asserts a probe
  responds on a `transport="sse"` app, nor that probes + a 405-gated `/mcp` coexist
  on one app.
- Suggested closure (not blocking): parametrize those two helpers over
  `("http", "sse")` — one-line each.

### R-3 (Low): "129 concurrent GETs" load condition — migration preserved it exactly, but the name overstates what was ever tested

- Migration fidelity confirmed: `bd2d11a` changed exactly one line in
  `test_p0_round2_hardening.py` (line 95: `Gateway(reg)` → `Gateway(reg, transport="sse")`).
  The 128 pre-filled sessions (line 96-97) and everything else are byte-identical —
  load conditions were preserved, nothing was weakened.
- However, the test fires **5** concurrent GETs against 128 pre-filled sessions
  (line 104), not 129 concurrent GETs — this was true before the migration too
  (pre-existing gap, NOT introduced by this change). It proves the *reject* path under
  contention (all 429, session count stays 128 → no over-admission on reject,
  line 112). The *admit* race named in the gateway comment ("129 concurrent GET /
  mcp deterministically yields one 429", gateway.py:541-542) — 129 concurrent from an
  empty table → exactly 128 admitted, exactly one 429 — has no test. The `_sse_lock`
  check-and-create (gateway.py:543-551) reads correct under review, but the admit
  race is uncovered. TEST_MATRIX.md:42 should not be read as evidence it is covered.
- Same-day closure option: `asyncio.gather(*(c.get("/mcp") for _ in range(129)))` on
  an empty gateway, assert `sum(200) == 128` and `sum(429) == 1`.

### R-4 (Low): unreachable-but-misleading ValueError handler in `_serve_http`

- `Gateway.__init__` raises `ValueError` (gateway.py:181-182) as the **first** statement
  — before `registry.ensure()` (gateway.py:274), so fail-fast with zero side effects.
  Proven by `test_transport_separation.py:38-47`.
- CLI reachability: `click.Choice(["stdio", "http", "sse"])` (cli.py:592) rejects any
  other value before the callback runs — the `ValueError` is unreachable via `serve`.
  The `else: raise click.BadParameter` at cli.py:642-643 is dead-but-defensive behind
  the Choice. Clean behavior verified: no traceback path exists.
- If `_serve_http` is ever called programmatically with a bad transport, the
  `except Exception` at cli.py:516-520 catches it and prints
  `Error: invalid --registry-dir {dir} [reason=unknown transport 'x']` → exit 2.
  Exit is clean (no traceback), but the message **misattributes the failure to
  `--registry-dir`** — an operator chasing a config path during an incident. One-line
  fix: catch `ValueError` separately or reword. Unreachable today → Low.

### R-5 (Info): heartbeat / lifespan / cleanup unchanged by the refactor

- Full `git show 88f47fd` reviewed: hunks touch only the `__init__` signature +
  validation + `self.transport` (gateway.py:169-186), the `mcp_routes` block
  (gateway.py:320-330), `app.state.transport` (gateway.py:349), and the two new 405
  handlers (gateway.py:522-538). `_lifespan` (gateway.py:302-318), `_heartbeat`
  (gateway.py:503-517), `aclose` (gateway.py:359-386), and
  `cleanup_expired_sessions` (gateway.py:397-427) are untouched.
- Guard coverage on the new route table verified green at HEAD:
  `test_r3_post_contention_429_with_retry_after` (32 sem slots → 429 + Retry-After via
  `POST /mcp` on http; test_p0_round21_fixes.py:78-101),
  `test_r3_read_outside_semaphore_or_read_timeout` (:104-113),
  `test_gateway_post_semaphore_and_metric` (test_p0_round2_verify.py:126-151),
  MAX_QUEUE drop (test_gateway_sse_limits.py:62-85, transport-agnostic direct call),
  idle reaper (:88-105), idle disconnect (test_obsfeat007.py with `transport="sse"`),
  429-full (test_gateway_sse_limits.py:33-59, 128 sessions preserved).

## Checklist

| # | Checklist item | Verdict | Evidence |
|---|----------------|---------|----------|
| 1 | 405 handlers vs POST guards (post_sem, body limit, slow-loris): safe short-circuit before body read? | **PASS** — handlers outside guards by design; cannot hold a slot; strictly less exposure than pre-refactor | gateway.py:522-538 vs 608-669; routes 320-330 |
| 2 | SSE limits (MAX_SESSIONS=429, MAX_QUEUE drop, idle cleanup) unchanged; migration preserved load conditions | **PASS with note (R-3)** — 128-session conditions byte-identical post-migration; "129 concurrent" naming pre-existing gap, admit race untested | gateway.py:61-70, 540-606 untouched; test_gateway_sse_limits.py:33-59, 62-85; test_p0_round2_hardening.py:95-112 (only line 95 changed) |
| 3 | Probes available when `/mcp` gated (degradation path) | **PASS with note (R-2)** — structurally unconditional; test coverage only on `http` | gateway.py:331-337; test_edgecases_gateway.py:57-68; test_wave2_api.py:18-27 |
| 4 | Unknown transport (ValueError): caught? clean CLI error, no traceback? | **PASS with note (R-4)** — unreachable via `click.Choice`; if reached programmatically: exit 2, no traceback, but message misattributes `--registry-dir` | gateway.py:181-182 (before side effects); cli.py:592, 516-520, 642-643; test_transport_separation.py:38-47 |
| 5 | Heartbeat/lifespan unchanged? | **PASS** — zero diff hunks touch lifespan/heartbeat/aclose/reaper | `git show 88f47fd` full diff; test_gateway_sse_limits.py:88-105 green |
| — | Resilience suite green at HEAD | **PASS** — 128 passed / 0 failed (subset: transport_separation, sse_limits, p0_round2*, edgecases, obsfeat007, round2_p0, wave2, gateway, serve_unified, observability_probes) | `uv run pytest -q <subset>` @ `6fff6cc` |

## Residual risk (explicit)

R-2 and R-3 are coverage gaps, not behavior defects: probe-on-sse and admit-race are
guaranteed by reviewed code paths but not executed by tests. Accepted for this gate
with the closure suggestions above; neither should survive to the next transport change.
