# Resilience Review: admin-ui-3.1.0

**Reviewer:** review-resilience (engineering domain)
**Date:** 2026-09-23 (re-gated same day — current verdict: **conditional**, F-7 High open; see "Re-gate addendum 2026-09-23")
**Verdict:** conditional (initial run — findings F-1..F-6 below stand as written)
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

## Re-gate addendum 2026-09-23

**Reviewer:** review-resilience (engineering domain) — re-run sign-off
**Verdict:** conditional — gate **must not close** while F-7 (High) is open; F-1..F-3 (Medium) also remain pending waiver/backlog records.
**Scope:** read-only. Live GET/HEAD probes against the orchestrator's temp instance `http://127.0.0.1:8090` (registry `/tmp/opencode/gw-admin-check/servers`), source/test reads, plus exactly two sanctioned execute POSTs with **bounded** Starlark (2e7 / 5e7-iteration loops that self-recover — no infinite code; the server was never killed or restarted; no `mcp-gway` CLI invocations; no `~/.config/mcp-gway` access; no source edits; no commits). Zero secrets in this artifact (the ephemeral per-process CSRF token used for the probe is not recorded).
Own-forward: the first execute POST returned 403 `CSRF token mismatch` because my token extraction left the `X-CSRF-Token&#34;: &#34;` prefix in the value — extraction bug on my side, not a product defect; corrected extraction then passed the gate (43-char token). Disclosed for a clean record.

### Remediation verification — gate 3 Highs + CE-001

| Item | Status | Evidence (file:line / command output) |
|------|--------|----------------------------------------|
| REQ-H1 per-field OAuth merge | **verified** | `_oauth_field` blank+mask-sentinel→keep (`admin/routes.py:854-861`); per-field merge, all-blank leaves `data["oauth"]` untouched (`routes.py:945-954`); omission-safe (form.get→None→blank); every failure path exits via `_reject` toast/redirect, never 500 (`routes.py:840-851,888-889,955-958,967-970`); tests `test_admin_dashboard.py:553,578,604,627`. Static+test evidence (no live mutation — read-only posture). Degradation story: fail-closed toasts, no 500s — sound. |
| REQ-H2 fail-closed Host gate | **verified** | `_ALLOWED_HOSTS` (`routes.py:48`), `_normalize_host` fail-closed (`routes.py:104-126`), `_gate` Host check **before** CSRF/body parsing (`routes.py:129-146`). Live: `Host: evil.example.com` → **403** `<!doctype html><title>403</title><p>Admin is loopback-only.</p>` on `/admin`; `Host: 127.0.0.1:8090` and bare `127.0.0.1` → **200**; probes deliberately ungated: evil-Host `/health` → 200, `/metrics` → 200, `/mcp` GET → 405 `Allow: POST` (design-asserted `test_admin_dashboard.py:728-736`). Degradation semantics: distinct 403 body, gateway/MCP/probes keep serving while admin fails closed — correct. An already-open tab cannot carry a non-loopback Host (page render is gated too), so the 403 is forged-request-only; htmx swallows non-2xx silently — acceptable, no finding. Tests `:651,685,701`. |
| REQ-H3 execute timeout | **partial — refuted for CPU-bound code → F-7** | Branch exists: clamp (`routes.py:52-54,1090-1101`), `asyncio.wait_for(asyncio.to_thread(...))` (`routes.py:1156-1159`), toast/retarget surface (`routes.py:1104-1114`), warning log (`routes.py:1161-1165`); tests `:747,773,790,814,827`. Live probes show the bound does not hold — see F-7. |
| REQ-CE-001 toolbar floors | **verified** | Row `shrink-0`, both children `flex-1 md:flex-none` (`admin/pages/servers.py:211-231`); live `GET /admin/servers` contains the floor markup (1 match); test `test_admin_dashboard.py:841`. |

### Findings — updated rows (prior F-1..F-6: **fixed 0 / persisting 6**, of which 2 line-anchors moved)

