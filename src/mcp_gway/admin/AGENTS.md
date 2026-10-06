# admin — AGENTS

`DOMAINS: Security & Privacy, Engineering`

## OVERVIEW

Server-rendered dashboard (htpy + htmx + Tailwind CDN); loopback-only management UI, CLI stays canonical.

## WHERE TO LOOK

| Task | Location | Notes |
| Loopback + CSRF gate | `routes.py` (`_gate`) | 403 off-loopback, token per process |
| Pages/partials | `pages/` | status/overview/servers/tools/observability/policy |
| Shared chrome | `layout.py`, `components.py`, `theme.py`, `icons.py` | SVG authored, no secrets in bundle |
| Row data | `data.py` | headers/OAuth masked in detail views |

## GUARDRAILS (THIS DIR)

- Every mutation needs CSRF (`X-CSRF-Token` or `_csrf` field).
- OAuth never runs inline — background task with `refresh --auth` parity.
- Single relaxed `CSP` lives in `gateway.py`; no inline secrets.

## ANTI-PATTERNS

- No `dangerouslySetInnerHTML` without sanitizing; no tokens in markup.
