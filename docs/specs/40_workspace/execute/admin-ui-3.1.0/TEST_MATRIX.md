# Test / Evidence Matrix: admin-ui-3.1.0 — Quality-Gate Remediation

**Agent:** engineering implementation specialist (execute-spec remediation cycle)
**Date:** 2026-09-23
**Domains-Touched:** engineering

| REQ-ID | Evidence ID | Description | Type | Status | Commit |
|--------|-------------|-------------|------|--------|--------|
| REQ-H1 | T-H1-1 | `test_oauth_scope_only_put_keeps_credentials_byte_identical` — PUT with only `oauth_scope` set keeps stored `clientId`+`clientSecret` byte-identical, replaces scope only. FAILS BEFORE (old whole-object replace re-minted clientId, dropped clientSecret) | Unit | pass | uncommitted¹ |
| REQ-H1 | T-H1-2 | `test_oauth_all_blank_fields_keep_stored_credentials` — all OAuth fields blank → stored oauth untouched (clientId/secret/scope keep values, other fields like timeout still save) | Unit | pass | uncommitted¹ |
| REQ-H1 | T-H1-3 | `test_oauth_blank_fields_with_no_stored_oauth_stay_none` — no stored oauth + all-blank → `oauth is None` after save | Unit | pass | uncommitted¹ |
| REQ-H1 | T-H1-4 | `test_oauth_mask_sentinels_treated_as_blank` — `oauth_client_id="••••••••"` + `oauth_client_secret="********"` treated as blank → stored credentials preserved, mask text never persisted. FAILS BEFORE (sentinels group-replaced the whole object → mask written as secret) | Unit | pass | uncommitted¹ |
| REQ-H2 | T-H2-1 | `test_evil_host_header_403_on_every_admin_surface` — `Host: evil.example.com` → 403 with "loopback" on page GET `/`, page GET `/admin/servers`, partial GET `/admin/partials/status`, partial GET `/admin/partials/empty`, mutation **PUT** `/admin/partials/servers/Demo/config` (CSRF-valid → 403 AND registry unchanged; Host check runs before CSRF — no-CSRF PUT answers "loopback", never "CSRF token mismatch"). FAILS BEFORE (index answered 200) | Integration | pass | uncommitted¹ |
| REQ-H2 | T-H2-2 | `test_loopback_host_variants_pass_admin_gate` — `127.0.0.1`, `localhost`, `::1`, `[::1]`, `127.0.0.1:8080`, `LOCALHOST:9999`, `[::1]:8080` → 200 | Integration | pass | uncommitted¹ |
| REQ-H2 | T-H2-3 | `test_normalize_host_fails_closed_matrix` — unit matrix: port strip, lowercase, IPv6 bracket form kept; `None`/empty/whitespace → `""`; malformed `[::1]evil`, `[::1]:abc`, `[evil` → `""` (fail closed); `_ALLOWED_HOSTS` contains exactly the 4 allowed values and never `testserver`/`evil.example.com`/suffix-tricks | Unit | pass | uncommitted¹ |
| REQ-H2 | T-H2-4 | `test_non_admin_routes_unaffected_by_host_gate` — `/health` 200 and `/mcp` 405 `Allow: POST` with a non-loopback Host (gate covers admin routes only) | Integration | pass | uncommitted¹ |
| REQ-H2 | E-H2-1 | Test-suite repair: shared `_client()` helper (loopback `base_url="http://127.0.0.1"`, 33 call sites) in `tests/test_admin_dashboard.py`; `tests/test_gateway.py` index test → `base_url="http://127.0.0.1"`. `test_wave2_api.py` (only `/health`) and `test_edgecases_gateway.py` (only probes + `/mcp`) checked clean — untouched | Review | pass | uncommitted¹ |
| REQ-H3 | T-H3-1 | `test_execute_timeout_htmx_returns_prompt_toast` — async `httpx2.ASGITransport` client; blocking execute double (2.0s GIL-releasing `time.sleep`) + `timeout=0.1` → 200 + `HX-Retarget: #toast` + `HX-Reswap: outerHTML` + "timed out after 0.1s", no `hx-swap-oob`, elapsed < 1.5s (measured ~0.11s). FAILS BEFORE (no `wait_for` — output returned after full 2s, no retarget) | Integration | pass | uncommitted¹ |
| REQ-H3 | T-H3-2 | `test_execute_timeout_real_starlark_does_not_hang` — real Starlark `for _ in range(100000000)` + `timeout=0.1` → timeout toast surface, elapsed < 8.0s (measured ~0.6-0.64s; arrival tracks eval end under GIL — bounded, no hang). FAILS BEFORE (route waits for completion and returns the success surface) | Integration | pass | uncommitted¹ |
| REQ-H3 | T-H3-3 | `test_execute_timeout_non_htmx_redirects_with_notice` — non-htmx timeout → 303 `/admin/tools?notice=exec-timeout`, landing page shows "timed out" (mirror of `_reject`'s structured non-htmx fallback) | Integration | pass | uncommitted¹ |
| REQ-H3 | T-H3-4 | `test_exec_timeout_clamps_and_defaults` — `_exec_timeout`: default 10.0 for missing/blank/garbage/`nan`/`inf`/`-inf`; clamp `[0.1, 30]` (`"0"`→0.1, `"0.001"`→0.1, `"999"`→30.0); pass-through `"5.5"`→5.5 | Unit | pass | uncommitted¹ |
| REQ-H3 | T-H3-5 | `test_execute_fast_path_returns_result_without_timeout` — real Starlark `result = 42` through the `wait_for` wrapper → 200 with result, no retarget, no "timed out" (happy path unbroken) | Integration | pass | uncommitted¹ |
| REQ-CE-001 | T-CE-1 | `test_toolbar_flex_children_share_identical_floors` — class-level: `<div class="flex gap-3 w-full md:w-auto shrink-0">` is immediately followed by the padding-free wrapper `<div class="flex-1 md:flex-none">` (Refresh-all pill inside it), modal carries `class="relative flex-1 md:flex-none"`, pill keeps `px-4 py-2 text-[14px]` + `flex-1 justify-center md:flex-none`, trigger `w-full justify-center md:w-auto`, `hx-post="/admin/partials/refresh"` and `for="add-server-modal"` click-target intact. FAILS BEFORE (pill was the padded direct flex child → Δ32px floor) | Unit | pass | uncommitted¹ |

¹ **Commit column:** explicit orchestrator deviation — no commits during this remediation cycle; the feature stays uncommitted until ship-release. Traceability is carried by this lane (`docs/specs/40_workspace/execute/admin-ui-3.1.0/`) plus the final `ruff`/`pytest` verdicts below.

## Fails-Before Demonstrations (behavior-only reverts, 2026-09-23)

Each fix was reverted to its pre-fix *behavior* (helper symbols kept so the test module still imports — a symbol-absent revert of the pre-fix code would fail at import, which is trivially implied and not run separately), the REQ's test subset executed, then the file restored from a `cmp`-verified backup and the subset re-run.

| Fix | Revert applied | Before (reverted) | Restore | After (fixed) | Evidence log |
|-----|----------------|-------------------|---------|---------------|--------------|
| REQ-H1 | merge block → pre-fix whole-object replace (`clientId=client_id or None, clientSecret=client_secret or None, scope=client_scope or None` whenever any field non-blank) | **2 failed, 3 passed** — `test_oauth_scope_only_put_keeps_credentials_byte_identical` (clientId re-minted `eb28ab18… ≠ 11111111…`) + `test_oauth_mask_sentinels_treated_as_blank` failed; complements passed | `cp` + `cmp` identical | **5 passed** | `/tmp/opencode/h1_before.txt`, `h1_after.txt` |
| REQ-H2 | Host-check block removed from `_gate` (pre-fix had **zero** `headers.get("host")` checks — gate-report SEC-001) | **1 failed, 3 passed** — `test_evil_host_header_403_on_every_admin_surface` failed at `assert 200 == 403` (evil Host reached the page); loopback/normalize/non-admin pass pre-fix by design | `cp` + `cmp` identical | **4 passed** | `/tmp/opencode/h2_before.txt`, `h2_after.txt` |
| REQ-H3 | execute branch → direct `result = code_mode.execute_tool_code(source)` (no `wait_for`; `_exec_timeout*` helpers kept) | **3 failed, 2 passed** — `test_execute_timeout_htmx_returns_prompt_toast`, `test_execute_timeout_real_starlark_does_not_hang`, `test_execute_timeout_non_htmx_redirects_with_notice` failed; clamps + fast-path pass (helpers kept; fast path never timed out pre-fix) | `cp` + `cmp` identical | **5 passed** | `/tmp/opencode/h3_before.txt`, `h3_after.txt` |
| REQ-CE-001 | wrapper div unwrapped → Refresh-all pill back as padded direct flex child | **1 failed** — `test_toolbar_flex_children_share_identical_floors` failed at the container+wrapper adjacency assert (Δ32px floor restored) | `cp` + `cmp` identical | **1 passed** | `/tmp/opencode/ce_before.txt`, `ce_after.txt` |

Final gate after all restores: `/tmp/opencode/final_pytest.txt` (619 passed), `final_ruff_check.txt` (All checks passed), `final_ruff_format.txt` (89 files already formatted).

## Quality Verdicts

| Check | Command | Result |
|-------|---------|--------|
| Lint | `uv run ruff check src/ tests/` | PASS (no findings) |
| Format | `uv run ruff format --check src/ tests/` | PASS (89 files already formatted) |
| Tests | `uv run pytest -q` | PASS — 619 passed (605 baseline + 14 new²) |

² New tests (14): T-H1-1..4 (4), T-H2-1..4 (4), T-H3-1..5 (5), T-CE-1 (1) — all appended to `tests/test_admin_dashboard.py` (file total 48 = 34 pre-existing + 14; the shared `_client()` helper added no test functions, it only repaired Host handling of existing ones).

## Round 2 — Test / Evidence Matrix (CE-001 completion + CE-007 + QA F-01/F-07)

**Date:** 2026-09-23 · **Domains-Touched:** engineering

| REQ-ID | Evidence ID | Description | Type | Status | Commit |
|--------|-------------|-------------|------|--------|--------|
| REQ-CE-001c | T-CE-1 (strengthened) | `test_toolbar_flex_children_share_identical_floors` (`tests/test_admin_dashboard.py:923`) — asserts toolbar container + REFRESH wrapper adjacency `<div class="flex gap-3 w-full md:w-auto shrink-0"><div class="flex flex-1 md:flex-none"><button` (wrapper carries BOTH the `flex` container class and the shared basis), modal root `class="relative flex-1 md:flex-none"` (both row children share `flex-1 md:flex-none`), pill keeps `flex-1 justify-center md:flex-none` + `px-4 py-2 text-[14px]`, `hx-post="/admin/partials/refresh"` + `for="add-server-modal"` intact. FAILS BEFORE (block wrapper → pill shrink-to-fit, Δ8.11px@414 / Δ101px@600 / Δ7.34px@768) | Unit | pass | uncommitted¹ |
| REQ-H3-doc | E-H3-doc-1 | `_exec_timeout` docstring (`src/mcp_gway/admin/routes.py:1091-1098`) rewritten to the true contract: clamp [0.1,30]s default 10; response fires at eval completion; CPU-bound Starlark eval can delay the response and briefly stall the event loop until the sandbox gains interrupt/step-limit; worker abandoned after timeout. "Neither pins nor starves" claim removed. No behavior change — function body byte-identical; behavior pinned by existing T-H3-4. No revert demo: docstrings carry no executable assert (explained, not skipped) | Review (docstring) | pass | uncommitted¹ |
| REQ-QA-F-01 | T-F01-1 | `test_local_config_put_allowed_command_saves_and_audits_admin_update` (`tests/test_admin_dashboard.py:475`) — seeded local server + `MCP_GWAY_ALLOW_LOCAL_COMMANDS=python3` → PUT command `python3 -m allowed_mod` answers 200 with "Config updated for Loc1.", registry command/timeout/enabled persisted, caplog audit exactly `local action=admin_update name=Loc1 binary=python3 allowed=True reason=allow_list`. Mutation FAILS BEFORE (gate+audit removed → 2 failed) | Integration | pass | uncommitted¹ |
| REQ-QA-F-01 | T-F01-2 | `test_local_config_put_denied_command_rejected_registry_unchanged` (`tests/test_admin_dashboard.py:515`) — env unset (only `DEFAULT_ALLOW_LIST {npx,bunx,uvx,pipx}` live) → `totallynotallowed --flag` rejected via normal `_reject` toast (`HX-Retarget: #toast`, `HX-Reswap: outerHTML`, "command not allowed: totallynotallowed", `[reason=not_allowlisted]`), registry command+timeout unchanged, audit `allowed=False reason=not_allowlisted`. Mutation FAILS BEFORE | Integration | pass | uncommitted¹ |
| REQ-QA-F-07 | T-H2-3 (strengthened) | `test_normalize_host_fails_closed_matrix` (`tests/test_admin_dashboard.py:784`) — `assert set(_ALLOWED_HOSTS) == {"127.0.0.1", "localhost", "::1", "[::1]"}` at `:798` (exact-set equality, not membership) + existing negative matrix. Mutation-proof: injecting a 5th host `0.0.0.0` into `_ALLOWED_HOSTS` now FAILS the test (`1 failed` demonstrated; QA F-07's "adding a 5th host leaves the test green" falsified) | Unit | pass | uncommitted¹ |

### Round-2 Fails-Before / Mutation Demos (behavior-only revert → restore → cmp-identical, 2026-09-23)

| Fix | Revert applied | Before (reverted) | Restore | After (fixed) | Evidence log |
|-----|----------------|-------------------|---------|---------------|--------------|
| REQ-CE-001c | wrapper `flex flex-1 md:flex-none` → `flex-1 md:flex-none` (drop container class = pre-fix block wrapper) | **1 failed** — `test_toolbar_flex_children_share_identical_floors` at `:927` adjacency assert | `cp` + `cmp` identical | **1 passed** | `/tmp/opencode/r2_ce_before.txt`, `r2_ce_after.txt`, backup `r2_ce_servers.py.bak` |
| REQ-QA-F-01 | `p_set_config` local gate + `audit_local_action` block removed (save-unconditionally behavior) | **2 failed** — both F-01 tests (allowed one at the exact audit-string assert; denied one on registry-changed/saved) | `cp` + `cmp` identical | **2 passed** | `/tmp/opencode/r2_f01_before.txt`, `r2_f01_after.txt`, backup `r2_f01_routes.py.bak` |
| REQ-QA-F-07 | 5th host `0.0.0.0` injected into `_ALLOWED_HOSTS` (the QA-cited mutation) | **1 failed** — `test_normalize_host_fails_closed_matrix` at `:798` exact-equality assert | `cp` + `cmp` identical | **1 passed** | `/tmp/opencode/r2_f07_before.txt`, `r2_f07_after.txt`, backup `r2_f07_routes.py.bak` |
| REQ-H3-doc | not applicable — docstring-only target, no executable assert; behavior already pinned by T-H3-4 (unchanged, still passing in the 621-run) | n/a (explained per packet allowance) | n/a | n/a | docstring `routes.py:1091-1098` + final gates |

### Round-2 Quality Verdicts

| Check | Command | Result |
|-------|---------|--------|
| Lint | `uv run ruff check src/ tests/` | PASS (`[]`, 0 findings — fixed 2 pre-existing ISC004 in the new F-01 audit asserts) |
| Format | `uv run ruff format --check src/ tests/` | PASS (89 files already formatted) |
| Tests | `uv run pytest -q` | PASS — **621 passed** (619 baseline + 2 new: T-F01-1, T-F01-2; F-07 + CE-001 strengthen existing tests, no count change) |

## Residual Risks (explicit, per packet)

| Risk | Evidence | Disposition |
|------|----------|-------------|
| **GIL held during starlark eval defers the route timeout to eval end** — `wait_for(0.5)` over an 11.799s workload raised `TimeoutError` at 12.048s (probe re-run 2026-09-23: starlark-pyo3 holds the GIL; the loop cannot run during eval). Route-level promptness therefore holds for GIL-releasing blocking work (T-H3-1, ~0.11s) but not for pure Starlark eval (T-H3-2 proves bounded, correct-surface, no-hang; arrival tracks eval end). | probe recorded 2026-09-23 in plan §Empirical Findings | **Root cause in `sandbox.py` (GIL/step-limit) OUT OF SCOPE — core owner's backlog** per packet; route fix + this record = this lane's closure |
| **Worker thread may linger after timeout** — `asyncio.to_thread` cannot cancel a running thread; on timeout the sandbox thread keeps running until its own work/sandbox-timeout completes, and loop/test teardown joins it. | Python concurrency semantics; bounded in tests by workload size | Documented; accepted residual until the sandbox root cause lands |
| Legacy unmodeled `oauth` JSON keys (incl. any stored port) dropped at parse — cannot be preserved by any save path | `models.py:687-691` + pydantic `extra=ignore` | Reported to core/model owner (Low), out of this packet's scope |

## Coverage Summary

- Unit coverage: engineering only — H1 (4), H2 (1: T-H2-3), H3 (1: T-H3-4), CE-001 (1) = 7 unit rows
- Integration coverage: H2 (3: T-H2-1/2/4), H3 (4: T-H3-1/2/3/5) = 7 integration rows, plus the full-suite client-host repair (E-H2-1)
- Evidence coverage: 4/4 REQ-IDs (H1, H2, H3, CE-001) with linked test evidence **plus a demonstrated fails-before revert cycle per fix**
- Acceptance criteria covered: 4/4 (each REQ has ≥1 regression test proven to fail on pre-fix behavior and pass on fixed behavior)
