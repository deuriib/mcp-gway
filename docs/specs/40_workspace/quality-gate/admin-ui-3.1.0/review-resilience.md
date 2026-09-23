# Resilience Review: admin-ui-3.1.0

**Reviewer:** review-resilience (engineering domain)
**Date:** 2026-09-23
**Verdict:** conditional
**Scope:** read-only; live probes against `mcp-gway serve --transport http --host 127.0.0.1 --port 8099 --registry-dir /tmp/opencode/rr/servers` (isolated registry). No source edits, no commits. Zero secrets in this artifact.

## Checklist

- [x] Graceful degradation under partial failure — empty registry, corrupt config JSON, unreachable upstream all degrade to UI states (RS-101/103/104), never 500s.
- [~] Circuit breakers / retries with backoff — discovery is bounded (semaphore 3 + `asyncio.timeout`, `core/install.py:14,39-47`; `core/client.py:299`); no backoff, but refresh is user-triggered single-shot — acceptable, no breaker needed at this scale.
- [~] Resource limits (memory, CPU, connections) — per-server discovery bounded, but **refresh-all has no aggregate deadline** (F-2).
- [x] Recovery from crash / restart — atomic writes (`registry.py:62-67`); crash mid-`add` pair degrades to an `config unreadable` row, not a 500 (`admin/data.py:46-49`). Stale CSRF after restart is fail-closed (F-5).
- [~] No single point of failure introduced — **two external CDNs gate admin operability** (F-1).
- [~] Observability — JSON warn logs on `mcp_gway.admin` (`routes.py:279-281,657-659,788-791`) + metrics middleware, but **probes mask config corruption** (F-3).
- [~] Chaos scenarios tested — 34 admin tests cover 403/404/405/empty/unreadable (`tests/test_admin_dashboard.py`), but no test for CDN outage, probe-health-during-admin-failure, or refresh timeout (F-6).

## Stress Scenarios

| ID | Scenario | Expected | Observed | Pass? |
|----|----------|----------|----------|-------|
| RS-101 | Empty registry: probes + admin index | `/health` `/ready` `/live` 200; index 200 with empty state | all 3 probes 200; `GET /` → 200, `No servers yet` present (1) | yes |
| RS-102 | Graceful 403/404/405 fallbacks | correct codes, no 500s | `PUT .../servers/X/tools` → 405; `POST /admin/observability` → 405 (`allow: HEAD, GET`); `GET /admin/does-not-exist` → 404; `POST partials/refresh` no CSRF → 403; `GET /admin/servers/Nope` → 404 | yes |
| RS-103 | Upstream discovery timeout (unreachable `npx -y <fake-pkg>`, timeout 5000) | bounded, graceful toast, no hang | wall **7758 ms**, HTTP 200, toast `No tools discovered for Demo — try authentication.` | yes |
| RS-104 | Corrupt registry JSON mid-flight | admin degrades, probes stay healthy | `GET /admin/servers` → 200 with `config unreadable` row (1); `/health` `/ready` `/live` → 200 (but see F-3: `checks.registry: "ok"`) ; refresh-on-corrupt → graceful toast, 13 ms | yes (F-3) |
| RS-105 | CDN unavailability (Tailwind/htmx) | page remains operable or degrades declared | **not operable**: no local fallback — static evidence F-1; not live-tested (no network-partition harness) | no (F-1) |
| RS-106 | Refresh-all aggregate deadline with N remote/OAuth-less servers | bounded total | **no aggregate cap**: sequential loop × per-server inline OAuth wait up to 300 s — static evidence F-2 | no (F-2) |
| RS-107 | Concurrent CLI + web writes | last-write-wins, no torn files | atomic single-file writes (`registry.py:123-129` json-only for `set_config`; `update()` re-reads config *after* discovery, `registry.py:178-180`); human-timescale modal window loses CLI edits — documented accepted design (F-4) | yes (accepted) |

## Findings

