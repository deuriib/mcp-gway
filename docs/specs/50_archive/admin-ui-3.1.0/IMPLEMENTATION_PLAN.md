# Implementation Plan: admin-ui-3.1.0 — Quality-Gate Remediation (3 Highs + CE-001)

**Agent:** engineering implementation specialist (execute-spec remediation cycle)
**Date:** 2026-09-23
**Approved By:** engineering owner (spec packet: quality-gate CLOSED findings, admin-ui-3.1.0)
**Domains-Touched:** engineering

## Steps

| Step | Description | Target / Files | Evidence Location | Est. Effort |
|------|-------------|----------------|-------------------|-------------|
| 1 | REQ-H1: per-field OAuth merge in `p_set_config` — blank keeps stored, non-blank replaces that field only, mask sentinels (bullet/asterisk runs) treated as blank, `clientId`/`clientSecret` stay byte-identical on scope-only edits; all-blank → stored oauth untouched; no stored + all-blank → `None` | `src/mcp_gway/admin/routes.py` (`_oauth_field` helper L854 + merge block L945-955) | `tests/test_admin_dashboard.py` T-H1-1..4 | 0.5h |
| 2 | REQ-H2: fail-closed Host validation in `_gate` — strip port, lowercase, `[::1]` bracket normalization, allow ONLY {127.0.0.1, localhost, ::1, [::1]}; deny before CSRF/form parsing; same 403 loopback surface for both gate conditions | `src/mcp_gway/admin/routes.py` (`_ALLOWED_HOSTS` L48, `_normalize_host` L104, `_gate` L129 — Host check L136-140) | T-H2-1..4 | 0.75h |
| 3 | REQ-H2 follow-up: apply the gate to `p_empty` GET (currently skips `_gate`, only checks bind host) so ALL admin surfaces (pages, partials, mutations) are Host-checked | `src/mcp_gway/admin/routes.py` (`p_empty` L1197) | T-H2-1 (includes `/admin/partials/empty`) | 0.1h |
| 4 | REQ-H2 test-suite repair: one shared client helper sending a loopback Host (TestClient default `testserver` is now rejected); fix the single admin-hitting AsyncClient in `test_gateway.py` | `tests/test_admin_dashboard.py` (`_client` helper + call-site swap), `tests/test_gateway.py` (index test base_url) | full-suite run (605 baseline) | 0.5h |
| 5 | REQ-H3: execute-route timeout — `asyncio.wait_for(asyncio.to_thread(...), timeout=t)` with `t` from the form field clamped [0.1, 30]s default 10s; `TimeoutError` → htmx toast via HX-Retarget/HX-Reswap (mirror `_reject`), non-htmx → redirect with new `exec-timeout` notice | `src/mcp_gway/admin/routes.py` (`_exec_timeout` L1090, `_exec_timeout_response` L1104, `NOTICE_MESSAGES` `exec-timeout` L68, `p_codemode` execute branch L1150-1171) | T-H3-1..5 | 0.75h |
| 6 | REQ-CE-001: toolbar flex floors — wrap the Refresh-all pill in a `flex-1 md:flex-none` div so BOTH direct flex children of the toolbar carry identical border-box floors (no child-level horizontal padding); pill `px-4` stays on the actual pills; modal wrapper untouched | `src/mcp_gway/admin/pages/servers.py` (L211-231) | T-CE-1 (class-level) | 0.4h |
| 7 | Lane docs: plan + test matrix with per-REQ traceability, residual risks, no-commit deviation note | `docs/specs/40_workspace/execute/admin-ui-3.1.0/{IMPLEMENTATION_PLAN.md,TEST_MATRIX.md}` | this file + `TEST_MATRIX.md` | 0.5h |
| 8 | Quality run: `uv run ruff check src/ tests/`, `uv run ruff format src/ tests/`, `uv run pytest -q` — all green (baseline 605 + new tests) | repo-wide | TEST_MATRIX verdict lines | 0.5h |

