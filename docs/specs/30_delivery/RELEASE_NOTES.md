# Release Notes: v3.1.0 — Admin Dashboard (management UI at `/`)

**Date:** 2026-09-23
**Release Manager:** orchestrator / operations owner function
**Specs Included:** admin-ui-3.1.0 (interactive lane — no source spec in `20_backlog`)
**Domains-Touched:** engineering, security (+ data lens)
**Ship Type:** deploy (new user-facing surface on a local-first service; internal release, no external announcement)

---

## Highlights

- **Admin web dashboard, CLI parity.** New `src/mcp_gway/admin/` package (htpy 26.5.1 + htmx 2.0.10 + Tailwind CDN, Spotify aesthetic from `DESIGN.md`) spliced into `Gateway` for both transports: index `/` + `/admin` alias + 7 pages + 17 `/admin/partials/*` htmx endpoints (24 `Route` objects, 30 http / 31 sse total). Manages servers (add/remove/list/inspect/refresh), Code Mode tools explorer (list/read/docs/execute), observability, and break-glass policy — CLI stays canonical; `update` (tools) remains CLI-only; `/dashboard` + catalog stay 404.
- **Three gate Highs remediated and re-proven.** OAuth partial-edit credential wipe fixed (per-field merge, blank = keep, mask sentinel = blank — sha256 byte-identity 30/30) · `Host` header fail-closed on all 24 admin routes (evil Host 200 → **403**, anti-DNS-rebinding; 25 hostile probes, CSRF token in zero non-admin bodies) · Code Mode execute timeout real (`wait_for(to_thread)`, clamp [0.1,30]s default 10, `exec-timeout` toast/notice).
- **Verified full-wave.** 8 independent gate reviewers (readability, reliability, refuter, resilience, risk, QA, security, data — 1 subagent each) × 3 passes (first → remediation re-gate → round-2 re-check); **gate OPEN** with 13 three-block C3 waivers (W-01..W-13); suite **621 passed**, coverage **82.79%**, ruff check+format clean; refuter's rebinding/width/token attacks independently re-measured.

---

## Changes

### Features

- Admin dashboard package + route splice: 6 pages (`/`, `/admin`, `/admin/servers[/{name}]`, `/admin/tools`, `/admin/observability`, `/admin/policy`) + 17 partials (status polling 5s, server grid/CRUD/refresh/auth, config edit `PUT .../{name}/config`, tools read-only, break-glass enable/disable, metrics) (admin-ui-3.1.0, engineering) — `src/mcp_gway/admin/`
- `registry.set_config()` — paired atomic `.pyi`+`.json` write powering web config edits (admin-ui-3.1.0, engineering) — `src/mcp_gway/registry.py`
- Serve banner gains `Dashboard → http://host:port/` line (admin-ui-3.1.0, engineering) — `src/mcp_gway/cli.py`
- Toolbar equal-width action row on mobile/tablet (REFRESH ALL / ADD SERVER Δ=0 at 375/390/414/600) (REQ-CE-001, engineering) — `src/mcp_gway/admin/pages/servers.py:211`

### Fixes

- OAuth config partial edit no longer wipes `clientId`/`clientSecret` (REQ-H1) — `src/mcp_gway/admin/routes.py` `_oauth_field` + merge
- Fail-closed `Host` gate: only `{127.0.0.1, localhost, ::1, [::1]}` on admin routes (REQ-H2) — `src/mcp_gway/admin/routes.py` `_normalize_host`/`_gate`
- Execute timeout enforced under thread offload + honest docstring (REQ-H3 / CE-007) — `src/mcp_gway/admin/routes.py` `_exec_timeout`
- Local-branch config PUT covered by `admin_update` allow-list tests (QA F-01) + exact-set host test (QA F-07) — `tests/test_admin_dashboard.py`

### Domain Ships

