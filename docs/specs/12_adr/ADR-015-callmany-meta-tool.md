# ADR-015: Expose `callMany` as the fifth Code Mode meta-tool

**Date:** 2026-10-24  
**Status:** Accepted

## Context

The host-side `CodeMode.call_many` helper already existed before the gateway
surface was widened. It was useful for orchestrating multiple MCP calls in one
batch, but it remained Python-only and therefore invisible to agents that only
speak MCP JSON-RPC.

At the same time, the existing Code Mode contract had four discovery and
execution tools. Raising the count to five was a small surface change, but it
had to preserve the same safety model: no new sandbox capability, no new
environment variables, and no change to the existing concurrency semantics in
`CodeMode.call_many`.

## Decision

1. Add a fifth Code Mode tool named `callMany` to `CODE_MODE_TOOLS`.
2. Require a top-level `calls` array on the MCP request, with a 1–50-item limit.
3. Treat each item as `{"server": str, "tool": str, "arguments": dict, "id": str | None}`.
4. Default `arguments` to `{}` and preserve input order in the result.
5. Return the standard Code Mode envelope (`result`, `logs`, `calls`, `usage`), keeping the batch result in `result`.
6. Keep malformed items as per-item errors instead of crashing the whole batch.
7. Keep the host-side helper and the MCP tool shape aligned; no Starlark access.

## Alternatives considered

### 1. Keep `call_many` as a Python-only helper

This minimizes the API surface but leaves a large gap for agents that do not
write Python and are forced to fall back to `executeToolCode` for orchestration.
The same fan-out engine is already implemented and tested; surfacing it does not
add complexity, only visibility.

### 2. Add a new per-server method instead of a meta-tool

This would create more server-specific behavior and force tool discovery to learn
another naming pattern. It also makes the gateway contract inconsistent with the
existing meta-tool pattern, where one tool can orchestrate batches across many
servers.

### 3. Expose batching as a new Starlark builtin

This was rejected because Starlark is intentionally limited and synchronous.
The sandbox should stay hermetic and declarative; orchestration belongs on the
host side where error isolation and bounded concurrency already exist.

## Consequences

- The Code Mode tool surface grows from four to five items without changing the
  meaning of the other four.
- Agents can use a single MCP tool to dispatch bounded parallel work while
  preserving per-item isolation.
- The existing host-side helper keeps its tested semantics, and the MCP adapter
  simply wraps that contract.
- There is no dependency chaining or expression execution inside the batch; the
  response remains data, not a second evaluation engine.
- The sandbox stays unchanged: `callMany` is available over MCP, not within
  Starlark itself.
