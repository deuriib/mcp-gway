# Product Brief: Gateway Roadmap After Code Mode v2

**ID:** BRIEF-GW-ROADMAP-001
**Initiator:** Deuri Vasquez (CEO)
**Date:** 2026-10-24
**Status:** accepted (backlog)
**Domains-Touched:** [engineering, product]

## Problem Statement

The 2026-10 competitor review concluded that "4 meta-tools + Starlark sandbox" is a
commoditized surface — at least one gateway ships the same shape — so differentiation
must come from orchestration quality and local developer experience, not from the tool
count.

That conclusion and its ranked backlog lived only in the review session. Nothing in the
repository recorded what was decided, why, or what was deliberately rejected. A roadmap
that exists only in chat is not a roadmap; it is a memory that dies with the context
window.

This brief persists the backlog and the reasoning behind its order.

## What Already Shipped

| Release | Change | Evidence |
|---------|--------|----------|
| v4.8.0 | One upstream connection per script (was one process + handshake per call) | 3 calls → 1 spawn; 2214 ms then 2 ms |
| v4.8.0 | Response envelope with `calls[]` trace and `usage` | `docs/code-mode.md` |
| v4.8.0 | Result budget `MCP_GWAY_MAX_RESULT_BYTES`, labelled truncation | 50 KB result → 1007 B, valid JSON |
| v4.8.1 | CLI survives a legacy code page instead of crashing on output | strict cp1252 run exits 0 |

## Ranked Backlog

| # | Item | Why it matters | Size | Risk | Status |
|---|------|----------------|------|------|--------|
| 1 | `call_many` fan-out | Starlark is synchronous; N calls cost N sequential round trips. Connection reuse removed spawn cost, not serialized latency | M (1–2 d) | Touches the concurrency contract of the per-script session cache | done |
| 2 | Direct passthrough per server | `tools/list` returns only the 5 meta-tools, so no client can call an upstream tool without executing code. Blocks drop-in gateway use | L (2–4 d) | Tool-name collisions; auth/policy surface | queued |
| 3 | Cross-script session pool | Saves the handshake on repeat scripts | S–M | Stale sessions surviving between runs | gated on evidence |
| 4 | MCP `2026-07-28` stateless negotiation | Protocol currency, not differentiation | unknown | Spec still moving; speculative work | watch |

## Decisions

- **Order is driven by user-visible latency, not by feature parity.** `call_many` is the
  only remaining item that changes what a script can express; passthrough changes who can
  use the gateway at all, which is bigger but riskier and deserves its own design pass.
- **Cross-script pooling stays parked.** It buys roughly one handshake per repeat script
  and introduces the only failure mode deliberately avoided so far: a stale session that
  outlives its run. It reopens when the `calls[]` trace shows repeat traffic worth the
  trade. Default is no; the condition that flips it is measured repeat rate.
- **No speculative protocol work.** The MCP revision is a watch item until a client or
  server in use requires it.
- **Passthrough is not a `call_many` substitute.** One is a latency lever inside Code
  Mode; the other is a compatibility mode for clients that refuse code execution.

## Assumptions

- Competitor claims above come from the 2026-10 session review and were not re-verified
  when this brief was written. Treat them as decision context, not as current fact.
- The latency win from `call_many` is bounded by upstream response time; it helps
  aggregation across servers, not single-call scripts.

## Non-Goals

- Reviving the retired dashboard/catalog surfaces.
- Widening `MCP_GWAY_ALLOW_LOCAL_COMMANDS` for convenience.
- Parallelism inside Starlark itself. The runtime stays synchronous; concurrency is a
  host-side capability exposed as one builtin.

## Open Questions

- [ ] Does `call_many` return per-item errors, or fail the batch? (Starlark has no
      `try/except`, so a raise destroys the whole script.)
- [ ] Same-server fan-out in v1, or cross-server only until a per-session lock exists?
