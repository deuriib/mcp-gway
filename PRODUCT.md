# Product

<!-- impeccable:product-schema 1 -->

## Platform

cli + local service + web dashboard

## Users

Primary: agent developers wiring Pi / Antigravity / Claude / Cursor to many MCP servers through one gateway endpoint — schemas served on demand, not all loaded upfront.

Secondary: the operator running the gateway on their own machine, managing server connections and monitoring health via CLI (canonical) plus dashboard.

_\(inferred from DESIGN.md brief + AGENTS.md; no interview conducted — user chose "Infer from brief"\)_

## Product Purpose

One MCP endpoint for every server an agent needs. MCP Gateway aggregates remote/local servers behind a single headless HTTP/SSE endpoint; Code Mode (4 meta-tools) serves tool schemas on demand and executes in a hermetic Starlark sandbox. Success means agents fetch only the schemas they use, and operators manage one registry from the CLI with dashboard parity.

_\(inferred from the explicit user request\)_

## Positioning

The gateway is the product; the dashboard is a second front-end on the same running process — same registry, same policy gates, same audits as the CLI. Not a separate product, not a second source of truth.

_\(confirmed by "1:1 with cli in functionalities" + existing architecture\)_

## Operating Context

- Local-first: server binds `127.0.0.1`; non-loopback requires `MCP_GWAY_ALLOW_REMOTE=1`. The admin UI itself remains loopback-only (fail closed).
- Runs inside `mcp-gway serve --transport http|sse`; index route `/` (plus `/admin/`).
- Operator watches live telemetry: status bar polls the same process every 5s.
- External CDN dependency for Tailwind + htmx accepted by the user (requires network at page load).

## Capabilities and Constraints

- CLI parity: `add` (local|remote, full flags), `remove`, `update`, `list`, `inspect`, `refresh [--auth]`, `--version`/`-v`, `serve --transport stdio|http|sse`. No `local-unrestricted` — removed in v4.0.0, no bypass exists.
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

1. Gateway first, CLI canonical, dashboard in parity: same validation, same explicit allow-list (`MCP_GWAY_ALLOW_LOCAL_COMMANDS`, do not rename), same audit actions. No bypass.
2. Deny by default, fail closed: CSRF on mutations, loopback-only admin, SSRF guard, secret masking.
3. Dark, dense, functional: every pixel serves the operator's task — an app, not a magazine.
4. Honest telemetry: live values labeled only when backed by the running process.

## Accessibility & Inclusion

No product-specific standard was established (inferred floor, not a user requirement): WCAG AA contrast ≥4.5:1, keyboard navigation with visible focus, `prefers-reduced-motion` respected, no color-only status encoding.
