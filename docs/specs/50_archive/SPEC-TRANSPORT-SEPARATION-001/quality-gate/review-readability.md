# READABILITY Review — SPEC-TRANSPORT-SEPARATION-001

**Domain:** Readability (naming, structure, docstrings, cognitive load, WHY clarity)
**Reviewer role:** READABILITY reviewer (quality-gate lane)
**Date:** 2026-09-22
**Scope:** commits `88f47fd` (src), `bd2d11a` (tests), `dedf480` (docs)
**Packet:** `docs/specs/50_archive/SPEC-TRANSPORT-SEPARATION-001/{PROPOSED_CHANGES,IMPLEMENTATION_PLAN,TEST_MATRIX}.md` (read first, reference-only)

## Verdict: APPROVE

No blocking findings. The change reads well: names state intent, the transport
contract is documented where a reader lands first (`Gateway.__init__` docstring),
and every contract test carries a REQ-ID docstring. Findings below are minor and
none impede comprehension of the new behavior.

## Findings

### F1 (minor) — Missing WHY at the route-gating branch and 405 handlers

- **Where:** `src/mcp_gway/gateway.py:320-330` (the `if transport == "sse"` route
  branch — no comment) and `src/mcp_gway/gateway.py:522-538` (both handlers).
- **Evidence:** the handlers' docstrings state *what* is gated
  (`gateway.py:523` "GET /mcp is gated off: this gateway serves Streamable HTTP only";
  `gateway.py:531` "POST /mcp is gated off: this gateway serves SSE only"), and the
  `detail` bodies even carry the remediation (`gateway.py:525`,
  `gateway.py:534`). What is never stated in code: **why** the disallowed method
  gets an explicit route returning `405 + Allow` + JSON detail instead of simply
  not being registered (Starlette would answer 405 on its own, but with a
  plain-text body and no remediation hint — which is exactly why
  `tests/test_transport_separation.py:69` asserts `"detail" in r.json()`), and
  **why 405 rather than 404** (MCP spec permits 405 — rationale lives only in
  `PROPOSED_CHANGES.md:36-37`).
- **Impact:** a reader of `gateway.py:320` has to reconstruct the rationale from
  the test or the proposal. One WHY comment at the branch closes the gap.
  Directly touches checklist item "WHY comments present where non-obvious
  (405 handlers, route gating)" → that item is PASS-with-gap, not full PASS.

### F2 (minor) — ASCII architecture box row off by one column

- **Where:** `README.md:283` — `│  - refresh --auth         │  - POST /mcp/messages (alias) [sse]     │`
- **Evidence:** measured display width = **71** columns; the frame and sibling
  rows are **72** (`README.md:277`, `README.md:281`, `README.md:282`,
  `README.md:284` all = 72). The right border of that row is misaligned by one
  space. Introduced by `dedf480` (the previous text on that row was 76 cols —
  already broken; the edit fixed most of it but landed one short).
- **Impact:** cosmetic, but it is a visible break in the one diagram readers use
  to grasp the per-transport split. One space.

### F3 (minor, pre-existing on a touched line) — Wrong package path in amended contract row

- **Where:** `docs/specs/10_design/ARCHITECTURE.md:28` — cites
  `src/mcp_gateway/gateway.py`; the real path is `src/mcp_gway/gateway.py`.
- **Evidence:** `ls src/` shows package `mcp_gway`; the same typo spans the whole
  table (`ARCHITECTURE.md:29-33`), so it is table-wide pre-existing debt. But
  `dedf480` amended this exact row (added `gateway.py:320-340`, which is
  accurate) and left the path wrong — a reader navigating from the amended
  contract to the cited file will not find it.
- **Impact:** misleading citation inside the doc this commit was meant to bring
  up to date. Not introduced by the diff; flagged because the line was edited.

### F4 (observation, pre-existing) — `tests/test_gateway.py` lacks the future import

- **Where:** `tests/test_gateway.py:1-8` — no
  `from __future__ import annotations` (grep count 0, and 0 at
  `bd2d11a^`, i.e. not a regression). Every other test file touched by `bd2d11a`
  has it (`tests/test_serve_unified.py:3`, `tests/test_edgecases_gateway.py:3`,
  `tests/test_transport_separation.py:8`, and the three one-line SSE migrations).
