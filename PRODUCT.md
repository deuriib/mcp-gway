# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: the MCP Gateway operator/developer running the gateway on their own machine, managing MCP server connections and monitoring gateway health.

_\(inferred from DESIGN.md brief + AGENTS.md; no interview conducted — user chose "Infer from brief"\)_

## Product Purpose

A complete admin web app for MCP Gateway: a 1:1 web equivalent of the `mcp-gway` CLI plus web-only additions (overview metrics, Code Mode explorer, observability views). Success means every CLI task is possible from the browser, with live gateway state visible at a glance.

_\(inferred from the explicit user request\)_

## Positioning

The dashboard is a second front-end on the same running gateway process — same registry, same policy gates, same audits as the CLI. Not a separate product, not a second source of truth.

_\(confirmed by "1:1 with cli in functionalities" + existing architecture\)_

## Operating Context

- Local-first: server binds `127.0.0.1`; non-loopback requires `MCP_GWAY_ALLOW_REMOTE=1`. The admin UI itself remains loopback-only (fail closed).
- Runs inside `mcp-gway serve --transport http|sse`; index route `/` (plus `/admin/`).
- Operator watches live telemetry: status bar polls the same process every 5s.
- External CDN dependency for Tailwind + htmx accepted by the user (requires network at page load).

## Capabilities and Constraints

- CLI parity: `add` (local|remote, all 13 flags), `remove`, `update`, `list`, `inspect`, `refresh [--auth]`, `local-unrestricted enable|disable|status`.
- Web additions: overview dashboard, Code Mode explorer (list/read/docs/execute), observability views.
- Stack: Python 3.12, htpy (server rendering), htmx via CDN, Tailwind via CDN, Starlette.
- Retired surfaces stay retired: no `/dashboard`, no `/api/servers`, no catalog (v2.0.0 decision preserved; admin ≠ catalog).
- Undecided: none material.

## Brand Commitments

- DESIGN.md Spotify-inspired system is binding: near-black surfaces (`#121212`–`#1f1f1f`), single green accent (`#1ed760`) used functionally only, pill/circle geometry, compact 10–24px type, uppercase tracked buttons, heavy shadows, achromatic UI.
- Icons are authored SVG with one consistent stroke — no emoji, no glyph stand-ins.

## Evidence on Hand

- `DESIGN.md` (repo root) — pinned visual system, user-authored.
- `AGENTS.md`, `CHANGELOG.md` — product facts, CLI surface, security posture.
- No user research, metrics, testimonials, or customer proof exists. Future work must not fabricate any.

## Product Principles

1. CLI and dashboard never diverge: same validation, same allow-list, same audit actions.
2. Deny by default, fail closed: CSRF on mutations, loopback-only admin, SSRF guard, secret masking.
3. Dark, dense, functional: every pixel serves the operator's task — an app, not a magazine.
4. Honest telemetry: live values labeled only when backed by the running process.

## Accessibility & Inclusion

No product-specific standard was established (inferred floor, not a user requirement): WCAG AA contrast ≥4.5:1, keyboard navigation with visible focus, `prefers-reduced-motion` respected, no color-only status encoding.
