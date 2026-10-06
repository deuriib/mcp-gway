# core — AGENTS

`DOMAINS: Security & Privacy, Engineering`

## OVERVIEW

Transport/discovery/policy engine with zero CLI deps; single source for allow-list, parsing, install.

## WHERE TO LOOK

| Task | Location | Notes |
| Allow-list + cwd/env gates | `policy.py` | ADR-009; denylist exact + prefixes |
| Remote auto-detect | `transport.py` | streamable-http → sse → http |
| Discovery + persist | `client.py`, `install.py` | semaphore 3, OAuth fallback |
| Flag parsing | `parsing.py` | `KEY=VALUE` headers/envs |

## GUARDRAILS (THIS DIR)

- Never import CLI/gateway/HTTP here; pure transport + policy.
- Never rename `MCP_GWAY_ALLOW_LOCAL_COMMANDS`; `*`/paths → deny + warn.
- Timeouts + jittered retries on transport only, never after `call_tool`.
- `NODE_ENV` allowed; denylisted env names rejected with reason codes.

## CONVENTIONS

- Pure functions preferred, side effects at edges; early returns.

## ANTI-PATTERNS

- No shell spawning; no secret logging; no unbounded queues.
