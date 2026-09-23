# Risk Review: admin-ui-3.1.0 (interactive batch, no formal spec)

**Reviewer:** review-risk (engineering domain)
**Date:** 2026-09-23
**Verdict:** conditional

## Checklist

- [x] Blast radius analysis bounded and verified — CLI/SSE/HTTP/probes verified below; one inventory mismatch found (RK-002)
- [~] Backward compatibility preserved — additive routes + header-value change, documented in API_CONTRACTS/CHANGELOG, but no ADR (RK-003, Low)
- [~] Dependencies pinned; zero CVEs — `pip-audit` clean (29 pkgs, incl. htpy 26.5.1); htmx pinned @2.0.10 with sha384 SRI; Tailwind CDN unpinned/no SRI (RK-001, Medium)
- [~] Rollback determinism proven (≤15 min) — mechanically simple but **not proven**: all changes are UNCOMMITTED, no atomic revert artifact exists yet (RK-004, Medium)
- [x] Architectural contract invariants intact — INV-010 loopback preserved; admin `_gate` fails closed on non-loopback `serve_host` (`src/mcp_gway/admin/routes.py:46,94-100`; `ARCHITECTURE.md:72`)
- [x] Zero unmitigated regression risk across touched systems — 605 tests green, ruff green, route counts executed and match docs; residuals named in RK-001/RK-004

## Risk Assessment Matrix

| ID | Risk Dimension | Impact | Likelihood | Mitigation | Residual |
|----|----------------|--------|------------|------------|----------|
| RK-001 | Supply chain: Tailwind CDN script unpinned, no SRI, granted by global CSP relaxation on **every** response | Med | Low | htmx pinned+SRI; CSP `script-src` limited to jsDelivr+Tailwind only; admin loopback-only + CSRF on mutations | Med (conditional impact: needs CDN compromise + operator visiting dashboard) |
| RK-002 | Inventory/rollback scope: working tree contains untracked `.impeccable/` + `PRODUCT.md` **not** in packet inventory; blanket `git clean` rollback would destroy them | Med | Med (if rollback done bluntly) | Selective rollback documented below; packet inventory otherwise matches `git status` | Low |
| RK-003 | Contract shift without ADR: `/` went 404 → 200 (admin index) and `Content-Security-Policy` value changed from `default-src 'self'` for all consumers | Low | High (already shipped in tree) | Documented in `docs/specs/10_design/API_CONTRACTS.md:21-23`, `CHANGELOG.md:5`, test renamed honestly (`tests/test_gateway.py:247`); legacy `/dashboard`,`/api/*`,`/static` still asserted 404 | Low (needs ADR note or orchestrator waiver) |
| RK-004 | Rollback determinism: entire batch UNCOMMITTED — no revert commit/tag exists; ship from dirty state risks partial commit | Med | Med | Rollback procedure is mechanical (<15 min) **after** commit; see below | Med until committed |
| RK-005 | Dependency bound: `htpy>=26.5.1` unbounded upper on a CalVer package, propagates to PyPI consumers | Low | Low | `uv.lock` pins 26.5.1 for dev/CI; pip-audit clean; htpy is 21 KB, deps = markupsafe only | Low |
| RK-006 | Availability: dashboard requires internet at runtime (htmx + Tailwind CDN); offline/air-gapped operators get degraded UI | Low | Med (offline ops) | Server-rendered HTML + non-hx 303 form fallbacks keep core mutations usable without JS | Low |
| RK-007 | Maintenance burden: `admin/` ≈ 3,520 new LOC; `routes.py` alone 1,159 LOC (single hotspot) + 519-LOC test file | Low | High (ongoing churn) | Loopback+CSRF centralized in one `_gate` (`routes.py:94`); 34 admin tests | Low (backlog: split routes.py when churn hurts) |

## Blast Radius Verification (evidence)