| ID | Status | Sev | Location @ 2026-09-23 | Note |
|----|--------|-----|------------------------|------|
| F-1 | persist | Medium | `admin/layout.py:36-40` (CDN constants; rendered tags confirmed live: `GET /` → `https://cdn.tailwindcss.com`, `https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/...`) | No local fallback added. **No in-repo accepted-risk record** (owner+justification+expiry) found — `CHANGELOG.md:5` documents the CDNs as a feature, not as a risk acceptance. Waiver, if any, must live in the gate packet. |
| F-2 | persist (**moved**) | Medium | loop now `p_refresh_all` `routes.py:712-731` (sequential `await _refresh_one` at `:721-724`) via `_refresh_one` `routes.py:684-709` (`refresh_server` awaited `:700`); anchors unchanged: `core/client.py:353-356` (empty-discovery→needs_auth), `oauth.py:532` (`wait_for_callback(timeout=SSRF_IDLE_TIMEOUT)`), `models.py:28` (300.0 s) | Still no aggregate deadline; inline OAuth wait unchanged. Prior evidence stands. |
| F-3 | persist | Medium | `observability/health.py:13-27` — get_config failure swallowed `:19-24`, `return "ok"` `:25` | Unchanged; no live re-corruption this run (read-only mandate). RS-104 observation from the first run still stands. |
| F-4 | persist (**moved**) | Low | read `routes.py:883` → write `routes.py:968`; `registry.py:123` (`set_config`), `registry.py:178` (`update` re-read) | Accepted risk, documented last-write-wins. Line anchors updated from prior run (826/910). |
| F-5 | persist | Low | token `gateway.py:375` (unchanged); CSRF compare now `routes.py:96-101,147-153` | Backlog item (reload hint on CSRF 403) unchanged. |
| F-6 | persist — **restate as condition** | Low | `tests/test_admin_dashboard.py` now 48 tests; the 14 new ones are exactly the fix-scoped set: OAuth merge `:553,578,604,627`, Host gate `:651,685,701,728`, execute timeout `:747,773,790,814,827`, toolbar `:841` | **Zero new RS-style chaos tests**: no probe-health-during-corruption test (F-3 parity), no bounded/aggregate refresh test (F-2 parity), no CDN-degradation test (F-1 parity). `test_edgecases_observability.py:23` (`check_registry`) is pre-existing and list()-only; CDN tests (`test_admin_dashboard.py:47`, `test_edgecases_gateway.py:65,330`, `test_wave2_api.py:31`) only assert CDN *presence*. Condition unchanged: add RS-103/RS-104-parity tests when F-2/F-3 are remediated. |

### New findings

