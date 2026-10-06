# observability — AGENTS

`DOMAINS: Operations & Automation, Engineering`

## OVERVIEW

Stdlib-only logging/metrics/tracing/health; every deploy emits change events, every request carries correlation.

## WHERE TO LOOK

| Task | Location | Notes |
| JSON logs + request IDs | `logging.py`, `middleware.py` | stderr, `X-Request-ID` |
| Prometheus exposition | `metrics.py` | hand-rolled counter/gauge/histogram |
| Probes | `health.py` | `/health` `/ready` `/live` `/metrics` |
| Tracing spans | `tracing.py` | W3C traceparent, 256-span ring |

## GUARDRAILS (THIS DIR)

- No alert without owner + runbook; no gate bypass without written approval.
- `X-Warning: exposed` only on `/metrics` → 403 when exposed without opt-in.
- Zero third-party deps; keep it stdlib + Starlette.

## ANTI-PATTERNS

- No PII in logs/exports; no unbounded buffers (ring caps apply).