## Order of Operations

1. Lane docs (step 7 content drafted first — establishes REQ → test-id contract).
2. routes.py changes in one pass (H2 gate first, then H1 merge, then H3 timeout) — all three touch the same file; batching minimizes intermediate states.
3. servers.py CE-001 (independent file).
4. Test-suite client-host repair (step 4) BEFORE the first full run — otherwise ~35 admin tests 403 on `Host: testserver`.
5. New regression tests appended to `tests/test_admin_dashboard.py` (single existing admin test module — also the file already being touched for H2, keeping the change surface minimal per the no-scope-creep hard rule).
6. Quality run last; TEST_MATRIX finalized from actual output.

Rationale: H2 must land before any suite run (it invalidates every admin client), H1/H3/CE-001 are independent of each other and of H2 at the code level.

## Empirical Findings Shaping This Plan (evidence, not assumptions)

- **Edit-form prefill (H1 CRITICAL check):** `_edit_config_details` (`servers.py:550-569`) renders OAuth fields with `placeholder="blank keeps current"` and NO `value=` — the form never prefills a masked sentinel today. The mask-as-blank defense is still implemented (bullet/asterisk-only submissions → treated blank) because the packet forbids ever persisting mask text as a secret, and the endpoint accepts arbitrary POSTs, not just this form.
- **GIL probe (H3):** starlark-pyo3 holds the GIL for the whole eval: an 11.799s workload under `wait_for(0.5)` raised `TimeoutError` at **12.048s** (re-run 2026-09-23) — the event loop is starved during eval; the timeout fires when eval releases the GIL. Loop shapes: no `while` (parse error), no top-level `for`, recursion dies at depth limit (~1ms), `range(10**10)` overflows int — "infinite" ≈ `for _ in range(N)` with N < 2**31. The GIL root cause is OUT OF SCOPE per packet (core owner backlog) → route-level `wait_for` + documented residual risk, with promptness proven on a GIL-releasing blocking call (test double) and no-hang proven on a real Starlark workload.
- **`OAuthConfig` has no port field** (`models.py:687-691`: `clientId`/`clientSecret`/`scope` only); the dead `oauth_port` form/CLI field stays unwired per the HARD rule. The merge reconstructs from the stored model instance, so every modeled field is preserved byte-identically. Unmodeled legacy JSON keys are dropped at parse by pydantic `extra=ignore` — pre-existing behavior, reported below, not fixed (out of scope).

## Rollback Points

- **RP-1 (after step 2-3):** `_gate`/`_normalize_host` revert restores prior behavior; test-suite helper (step 4) is additive and harmless against old code (loopback Host was always accepted).
- **RP-2 (after step 1):** H1 merge reverts independently; no schema/registry format change (pure request→model mapping).
- **RP-3 (after step 5):** H3 reverts independently; the `exec-timeout` notice key is inert once the raise path is gone.
- **RP-4 (after step 6):** CE-001 is a class-only, single-site change; reverting restores the Δ32px child-floor asymmetry and nothing else.
- No commits at any point — orchestrator deviation: feature stays uncommitted until ship; traceability recorded in `TEST_MATRIX.md` Commit column instead.

## Quality Gates

- [x] Engineering: Lint / Tests / Type checks — `ruff check`, `ruff format`, `pytest -q` green (verdicts in TEST_MATRIX)
- [x] Engineering security: H1/H2/H3 each carry a fails-before regression test (evidence in TEST_MATRIX)
- Finance: N/A — no financial surface touched (per template: delete non-touched)
- Legal: N/A — no legal surface
- Marketing: N/A — no copy/brand surface
- People: N/A — no people/impact surface
- Revenue: N/A — no pipeline surface
- Automation/ops: N/A — no runbook/flags/capacity change (no env vars added or renamed)

## Findings Outside Scope (reported, not fixed)