- **CLI parity:** `src/mcp_gway/cli.py` diff = banner line only (+3). `Registry.add` refactored to shared `_config_data` (`registry.py:83-121`) — output payload unchanged; `set_config` (`registry.py:123-130`) writes `.json` only, never `.pyi` (test `tests/test_registry.py:213-221` proves `.pyi` bytes unchanged).
- **Transports/probes:** executed route counts — `transport="http"` → **30** entries, `transport="sse"` → **31** entries, matching `AGENTS.md` (24 admin routes = 7 pages + 17 partials). Probe paths/handlers unchanged (`gateway.py:356-359` diff adds only `*create_admin_routes()`); `/health` tests green in `tests/test_edgecases_gateway.py`.
- **Metrics cardinality:** `path_template` collapses `/admin/*` to a fixed set with `/admin` fallback (`observability/middleware.py:42-58`), asserted `tests/test_admin_dashboard.py:350-358`.
- **CSP:** single constant `CSP` (`gateway.py:38-49`) replaces inline literal; `<=2`-literals test still intact; 3 migrated asserts (`test_edgecases_gateway.py:62-65,324-327`, `test_wave2_api.py:24-31`).
- **Regression suite:** `uv run pytest -q` → **605 passed**; `ruff check` → `[]`; `ruff format --check` → 89 files formatted (re-run this session).
- **CVEs:** `pip-audit` over exported runtime deps → *No known vulnerabilities found*.
- **Security controls (observed, ruled by review-security, not this reviewer):** `_gate` loopback+CSRF (`routes.py:94-110`, `hmac.compare_digest`), per-process token `secrets.token_urlsafe(32)` (`gateway.py:375`), SSRF revalidation on config save + `check_local_command` allow-list + audit on add/update/refresh (`routes.py:511,569,632`), break-glass env-var still required for activation (`routes.py:p_policy_enable`).

## Rollback Procedure (RK-004 — deterministic only after commit)

1. `git restore AGENTS.md CHANGELOG.md README.md docs/specs/10_design/API_CONTRACTS.md pyproject.toml uv.lock src/mcp_gway/cli.py src/mcp_gway/gateway.py src/mcp_gway/observability/middleware.py src/mcp_gway/registry.py tests/*` (modified set, exact list from `git status`)
2. Delete **only** `src/mcp_gway/admin/`, `tests/test_admin_dashboard.py` (untracked, in inventory)
3. `uv sync --all-groups` (drops htpy per restored `uv.lock`)
4. `uv run pytest -q` sanity (expect 571 pre-batch tests)
5. **Do NOT run blanket `git clean -fd`** — it would destroy untracked `.impeccable/` and `PRODUCT.md` (out of inventory, presumed user/other-agent work).

Estimated <15 min — **condition:** a commit must exist first; today the tree is dirty, so step 0 is "commit the batch as one atomic commit".

## Verdict Rationale

**conditional** — no Critical/High findings; nothing here blocks on exploitability or data loss. Two Medium conditions must be dispositioned before ship:

1. **RK-001** (owner: engineering): pin/vendor the Tailwind CDN script or record it as an accepted risk with expiry — current state grants an unpinned, non-SRI script origin-wide execution rights via the relaxed CSP.
2. **RK-004** (owner: engineering): commit the batch atomically (single work-unit commit) to create the revert artifact; confirm `.impeccable/` + `PRODUCT.md` are intentionally excluded from scope.

Lows (RK-003 ADR-or-waiver, RK-005 upper bound, RK-006 offline note, RK-007 routes.py split, plus the doc mismatch: `API_CONTRACTS.md:23` claims *16 partials / 23 Route objects* but executed count is **17 partials / 24 admin routes** — `AGENTS.md` 24→30/31 is correct) go to backlog with owner = engineering.

Zero secrets/PII in this artifact.

---

## Re-gate addendum 2026-09-23

**Reviewer:** review-risk (engineering domain) — re-run after remediation cycle (gate 3 Highs + CE-001 only; Mediums owner-deferred to backlog).
**Verdict (re-gate): conditional — unchanged from 2026-09-23.**

**Counts:** my findings **fixed: 0 / persisting: 8** (matrix RK-001..RK-007 + doc-mismatch — none were in remediation scope) **+ new from fix-assessment: 2** (RK-008 Medium, RK-009 Low). Gate Highs + CE-001 fixes verified present in passing (evidence below) but are not this reviewer's findings.

### Checklist delta (re-run this session)

