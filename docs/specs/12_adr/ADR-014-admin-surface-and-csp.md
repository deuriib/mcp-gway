# ADR-014: Admin dashboard surface at `/` and single relaxed CSP

**Date:** 2026-09-23
**Status:** Accepted (v3.1.0 Unreleased)

## Context

v2.0.0 retired the legacy dashboard and left `/` returning 404. The v3.1.0
batch reintroduces a management UI (htpy + htmx 2.0.10 + Tailwind, all CDN)
which is a public-contract change: `/` becomes the admin index (plus `/admin*`,
30 routes http / 31 sse) and the CSP header value changes for every response.
This shifts the contract documented in `API_CONTRACTS.md` and needs a durable
decision record (flagged by the risk review, RK-003).

## Decision

1. `/` serves the admin dashboard index; `/dashboard` and catalog endpoints
   remain retired (404). CLI stays canonical; the web is for management only.
2. A single relaxed `CSP` constant in `gateway.py` allows the two CDNs
   (`script-src` jsDelivr + cdn.tailwindcss.com, `style-src 'unsafe-inline'`,
   `frame-ancestors 'none'`). htmx is SRI-pinned; Tailwind cannot be (runtime
   compiler) — accepted as waiver **W-02** with vendoring before the first
   v3.1.0 tag.
3. The relaxed surface is compensated by three fail-closed gates: loopback-only
   `_gate` (403 on non-loopback `serve_host`), per-process CSRF on every
   mutation, and fail-closed `Host` validation (only `127.0.0.1`, `localhost`,
   `::1`, `[::1]`; evil Host → 403 on all 24 admin routes — anti-DNS-rebinding).

## Consequences

- Consumers of `/` see 200 instead of 404; `path_template` collapses
  `/admin/*` to bound metric cardinality.
- Multi-user hosts share admin trust (waiver W-13, expires v3.1.0 GA).
- Full evidence and waivers: `docs/specs/40_workspace/quality-gate/admin-ui-3.1.0/GATE_REPORT.md`.