| Severity | Location | Finding | Owner |
|----------|----------|---------|-------|
| Low (hygiene) | `src/mcp_gway/models.py:687-691` + `oauth_port` form/CLI fields | `OAuthConfig` has no `port` field; legacy unmodeled keys under `oauth` are dropped at parse (`extra=ignore`), and `oauth_port` is a dead field on both the add form and CLI. Cannot be "preserved" through any save path today. | core/model owner (backlog) |
| Medium (backlog, already tracked) | admin-ui-3.1.0 quality-gate report | CDN pins, refresh-all budget, health false-green, retry key, oversized handlers — explicitly excluded by packet HARD rule. | per gate report |

## Round 2 — Quality-Gate Remediation (CE-001 completion + CE-007 + QA F-01/F-07)

**Agent:** engineering implementation specialist (execute-spec round 2) · **Date:** 2026-09-23 · **Approved By:** engineering owner (packet: 4 approved targets, admin-ui-3.1.0)

| Step | Description | Target / Files | Evidence Location | Est. Effort |
|------|-------------|----------------|-------------------|-------------|
| R2-1 | REQ-CE-001c: toolbar REFRESH wrapper → flex container — wrapper div gains `flex` beside `flex-1 md:flex-none` so the pill's `flex-1 justify-center md:flex-none` becomes a live flex-item rule; both row children (wrapper + modal root) carry identical `flex-1 md:flex-none` basis; pill visuals (`px-4 py-2`, centered), `md:` desktop layout and modal behavior untouched | `src/mcp_gway/admin/pages/servers.py:212` (row L211, pill cls L216, modal L224-230) | T-CE-1 (strengthened) `tests/test_admin_dashboard.py:923` | 0.3h |
| R2-2 | REQ-H3-doc: `_exec_timeout` docstring honesty — delete the "neither pins nor starves" claim; true contract only: clamp [0.1,30]s default 10, response fires at eval completion, CPU-bound eval can delay response + briefly stall the loop until sandbox gains interrupt/step-limit, worker may be abandoned after timeout. **No behavior change** | `src/mcp_gway/admin/routes.py:1091-1098` | E-H3-doc-1 (docstring diff + suite green; docstrings carry no executable assert) | 0.2h |
| R2-3 | REQ-QA-F-01: local-branch `PUT /admin/partials/servers/{name}/config` tests — (a) allow-listed command saves 200/htmx toast + exact `action=admin_update name=Loc1 binary=… allowed=True reason=allow_list` audit; (b) denied command (absent from `MCP_GWAY_ALLOW_LOCAL_COMMANDS` and `DEFAULT_ALLOW_LIST {npx,bunx,uvx,pipx}`) → normal `_reject` toast surface + registry unchanged + `allowed=False reason=not_allowlisted` audit. Synthetic values, `_seed_local`, env monkeypatched | `tests/test_admin_dashboard.py:475` + `:515` (route `src/mcp_gway/admin/routes.py:959-966`) | T-F01-1, T-F01-2 | 0.5h |
| R2-4 | REQ-QA-F-07: host-set exactness — `test_normalize_host_fails_closed_matrix` asserts `set(_ALLOWED_HOSTS) == {127.0.0.1, localhost, ::1, [::1]}` (equality, not membership) so a 5th added host fails the test; TEST_MATRIX wording corrected | `tests/test_admin_dashboard.py:798` | T-H2-3 (strengthened) | 0.1h |
| R2-5 | Round-2 quality run: `ruff check`, `ruff format --check`, `pytest -q` all green (619 baseline + 2 new = 621) + fails-before/mutation demos with cmp-identical restores | repo-wide | TEST_MATRIX §Round 2 | 0.4h |

**Round-2 order:** source edits verified in place (R2-1/R2-2 landed earlier in this lane, re-verified by anchor read) → new tests fixed for ruff ISC004/format → mutation demos → gates → docs.

**Rollback:** R2-1 class-string revert restores block-wrapper behavior (demo'd, cmp-identical); R2-2 is a docstring (revert = git checkout of the string); R2-3/R2-4 are test-only. No commits.
