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