### F-7 — High — Execute "timeout" does not bound CPU-bound snippets; the whole gateway stalls for the full eval duration
**Location:** `admin/routes.py:1156-1159` (`wait_for(to_thread(...))`); `sandbox.py:99-101,110-113` (`sl.eval` inside inner `ThreadPoolExecutor`); claim refuted: `routes.py:1093-1094` ("neither pin the route open nor starve it") and `routes.py:1108` ("the snippet was abandoned").
**Evidence (live, temp instance):** POST `/admin/partials/codemode` `mode=execute`, `timeout=0.5`, Starlark `for i in range(50000000)` → response wall **11 890 ms** with `HX-Retarget: #toast` and body `Execution timed out after 0.5s — the snippet was abandoned.` — the toast arrived only at eval end, not at 0.5 s. Concurrent `GET /health` issued 0.7 s into the run took **11 194 ms** (blocked until eval end); the next health call took 3 ms (loop recovered immediately). A 2e7-iteration run showed the same pattern (wall 4 440 ms for a 0.5 s timeout). Interpretation: `asyncio.wait_for` cannot fire while the event loop is starved for the eval — consistent with starlark eval holding the GIL across `sandbox.py:110-113` — so for CPU-bound code neither the route bound nor loop liveness holds; probes, `/mcp`, and all admin surfaces stall together (RS-101's "probes serve throughout" breaks during execute). No in-repo recovery bound for an unbounded snippet; whether `starlark-pyo3` (`pyproject.toml:15`, `>=2026.1.1`) has an internal step/interrupt limit is **unverified** (package not importable from the ambient interpreter; not re-checked via env-mutating commands under the read-only mandate) — treat as unbounded until the owner confirms. Secondary facet: for GIL-releasing slow work the timeout *does* fire (test `:747` sleep-path), but the abandoned `to_thread` worker plus the inner sandbox thread keep running until completion (`sandbox.py:110` `shutdown(wait=True)` waits on it) — an orphan bounded by the snippet's own duration.
**Impact:** gateway-wide availability stall triggerable by one pasted long loop; contradicts the remediation's own claim. Trigger requires loopback + CSRF (operator-triggered, conditional), but impact is unbounded → High.
**Owner:** engineering. Verify `starlark-pyo3` interrupt support; enforce the bound at a layer that does not depend on a live event loop (e.g., a sandbox-level step/time limit before or inside eval that can actually interrupt); reword the toast/docstring until then. Reporting only — no fix attempted (no freelance fixes).

### O-1 — Low (observation; out of admin-ui-3.1.0 scope — route to security/gateway domain) — Host gate deliberately excludes `/mcp` and probes
**Location:** design-asserted `tests/test_admin_dashboard.py:728-736`; live: evil-Host `/mcp` GET → 405 (not 403), `/metrics` → 200.
**Evidence:** DNS-rebinding page (Host = attacker domain → 127.0.0.1) is blocked on every admin surface (verified) but reaches the MCP transport under the loopback-auth model. Pre-existing design, **not introduced** by REQ-H2; residual-risk note for the security reviewer, no gate condition raised from this domain.
**Owner:** security/gateway.

### Stress scenario rows — re-run 2026-09-23

| ID | Scenario | Expected | Observed | Pass? |
|----|----------|----------|----------|-------|
| RS-101 | Probes/index during normal ops | 200s | `health=200 index=200`, post-probe `health 2-3 ms` | yes |
| RS-105 | CDN dependence | — | live `GET /` still references `cdn.tailwindcss.com` + `cdn.jsdelivr.net` only | no (F-1 persists) |
| RS-106 | Refresh-all aggregate deadline | — | static re-read: loop unchanged, no budget (`routes.py:721-724`) | no (F-2 persists) |
| RS-108 (new) | Host-gate degradation semantics | evil Host → 403 on admin; probes/MCP unaffected; loopback ±port → 200 | `evil-admin=403` (distinct body), `evil-health=200`, `evil-metrics=200`, `evil-mcp-get=405`, `port-admin=200`, `bare-admin=200` | yes |
| RS-109 (new) | Execute-timeout bound + probe liveness under load | response ≈ 0.5 s; probes keep answering | response **11 890 ms**; health blocked **11 194 ms** (5e7 iters); toast text correct but late | **no (F-7)** |

### Verdict rationale (re-gate)

**Conditional.** Three of four remediations are sound and verified (REQ-H1 merge, REQ-H2 Host gate, CE-001 floors — source + 14 fix-scoped tests + live probes). REQ-H3 delivers the response surface but its core resource-bound claim is **empirically refuted for CPU-bound snippets** (F-7, High: measured 11.9 s response for a 0.5 s timeout and an 11.2 s full-gateway stall). Prior findings: **0 fixed, 6 persisting** (F-2/F-4 line-anchors moved; F-1..F-3 Mediums still lack in-repo accepted-risk records with owner+justification+expiry; F-6 restated as the standing condition tied to F-2/F-3). F-7 blocks closure: remediate, or orchestrator + engineering owner waive explicitly with recorded justification and expiry. This domain does not pass the gate while a High it verified as refuted remains open.
