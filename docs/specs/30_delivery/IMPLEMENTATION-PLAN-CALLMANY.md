# callMany Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing host-side `call_many` helper as the fifth MCP meta-tool, `callMany`.

**Architecture:** The engine already exists (`CodeMode.call_many`). Add a schema entry to `CODE_MODE_TOOLS`, a validating adapter on `CodeMode` that returns the standard response envelope, and one dispatch branch in `Gateway._handle_tool_call`. No changes to the engine's concurrency or error semantics.

**Tech Stack:** Python 3.12, asyncio, pytest (asyncio auto mode), ruff.

**Spec:** `docs/specs/10_design/CALL_MANY.md`

## Global Constraints

- Meta-tool name is `callMany`; existing four names never change.
- Item shape is `{"server", "tool", "arguments"}`; `arguments` optional, defaults `{}`.
- Limits: 1–50 items; default concurrency stays `min(8, len(calls))`.
- `CodeMode.call_many` behavior is frozen: `tests/test_code_mode.py:349` pins
  `peak_calls == 2` and must keep passing untouched.
- Responses use `build_envelope`; never a second truncation path.
- No new environment variables.

## Review Focus

- An item missing `tool` must become a per-item error, not an exception that discards the
  other 49 results.
- A denied tool must be refused per item and must not leak a call through.
- `calls: []` and 51 items are caller errors (`InvalidParamsError`), not empty results.
- A huge batch result must stay valid JSON under `MCP_GWAY_MAX_RESULT_BYTES`.
- Existing meta-tools keep byte-identical behavior.

---

### Task 1: Schema presence

**Files:**
- Modify: `src/mcp_gway/gateway.py:206` (`CODE_MODE_TOOLS`)
- Test: `tests/test_call_many_meta.py`

**Interfaces:**
- Produces: `CODE_MODE_TOOLS` gains an entry named `callMany` with
  `inputSchema.required == ["calls"]` and `inputSchema.properties.calls.maxItems == 50`.

- [ ] **Step 1: Write the failing test** — `test_tools_list_exposes_call_many`: call
      `Gateway._handle_method("tools/list", {})`, assert `callMany` in the names and its
      schema requires `calls`.
- [ ] **Step 2: Run it** — `pytest tests/test_call_many_meta.py -k tools_list -v`;
      expect FAIL (name not found).
- [ ] **Step 3: Add the schema entry** to `CODE_MODE_TOOLS`; description states ordering,
      per-item errors, 50-item cap, and that dependencies between calls belong in
      `executeTool`.
- [ ] **Step 4: Run it** — expect PASS.
- [ ] **Step 5: Commit** — `feat(code-mode): advertise callMany in tools/list`.

### Task 2: Adapter and dispatch

**Files:**
- Modify: `src/mcp_gway/code_mode.py` (new method after `call_many`)
- Modify: `src/mcp_gway/gateway.py:854-914` (dispatch branch)
- Test: `tests/test_call_many_meta.py`

**Interfaces:**
- Produces: `CodeMode.call_many_envelope(calls: object) -> str`, returning
  `build_envelope(result=[...], logs=[], calls=[], duration_ms=<int>, default=str)`.
- Consumes: `CodeMode.call_many(tool_calls, max_concurrency=None) -> list[dict]`.

- [ ] **Step 1: Write failing tests** — happy path across two servers (order preserved),
      per-item failure isolation, malformed item becomes data, empty and 51-item batches
      raise `InvalidParamsError`, envelope has `result/logs/calls/usage`, oversized result
      truncated and valid JSON.
- [ ] **Step 2: Run them** — expect FAIL (`AttributeError: call_many_envelope`).
- [ ] **Step 3: Implement `call_many_envelope`** — validate top level, normalize items,
      mark malformed items as per-item errors without dispatch, delegate to `call_many`,
      time it, wrap with `build_envelope`.
- [ ] **Step 4: Add the dispatch branch** — `elif name == "callMany":` validate
      `arguments.get("calls")` is present, call the adapter, return as `text`.
- [ ] **Step 5: Run them** — expect PASS; then the full suite.
- [ ] **Step 6: Commit** — `feat(code-mode): add callMany meta-tool`.

### Task 3: Documentation and skills

**Files:**
- Modify: `docs/code-mode.md`, `AGENTS.md`, `docs/briefs/BRIEF-gateway-roadmap.md`
- Modify: `skills/mcp-gway-mcp/SKILL.md`, `skills/mcp-gway-core/SKILL.md`,
  `skills/mcp-gway/SKILL.md`
- Create: `docs/specs/12_adr/ADR-015-callmany-meta-tool.md`

- [ ] **Step 1:** Replace "four meta-tools" claims with five and document `callMany`'s
      shape, ordering, isolation, and 50-item cap. Keep "not available inside Starlark".
- [ ] **Step 2:** ADR-015: decision, alternatives (tuple builtin, per-server method,
      Python-only), consequences (surface growth, no reuse in batch).
- [ ] **Step 3:** Verify — `pytest -q`, `ruff check`, `ruff format --check`, and
      `grep -rn "exactly four" skills docs` returns nothing.
- [ ] **Step 4: Commit** — `docs(code-mode): document callMany`.
