# Design: `callMany` — expose host-side fan-out as the fifth meta-tool

**Status:** approved by owner (2026-10-24: approach A + MCP meta-tool surface)
**Date:** 2026-10-24
**Scope:** small change — one meta-tool entry, one adapter, one test file
**Corrects:** an earlier sketch that proposed building the fan-out engine. It already
exists: `CodeMode.call_many` (`code_mode.py:464`), `Gateway.call_many`
(`gateway.py:493`), and `mcp_gway.call_many` (`__init__.py:10`).

## Intent

Agents that do not write Starlark have no way to fan out: `tools/list` exposes only the
four Code Mode meta-tools (`gateway.py:849`), and `call_many` is Python-only. Expose the
existing helper as `callMany` so an agent gets bounded parallelism with per-call error
isolation over plain MCP.

The engine is not rebuilt. This is an adapter: validate, delegate, envelope.

## Existing contract (unchanged)

`CodeMode.call_many(tool_calls, *, max_concurrency=None)`:

- Input items: `{"server": str, "tool": str, "arguments": dict, "id": str | None}`.
- Output: one item per input, input order, `{id, server, tool, ok, result}` or
  `{id, server, tool, ok: false, error: {type, message}}`.
- Default concurrency `min(8, len(calls))`; a failure never cancels siblings.
- Pinned by `tests/test_code_mode.py:349` (`peak_calls == 2` for same-server calls).

**No behavior change to this function.** Its concurrency contract is already tested and
documented in the skills; changing it is a separate slice.

## New surface

Fifth entry in `CODE_MODE_TOOLS`, name `callMany`.

```json
{"calls": [{"server": "Filesystem", "tool": "read_file", "arguments": {"path": "a.txt"}}]}
```

- `calls`: 1–50 items.
- Item shape is the object form, **not** tuples. Correction to the earlier sketch:
  `call_many` already ships with dict items, and the package API, `Gateway.call_many`,
  and three skills document it. Positional arrays are also easier for a model to get
  wrong. Keeping one shape beats terseness.
- Returns the `executeToolCode` envelope (`result` / `logs` / `calls` / `usage`) with the
  per-call list in `result`, so an agent reads one response shape across meta-tools.
- `logs` and `calls` are empty: the trace lives inside `executeToolCode`. Upstream
  per-call metrics already record through `_call_tool_async`.

## Validation rules

| Condition | Behavior |
|---|---|
| `calls` missing, not a list, empty, or > 50 | `InvalidParamsError` |
| Item is not an object, or `server`/`tool` empty | per-item `ok: false`, batch continues |
| `arguments` absent | defaults to `{}` |
| Unknown server | per-item `ok: false` from `get_config`, batch continues |
| Tool denied by ACL | per-item `ok: false` from `_check_tool_allowed`, batch continues |

Malformed items are data, not exceptions: one typo must not discard the other 49 results.

## Limits

- 50 items per call, 8 concurrent by default. No environment knob in v1; a knob before a
  measured need is premature.
- Result size is capped by the existing `build_envelope` budget
  (`MCP_GWAY_MAX_RESULT_BYTES`).

## Non-goals

- **No connection reuse inside a batch.** `call_many` runs without `_ACTIVE_CACHE`, so
  each call opens its own session. Wiring the cache in requires per-server serialization,
  which contradicts the pinned `peak_calls == 2` contract. Separate slice, with its own
  ADR and test change.
- **No sandbox builtin.** Scripts keep calling tools directly.
- **No dependency chaining.** Results, not expressions.
- **No passthrough.**

## Test matrix

| # | Case | Assertion |
|---|------|-----------|
| 1 | tools/list | `callMany` present, `calls` required |
| 2 | Happy path | 2 servers, order preserved, `ok: true` |
| 3 | Per-item failure | one failure, sibling succeeds, no raise |
| 4 | Malformed item | per-item error, batch continues |
| 5 | Limits | empty and 51 items raise `InvalidParamsError` |
| 6 | Envelope | valid JSON with `result`/`logs`/`calls`/`usage` |
| 7 | Budget | oversized batch truncated, still valid JSON |
| 8 | Regression | `executeToolCode` and the other meta-tools unchanged |

## Documentation

`docs/code-mode.md` (fifth meta-tool + limits), `AGENTS.md` (five meta-tools),
`skills/mcp-gway-mcp/SKILL.md`, `skills/mcp-gway-core/SKILL.md`, `skills/mcp-gway/SKILL.md`,
`docs/briefs/BRIEF-gateway-roadmap.md` (item 1 done), ADR-015 for the exposure decision.