### F-1 — Medium — CDN is a single point of failure for admin operability
**Location:** `src/mcp_gway/admin/layout.py:36-40,242-248`; `src/mcp_gway/admin/components.py:86,382`; CSP `src/mcp_gway/gateway.py:42-49`.
**Evidence:** both assets are CDN-only (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`). htmx is SRI-pinned (`layout.py:37-39`); Tailwind has no `integrity` (inherent — runtime JIT script) and no local fallback. Without them: `hidden`/`peer-checked:*` utilities are inert → modal overlay (`components.py:382`) renders permanently visible, sidebar/drawer layout collapses; every action pill defaults to `type=button` (`components.py:86`) with `hx-*` inert → **all mutations dead** (only plain-link navigation survives).
**Impact:** local-first admin tool depends on internet availability for both styling and function.
**Owner:** engineering. Either vendor both assets locally (self-host under `script-src 'self'`) or record an explicit accepted-risk entry (owner + justification + expiry) in CHANGELOG/ADR.

### F-2 — Medium — Refresh-all has no aggregate deadline; inline OAuth wait up to 300 s per server
**Location:** `src/mcp_gway/admin/routes.py:667-686` (sequential loop), `routes.py:655` (`refresh_server` awaited in-request); `src/mcp_gway/core/client.py:353-371` (`needs_auth` true for **any** remote with empty discovery); `src/mcp_gway/oauth.py:532` (`wait_for_callback(timeout=SSRF_IDLE_TIMEOUT)`); `src/mcp_gway/models.py:28` (`SSRF_IDLE_TIMEOUT = 300.0`).
**Evidence:** single-server refresh bounded (RS-103, 7.8 s), but `p_refresh_all` sums worst-case per-server times with no overall cap; a reachable remote whose discovery returns empty enters the interactive OAuth flow inline (browser + callback port) inside the request. htmx issues no request timeout → UI sits dimmed (`.htmx-request`, `layout.py:66`) potentially N×300 s. Note `p_auth` correctly backgrounds the flow (`routes.py:724-745`) — refresh paths do not.
**Impact:** hung admin tab; blocked event-loop-adjacent worker task per request (async, so gateway stays up — degradation, not outage).
**Owner:** engineering. Bound the aggregate (e.g. `asyncio.wait_for` budget) or background refresh-all like `p_auth`.

### F-3 — Medium — Probes report healthy while every config is unreadable
**Location:** `src/mcp_gway/observability/health.py:13-27` (get_config failure swallowed, lines 19-24); surfaced by `src/mcp_gway/admin/routes.py:131-134` (footer `healthy`) and `routes.py:343` (Observability page).
**Evidence:** RS-104 — with corrupt `Demo.json`, admin correctly degrades, yet `/health` returned `{"checks":{"registry":"ok",...}}` and the footer would show `healthy`. `check_registry` only requires `list()` to succeed.
**Impact:** false-green health signal; operators/automation monitoring `/ready` get no signal of registry corruption. Pre-existing semantics, now amplified by the v3.1.0 UI badge.
**Owner:** engineering. Make `check_registry` count config-read failures (degraded → honest detail), or rename the badge claim.

### F-4 — Low — Web config edit is a human-timescale read-modify-write (lost update window)
**Location:** `src/mcp_gway/admin/routes.py:826` (read) → `routes.py:910` (write); `src/mcp_gway/registry.py:123-129`.
**Evidence:** no version/CAS on `set_config`; a CLI write during an open edit modal is silently overwritten. Mitigations already in place: atomic writes (`registry.py:62-67`), `set_config` never touches `.pyi` (tools survive), `update()` re-reads config *after* upstream discovery (`registry.py:178-180`) so refresh races are read-post-await. Design is documented as last-write-wins (AGENTS.md, Registry section).
**Impact:** single-operator local-first tool; low probability, recoverable.
**Owner:** engineering — accepted risk; keep documented. No fix required for this release.

### F-5 — Low — Gateway restart invalidates open tabs' CSRF token (fail-closed, recoverable)
**Location:** `src/mcp_gway/gateway.py:375` (per-process token); `src/mcp_gway/admin/routes.py:86-91,107-108`.
**Evidence:** token baked into `hx-headers` at render (`layout.py:255`); after restart, every mutation from a stale tab → 403 `CSRF token mismatch`; GETs keep working, reload recovers. Correctly fail-closed; just silent from the user's perspective (htmx gets 403, no auto-reload).
**Owner:** engineering — backlog: surface a reload hint on CSRF 403 (`HX-Refresh` on mismatch for htmx requests would be enough).

### F-6 — Low — Chaos-scenario test coverage gaps
**Location:** `tests/test_admin_dashboard.py` (34 tests — strong on 403/404/405/empty/unreadable/poll/geometry).
**Evidence:** no test asserts probe health while an admin handler fails (RS-104 parity), no bounded-refresh test (RS-103 parity), CDN-degradation untestable as-is (follows from F-1).
**Owner:** engineering — add RS-103/RS-104-style regression tests when F-2/F-3 are remediated.

## Verdict Rationale

**Conditional.** Core degradation promises hold under live chaos: empty registry, corrupt config, unreachable upstream, and 403/404/405 all degrade to honest UI states with probes serving throughout (RS-101..104 verified live; 34 admin tests green; suite 605 green on record). Three Medium findings keep this from a clean pass: the CDN single point of failure (F-1), the unbounded aggregate refresh window with inline 300 s OAuth wait (F-2), and false-green probes masking registry corruption (F-3). None is Critical/High — no exploit, no data loss, no outage. Gate stays conditional until each Medium is either remediated or recorded as an accepted risk with owner + justification + expiry (per guardrails §"Accepted risks"). Lows (F-4/F-5/F-6) go to backlog.

**Side note for the orchestrator:** during evidence gathering, `mcp-gway add Demo` was run without realizing `cli.py:22` pins the default registry (`~/.config/mcp-gway/servers`); it was removed immediately (`Removed Demo.`) and the user's 6 pre-existing servers verified intact. The live gateway ran against an isolated `--registry-dir` under `/tmp/opencode/rr`. Own-forward: disclosed here so the record is clean.