- [x] Blast radius — remediation sites confined to `admin/routes.py` + `admin/pages/servers.py` + tests; `cli.py` diff still banner-only (+3, re-verified); route topology re-executed: **http 30 / sse 31 / admin 24 — unchanged** (remediation added zero routes); `/health` unaffected under evil Host.
- [~] Backward compat — RK-003 persists (no ADR: `docs/adr/`, `docs/architecture/` don't exist; only ADR on disk is `docs/specs/12_adr/ADR-013`; grep NO_ADR_MATCH). Host-gate adds a new 403 condition on admin only → folds into doc-mismatch + new RK-009.
- [~] Dependencies — `uvx pip-audit` re-run: *No known vulnerabilities found* (29 pkgs); htmx pinned+SRI (`layout.py:36-39`); **RK-001 persists**: Tailwind unpinned/no-SRI (`layout.py:40`, `layout.py:242`) granted by `script-src` on every response (`gateway.py:44`).
- [~] Rollback — **RK-004 persists by design** (still uncommitted; last commit `91dd912` = gate report only) → **reclassified: WAIVER candidate**, see below.
- [x] Arch invariants — INV-010 intact; `_gate` now fail-closed on Host (`routes.py:129-146`) — stronger than before.
- [~] Zero unmitigated regression — suite **619 passed** (605+14 ✓), `ruff check` `[]`, format 89 files, all re-run independently. Fix-assessment surfaced RK-008 (thread abandonment) + RK-009 (alias 403).

### Fix-assessment (new risk introduced by the remediation itself)

- **REQ-H1 OAuth merge** (`routes.py:854-861`, `945-954`): per-field merge with mask sentinels treated as blank; byte-identical preservation proven (`tests/test_admin_dashboard.py:553-626`, mask test `:627`). CLI parity **intact** — merge is admin-write-path only; CLI `add`/`refresh` untouched (`cli.py` diff +3 banner). Limitation (Low, backlog): web cannot *clear* an OAuth field (blank = keep); pathological secret made only of `•`/`*` cannot be set. No security regression.
- **REQ-H2 Host gate** (`routes.py:48`, `104-126`, `129-146`, `p_empty:1197-1201`): fail-closed verified live — `Host: evil.example.com` → 403 on `/` and `/admin/partials/status`; `localhost` → 200; `/health` 200 + `/mcp` 405 under evil Host (`tests/test_admin_dashboard.py:728-736`). **Does NOT break** standard loopback access (127.0.0.1 / localhost / ::1 / [::1] all allowed, port-stripped). **Does break** custom loopback aliases (`myhost`→127.0.0.1 in hosts-file, `localhost.` FQDN form) → 403 → new **RK-009** (Low): dashboard-only, CLI/MCP/probes unaffected, workaround = use standard names; docstring documents intent (`routes.py:130-135`) but `API_CONTRACTS.md:23` still describes only the `serve_host` condition → doc gap.
- **REQ-H3 execute timeout** (`routes.py:1090-1101`, `1104-1114`, `1150-1171`; notice `routes.py:68-71`): user-facing bound works (toast at ≤30 s, clamp tests `:814-824`). **Thread-leak risk is REAL → new RK-008 (Medium):** `asyncio.wait_for(asyncio.to_thread(...))` at `routes.py:1156-1159` abandons the worker — `to_thread` cancellation never stops a running thread; sandbox runs `_run` in `ThreadPoolExecutor(max_workers=1)` as a **context manager** (`sandbox.py:110-119`), so `future.result(timeout)` raising on a non-terminating loop leads to `__exit__ → shutdown(wait=True)` which **blocks forever**: (a) the "abandoned" snippet keeps executing and burning CPU (GIL is released during `sl.eval` — proven by `tests/test_admin_dashboard.py:773-787` returning the 0.1 s toast mid-loop), (b) each event leaks one default `to_thread` worker (pool ≈ `min(32, cpu+4)`); after enough events admin execute degrades to permanent misleading timeouts, (c) non-daemon workers are joined at interpreter exit → graceful shutdown can hang after such events. Test only proves a *finite* 100M loop terminates — no test covers non-termination. Pre-existing sandbox characteristic (also reachable via `/mcp` executeToolCode, `gateway.py:786`), and the fix still strictly improved availability vs. the prior event-loop freeze — but it must be dispositioned (fix = e.g. daemon worker / `shutdown(wait=False, cancel_futures=True)` in `sandbox.py:110`, engineering's call; or accept + document that "abandoned" ≠ "stopped"). Owner: engineering.
- **REQ-CE-001 toolbar floors** (`servers.py:211-231`): container `shrink-0` + children `flex-1 md:flex-none` (`:211,212,228`), asserted `tests/test_admin_dashboard.py:841-850`. Cosmetic, zero residual risk.

### Updated risk matrix rows

| ID | Risk Dimension | Impact | Likelihood | Mitigation | Residual |
|----|----------------|--------|------------|------------|----------|
| RK-001 | Supply chain: Tailwind CDN unpinned/no-SRI + global CSP relaxation | Med | Low | htmx pinned+SRI; loopback+CSRF | **Med — PERSISTS** (owner: engineering; fix or waiver+expiry) |
| RK-002 | Inventory/rollback scope: untracked `.impeccable/`, `PRODUCT.md`, **+ `docs/specs/40_workspace/execute/` (new)** not in packet inventory | Med | Med (blunt rollback) | Selective rollback procedure below | Low — PERSISTS (backlog) |
| RK-003 | Contract shift (`/` 404→200, CSP value) without ADR | Low | High | Documented `API_CONTRACTS.md:23`, `CHANGELOG.md:5`, honest test rename `tests/test_gateway.py:247`; live `/`→200, `/dashboard`→404 | Low — PERSISTS (no ADR exists; needs waiver or ADR note) |
| RK-004 | Rollback determinism: batch UNCOMMITTED, no revert artifact | Med | Med | Mechanical <15 min rollback below | **Med — PERSISTS by standing instruction → WAIVER candidate** (owner: user standing instruction / engineering execution; justification: user-directed uncommitted batch; **expiry: before first v3.1.0 release tag** — no ship from dirty tree) |
| RK-005 | `htpy>=26.5.1` unbounded upper (CalVer) `pyproject.toml:12` | Low | Low | `uv.lock:529-538` pins 26.5.1; pip-audit clean (re-run) | Low — PERSISTS (backlog) |
| RK-006 | Dashboard needs internet (htmx+Tailwind CDN) | Low | Med | SSR HTML + non-htmx 303 fallbacks | Low — PERSISTS (backlog) |
| RK-007 | `routes.py` hotspot, now **1,249 LOC** (+90 by fixes) | Low | High | Central `_gate`; 48 admin tests (+14) | Low — PERSISTS (backlog) |
| doc-mismatch | `API_CONTRACTS.md:23` claims *16 partials / 23 Route objects*; actual **17 partials / 24 Route objects** (re-counted `routes.py:1207-1248`, re-executed http 30 / sse 31 / admin 24); line also omits Host-gate 403 condition | Low | High | `AGENTS.md:151` correct (24→30/31) | Low — PERSISTS (backlog) |
| **RK-008 (new)** | Availability: timeout abandons but does not stop Starlark worker — CPU burn, `to_thread` pool drain, shutdown hang after non-terminating code (`routes.py:1156-1159`, `sandbox.py:110-119`, `code_mode.py:84,301`) | Med | Low (loopback+CSRF+pathological snippet) | wait_for bounds UX; server stays up (strict improvement over prior freeze); finite loops covered by test | Med — NEW, needs disposition (fix or accept+document; owner: engineering) |
| **RK-009 (new)** | Host gate 403s custom loopback aliases (`myhost`→127.0.0.1, `localhost.`) (`routes.py:48,136`) | Low | Low (uncommon alias use) | Standard names work; CLI/MCP/probes unaffected (test `:728-736`) | Low — NEW (backlog: document in `API_CONTRACTS.md`) |

### Conditions to clear this verdict (fix vs waiver — restated)

1. **RK-001 — FIX or WAIVER** (owner: engineering): pin/vendor the Tailwind script (`src/mcp_gway/admin/layout.py:40`, tag `layout.py:242`, CSP `src/mcp_gway/gateway.py:44`) **or** record accepted risk with owner + justification + expiry per guardrails. Currently neither → persists.
2. **RK-004 — WAIVER (reclassified from fix)**: the atomic-commit condition **cannot clear by design** under the standing uncommitted-tree instruction. Needs a recorded waiver: owner = user (standing instruction), execution = engineering at ship time, expiry = **before first v3.1.0 release tag** (rollback artifact must exist before any release; evidence: `git status` — all batch files M/??, last commit `91dd912` gate-report only).
3. **RK-008 — FIX or ACCEPT+document** (owner: engineering): bound the abandoned worker in `src/mcp_gway/sandbox.py:110` / accept with documented "abandoned ≠ stopped" + bounded-snippet guidance. Currently undispositioned → new Medium condition.

Lows → backlog with owner = engineering: RK-002 (add `execute/` to rollback inventory), RK-003 (ADR note or waiver), RK-005 (upper bound), RK-006, RK-007 (split `routes.py`), doc-mismatch (17/24 + Host-gate condition), RK-009 (alias note).

### Blast radius of the remediated set (verified this session)

Fixes touch only `src/mcp_gway/admin/routes.py` (Host gate, OAuth merge, exec timeout), `src/mcp_gway/admin/pages/servers.py` (toolbar), and tests — route topology re-executed **http 30 / sse 31 / admin 24 (unchanged)**; `cli.py` diff still `+3 -0` banner only; non-admin surfaces provably unaffected under evil Host (`tests/test_admin_dashboard.py:728-736`); OAuth merge cannot reach CLI/registry paths (admin write path only). Suite re-run: **pytest 619 passed**, `ruff check` `[]`, `ruff format --check` 89 files, `uvx pip-audit` clean (29 pkgs). Live server probed read-only: `/`→200, `/health`→200, `/dashboard`→404, evil-Host → 403 on admin surfaces. Residual blast radius = RK-008 (process-local thread/CPU after pathological admin snippets) and RK-009 (custom-alias operators lose dashboard access only). Zero secrets/PII in this artifact.