- Engineering: gate OPEN with 8 full-wave reviews + C3 waivers W-01..W-13 — `docs/specs/50_archive/admin-ui-3.1.0/GATE_REPORT.md`
- Security: rebinding exfil chain proven dead (24/24 admin routes gated, token never leaks cross-host); STRIDE full history (3 Highs first round → fixed → conditional → waived) — `docs/specs/50_archive/admin-ui-3.1.0/quality-gate/security-reviewer.md`
- Data: masking/atomicity/.pyi-isolation/token-unlink re-verified (DAT-001 closed, sha256 byte-identity); credential-field purpose/TTL/deletion declared (W-05) — `docs/specs/50_archive/admin-ui-3.1.0/quality-gate/review-data.md`

### Breaking Changes

- **`/` now serves the admin index (was 404 since v2.0.0), and the CSP response header changes** to allow the two CDNs (`script-src` jsDelivr + cdn.tailwindcss.com, `style-src 'unsafe-inline'`, `frame-ancestors 'none'`) — **Migration:** none for CLI/stdio/mcp clients; anything probing `/` expecting 404 must update; decision record + compensating controls: `docs/specs/12_adr/ADR-014-admin-surface-and-csp.md`.
- **Admin routes validate `Host` fail-closed** — a reverse proxy or client presenting a non-loopback `Host` (LAN IP, DNS name) to `/admin*` now gets 403 (was 200). — **Migration:** browse the dashboard from loopback with a loopback Host (normal local use is unaffected); `/mcp`, probes, and stdio paths do not gate `Host`. Impact window was the DNS-rebinding exfil path (SEC-001).

---

## Known Issues

Waivers with full three-block records in `docs/specs/50_archive/admin-ui-3.1.0/GATE_REPORT.md` (W-01..W-13); defaults expire **2026-12-22** unless noted.

- **W-01 (High):** CPU-bound Starlark eval can still delay the execute response and briefly stall the local event loop; post-timeout worker may keep burning CPU — core sandbox lacks interrupt/step-limit. Compensating: loopback+CSRF-only trigger, clamp [0.1,30]s, honest docstring (owner: core, expiry: core release or 2026-12-22).
- **W-02:** `cdn.tailwindcss.com` unpinned, no SRI possible (runtime compiler) + CSP lacks `form-action`/`base-uri` — vendor/pin before first v3.1.0 tag (owner: engineering + security).
- **W-03:** non-UUID user-typed OAuth `clientId` is uuid4-coerced (`models.py:692`, pre-existing) — v3.1.1 (owner: models).
- **W-04:** feature tree ships as one release commit — must land before first v3.1.0 tag (owner: orchestrator at release).
- **W-05..W-13:** credential-field doc mirror (pre-tag), raw-500 error surfaces, dead `oauth_port` field, absent-field PUT semantics, refresh-all N×300s aggregate, false-green `/health` on corrupt registry, registry schema drift (`retry_on_transport_error` no-op + no `schema_version`; immediate re-review if any writer lands), readability hygiene deferrals, no auth beyond loopback (expires **v3.1.0 GA** → escalate to High if a shared-host deployment model appears).
- Backlog Lows (not waived): 320px toolbar Δ5.4 cosmetic, ragged button heights in a ~389–403px band, 404-vs-405 on tools PUT path, `API_CONTRACTS` count note, no `pytest-timeout` (O-1), empty-state copy, no toast auto-dismiss.

## Rollback / Undo

- **Code:** `git revert <release-commit>` of the v3.1.0 commit restores the v3.0.1 tree — the admin package is additive, spliced via `create_admin_routes()`; no registry schema, env var, token file, or config path changed (verified by risk + data reviews). Pre-ship: discard the working tree per the inventory in `GATE_REPORT.md` W-04 (preserve out-of-inventory untracked `.impeccable/`, `PRODUCT.md`). Recovery <10 min.
- **PyPI:** `pip install mcp-gway==3.0.1` pins the previous behavior (no dashboard, `/` → 404, no Host gate).
- **Release:** `sync_version.py` owns `pyproject.toml` + `__init__.py` + `uv.lock` atomically at build (`--check` gates CI); a failed release leaves 3.0.1 intact (no partial bump). Tag push (`v*`) triggers `uv build` + `pypi-publish` — untagged = unpublished.