- **Evidence:** the diff added no annotations to this file, so there is no
  functional impact; repo convention ("`from __future__ import annotations` in
  all modules", AGENTS.md Code Conventions) is simply not met here.
- **Impact:** none on this change; housekeeping at most.

### F5 (observation, pre-existing structure) — Route contract lives inside a ~190-line `__init__`

- **Where:** `src/mcp_gway/gateway.py:168-357` (`Gateway.__init__` spans metrics
  pre-registration 196-273, wiring 274-297, lifespan closure 298-318, route
  gating 320-330, middleware/state 331-352).
- **Evidence:** the new code is self-contained at `gateway.py:181-182`
  (validation) and `gateway.py:320-330` (route selection) and reads clearly in
  place — adjacent to the `Starlette(...)` assembly, which is arguably the
  clearest spot for it. The `__init__` length is pre-existing debt, not created
  by `88f47fd`.
- **Impact:** none today. A future `_routes_for_transport()` helper would give
  the route contract one reason to change, but extracting it now is optional —
  the inline branch is not what makes `__init__` long.

## Checklist

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | Clear names | **PASS** | `gateway.py:522` `_mcp_get_not_allowed`, `gateway.py:530` `_mcp_post_not_allowed`, `gateway.py:321` `mcp_routes`; `test_edgecases_gateway.py:257/265` `alias_gw`/`limits_gw` name the two-gateway split; `test_serve_unified.py:116` `..._http_sse_distinct_routes` (renamed from `..._same_app`, old contract gone); `test_transport_separation.py:27` `_mcp_surface` |
| 2 | One reason to change | **PASS (note F5)** | new logic isolated at `gateway.py:181-182` + `320-330`; `cli.py:514` single-line propagation; the long `__init__` (`gateway.py:168-357`) is pre-existing |
| 3 | Docstrings on public functions | **PASS** | `gateway.py:174-180` (`Gateway.__init__`, states no-fallback invariant), `cli.py:467-471` (`_serve_http`, routes per transport), `cli.py:628` (`serve`), `gateway.py:523/531` (405 handlers), module docstring `test_transport_separation.py:1-6`, helpers `test_transport_separation.py:23/28`, rewritten `test_serve_unified.py:117-118` |
| 4 | Nesting ≤ 2 | **PASS** | `gateway.py:320-330` branch sits at method depth 1; `test_transport_separation.py:45-47` `for`+`with` = depth 2; `_mcp_surface` (`test_transport_separation.py:29-35`) is a flat comprehension |
| 5 | WHY comments where non-obvious (405 handlers, route gating) | **PARTIAL → F1** | handlers documented as *what* (`gateway.py:523/531`); rationale for explicit-405 route and 405-vs-404 absent at `gateway.py:320` (lives only in `PROPOSED_CHANGES.md:34-40`) |
| 6 | Repo conventions (`from __future__ import annotations`, type hints) | **PASS (note F4)** | future import: `gateway.py:3`, `cli.py:3`, `test_transport_separation.py:8` (+ all touched tests except `test_gateway.py`); hints: `gateway.py:168-173` (`transport: str = "http" -> None`), `cli.py:460-466`, `test_transport_separation.py:22/27`; module docstring `test_transport_separation.py:1-6` |
| 7 | No dead code/comments | **PASS** | dead `test_sse_endpoint` removed in `bd2d11a` and no dangling refs (grep: only `TEST_MATRIX.md:38` documenting the migration); `pytest` still used 20× in `test_gateway.py` (no orphan import after the deletion); stale "share the same app" wording gone from src/tests/docs (grep 0 hits outside the packet's own historical tables); `uv run ruff check src/ tests/` and `ruff format --check` on all touched files both clean |

## Verified-accurate claims (positive evidence)

- `AGENTS.md:32` and `AGENTS.md:148` cite `gateway.py:320-340` — matches actual
  code (`mcp_routes` 320-330, `Starlette(...)` 331-340). Route counts "http = 6
  / sse = 7" verified against `gateway.py:320-340` (4 probes + 2 / + 3).
- `AGENTS.md:78` claims ADR-010 is "referenciado, ausente en repo" — verified:
  `docs/architecture/` does not exist, so the comment is true, not stale.
- `API_CONTRACTS.md:16-22` amended section states `transport="http"` is default —
  matches `gateway.py:172`.
- REQ-ID traceability in every contract-test docstring
  (`test_transport_separation.py:39,51,63,73,81,90,99,117,142`) keeps the tests
  self-explanatory without opening `TEST_MATRIX.md`.
- Smoke check: `uv run pytest -q tests/test_transport_separation.py tests/test_serve_unified.py`
  → 22 passed (docstrings/names match observed behavior).

## Scope note

Evidence is limited to the three scoped commits and the files they touch.
Pre-existing debt (F3, F4, F5) is labeled as such and is not attributable to
this change. No src/, tests/, or packet files were modified; nothing committed.
