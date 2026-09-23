# Quality Assurance Review: admin-ui-3.1.0 (v3.1.0 Unreleased)

**Reviewer:** quality-assurance (engineering domain, final engineering reviewer)
**Date:** 2026-09-23
**Verdict:** conditional
**Findings:** 6 (1 Medium, 5 Low; 0 Critical, 0 High)
**Re-gate 2026-09-23 (see addendum at end):** conditional — fixed 1 (F-04); persisting 5 (F-01 Medium, F-02/03/05/06 Low); new 1 Low (F-07); open total 6 (1 Medium, 5 Low).

Independent review — evidence below comes solely from my own command runs and my own curl captures against `127.0.0.1:8090`. No other reviewer's verdict was consulted or relied upon.

## Checklist

- [x] All acceptance criteria have tests — 12/14 requirements carry at least one test-level assertion; REQ-07 and REQ-14 rest on live evidence only (F-04, F-05).
- [x] All REQ-IDs traceable to test IDs — see Traceability; gaps named explicitly.
- [x] Unit + integration coverage as appropriate — TestClient integration over every admin route; pixel-level e2e is outside the suite's evidence channel (F-04).
- [x] Regression suite updated — 34 admin tests (new), `test_set_config_writes_json_only` (new), CSP asserts in `test_wave2_api.py:24-31` + `test_edgecases_gateway.py:323` (`test_csp_and_security_headers`).
- [x] No flaky tests introduced — two consecutive full runs green; hermetic DNS autouse fixture; no sleeps/real network in admin tests.
- [x] Coverage threshold met — 81.56% ≥ `fail_under = 80` (`pyproject.toml:79`).
- [~] Manual exploratory testing — 10-endpoint read-only curl pass (below); pixel geometry at 1440/900 cannot be measured over curl (F-04).

## Evidence (commands I ran, raw results)

| Claim | Command | Result |
|---|---|---|
| Suite count | `uv run pytest -q` (run 1, raw to file) | `605 passed in 7.35s`, exit=0 |
| Suite determinism | `uv run pytest -q` (run 2, raw to file) | `605 passed in 7.21s`, exit=0 |
| Admin count | `uv run pytest tests/test_admin_dashboard.py -q` (raw) | `34 passed in 0.52s`, exit=0 |
| No hidden deselection | `uv run pytest --collect-only -q` (raw) | `605 tests collected in 1.17s`, exit=0; pytest config has no `addopts` (`pyproject.toml:83-85`) |
| Lint | `uv run ruff check src/ tests/` | exit=0, no diagnostics |
| Format | `uv run ruff format --check src/ tests/` | exit=0, `89 files already formatted` |
| Coverage | `uv run pytest -q --cov=mcp_gway --cov-report=term` | `Required test coverage of 80.0% reached. Total coverage: 81.56%`, exit=0 |
| No skip/xfail masking | `grep -rn "pytest.mark.skip\|pytest.mark.xfail\|skipif" tests/` | no matches |
| No PII/secrets in tests | pattern scan (`Bearer `, `sk-`, `AKIA`, private keys, long literal passwords) | only synthetic markers: `TOPSECRET123` (test_admin_dashboard.py:28,377), `TOKEN`, `t` — no real credentials |
| Determinism (network) | `tests/conftest.py:18-57` autouse `_stub_dns_hermetic` | `socket.getaddrinfo` stubbed for every test; no `_real` fallback |
| Live server (GET-only) | curl `127.0.0.1:8090` → `/`, `/admin/servers`, `/admin/observability`, `/admin/partials/servers`, `/admin/servers/{Notes,Weather,Calendar}` | all `200`; no mutations issued; server untouched |

## Traceability (14-item live-review batch + toolbar alignment)

| # | REQ (packet wording) | Test ID / Evidence | Type | Status |
|---|---|---|---|---|
| 1 | Type-conditional add-form sections both directions | `test_responsive_drawer_and_checkbox_modal` asserts `data-type-section="remote"` + `"local"` (test_admin_dashboard.py:490-491); both `:has()` hide rules verified live in `<style>` (`layout.py:58-63`) | Unit + Live | pass |
| 2 | Modal close X (add + edit) | add: test asserts `for="add-server-modal"` (test:492, presence-only — matches trigger label too); edit: **no test assert**. Live: add modal 3× `for=` labels + 2× `aria-label="Close dialog"`; edit modal 3× `for="edit-config-modal"` + 2× close arias (`components.py:419-434`, `servers.py:254,589`) | Unit (weak) + Live | partial → F-06 |
| 3 | Web config edit/update as modal; error keeps modal open + input preserved + toast retarget; success closes + fresh values | error: `test_config_edit_error_keeps_card_and_reports` (test:402-419) — `HX-Retarget: #toast`, `HX-Reswap: outerHTML`, no `hx-swap-oob`, config content absent ⇒ `#detail-config` (and open modal with typed input) untouched, registry unchanged; success: `test_config_edit_roundtrip_preserves_secrets` (test:363-383) — toast + persisted values + `id="edit-config-modal"` + no `<details`; plus unescaped-HTML regression (test:386-399), non-htmx fallback (test:421-443), CSRF (test:446-456). Note: fresh values *inside the success response body* not directly asserted (swap target = fresh inner, `routes.py:920-927`) | Integration | pass (note) |
| 4 | Hub logo | test asserts generic `<svg` + "MCP Gateway" (test:41-48); hub path `M12 6.4V8.6…` verified live (`icons.py:39-48`, `layout.py:94`) | Unit (weak) + Live | partial → F-05 |
| 5 | .pyi signatures internal scroll (300px cap) | `test_detail_readonly_tools_poll_and_signature_scroll` asserts exact `max-h-[300px] overflow-y-auto` (test:509); confirmed live on detail page (`servers.py:369`) | Unit + Live | pass |
| 6 | Probes flush-right values + REFRESH right-aligned | `test_probes_values_flush_right` asserts flush class + button text (test:513-519); Refresh's right-align container `mt-4 flex justify-end` verified live only (`observability.py:133`) | Unit + Live | partial → F-05 |
| 7 | kv row spacing | **no test** asserts `py-3 border-b`; live: 5 occurrences on `/admin/observability`, 6 on detail page (`components.py:459-465`) | Live only | gap → F-05 |
| 8 | Mobile nav drawer open/close | `test_responsive_drawer_and_checkbox_modal` asserts `id="nav-drawer"`, `peer-checked/nav:block`, `for="nav-drawer"`, sidebar `hidden shrink-0 md:flex` (test:483-486); live: exactly 3 `for="nav-drawer"` labels (burger open + backdrop close + X close, `layout.py:138-173`) | Unit + Live | pass |
| 9 | Mobile toolbar: search full-width own line; REFRESH ALL / ADD SERVER equal-width row | container + search classes asserted (test:494-496); equal-width children `flex-1 justify-center md:flex-none` (Refresh) and `flex-1 md:flex-none` (Add) verified live only (`servers.py:215,226`) | Unit (partial) + Live | partial → F-05 |
| 10 | Active-first stable sort | `test_active_servers_listed_first` asserts order on page + partial (test:459-476); live grid: disabled `row-Calendar` (`opacity-60`) last, enabled Notes/Weather first (`data.py:63` stable sort). Within-group ordering not asserted with ≥2 per group | Integration + Live | pass (note) |
| 11 | Tools read-only via web; no Save-tools; PUT …/tools → 405 | `test_tools_have_no_web_mutation_path` (test:272-288): PUT→405, `.pyi` tools unchanged, GET→200; "Save tools" absent asserted on servers + detail (test:493,508); route registered `GET`-only (`routes.py:1132`); live: 0× "Save tools" | Integration + Live | pass |
| 12 | Tools list hx-poll every 5s exact URL | `test_detail_readonly_tools_poll_and_signature_scroll` asserts `hx-trigger="every 5s"` + URL string + element id (test:505-507); live: contiguous `hx-get="/admin/partials/servers/Weather/tools"` present (`servers.py:623-630`) | Unit + Live | pass |
| 13 | Edit section as modal | `test_config_edit_roundtrip_preserves_secrets`: `hx-put=…`, `id="edit-config-modal"`, no `<details` (test:380-383); live: 0× `<details>` on detail page | Integration + Live | pass |
| 14 | Header bottoms flush + ADD pill fully inside container @1440, wraps @900, no horizontal overflow (toolbar alignment) | class-level only: `md:flex-row md:items-end md:flex-wrap`, `flex gap-3 w-full md:w-auto shrink-0`, `w-full md:w-[320px]` (test:494-496) — all confirmed live. **Pixel geometry (flush/wrap/overflow at widths) has no automated test and no QA-verifiable in-repo live-verification artifact**; measurement needs a browser, outside my curl-only channel | Unit (classes) | gap → F-04 |

**Coverage summary:** 8 pass, 4 partial, 2 gap (REQ-07 live-only, REQ-14 pixel-evidence missing).

## Findings

**F-01 · Medium · Local branch of the web config write path is untested.**
`p_set_config` local branch (`src/mcp_gway/admin/routes.py:850-873` — command required, shlex, cwd gate, env parse) and the update-time policy re-gate `admin_update` (`routes.py:901-908`) have zero test coverage: grep for `admin_update` / local-config PUT across `tests/` returns no matches; all six config-PUT tests exercise the remote `Demo` only. The allow-list re-gate on web edit of a local server's command is a security boundary proven only by code reading — a regression there would ship silently (the analogous add-path deny *is* tested: `test_add_local_command_denied_by_policy`, test:171-188). Conditional impact ⇒ Medium. Owner: engineering.

**F-02 · Low · Happy-path web add never asserted.**
Success toast + `modal_closed("add-server-modal")` (`routes.py:589-593`) untested — grep for `Added … with` / `modal_closed` in tests: no matches. Only error paths covered (name required, policy deny, duplicate). Owner: engineering.

**F-03 · Low · SSRF revalidation on config save is a docstring claim without a web-level test.**
`p_set_config` docstring promises URL revalidation through the SSRF guard on every save (`routes.py:810-812`; model validator `models.py:744-749` → `validate_url_ssrf`); no test PUTs a blocked URL to `…/config`. Model-level SSRF coverage exists separately (`test_models_ssrf.py`, `test_p0_fixes.py:13-18`), so the guard itself is tested — only the web fail-closed wiring (`_reject` for that error class) is not. Owner: engineering.

**F-04 · Low · REQ-14 pixel claims lack QA-verifiable evidence.**
"Header bottoms flush + ADD pill inside container @1440 + wraps @900 + no horizontal overflow" cannot be asserted by HTML-class tests (test:494-496 prove the mechanism, not the geometry), and no in-repo live-verification artifact for this batch was found under `docs/specs/40_workspace/` (my docs grep surfaced only another reviewer's file, which I exclude as evidence per independence rule). Either attach browser measurements (rects/scrollWidth at 1440 and 900) to the gate packet or have the product owner narrow the requirement to class-level. Owner: engineering / product.

**F-05 · Low · Class-level test gaps for REQ-04, 06, 07, 09, 10, 12-adjacent.**
Six assertions verified by my live curl but absent from tests, so each would only be caught by live review: hub mark path (REQ-04); Refresh right-align container `mt-4 flex justify-end` (REQ-06); kv `py-3 border-b` spacing (REQ-07); equal-width `flex-1` toolbar children (REQ-09); within-group stable ordering with ≥2 enabled servers (REQ-10); contiguous exact `hx-get="…"` attribute rather than two substring asserts (REQ-12). Owner: engineering.

**F-06 · Low · Modal close-X assertions are presence-only for add and absent for edit.**
test:492 asserts `for="add-server-modal"` once — satisfied by the trigger label alone, so removal of the close X would not fail the test; no test asserts `for="edit-config-modal"` (REQ-02). Live evidence confirms both X buttons exist today (3 labels / 2 close arias each). Owner: engineering.

No Critical or High findings. Nothing here blocks release; F-01 is the only Medium and sits on a security boundary.

## Coverage

- Line coverage: 81.56% (4993 statements, 859 missed) — gate `fail_under = 80` **met**, run exit 0.
- Acceptance criteria coverage: 12/14 with automated assertions; 2/14 live-evidence-only (REQ-07 verified live by me, REQ-14 not verifiable in my channel).
- Suite: 605/605 across two consecutive runs (7.35s, 7.21s); admin subset 34/34 twice; 0 skipped, 0 xfailed.

## Verdict Rationale

**conditional** — every hard engineering claim in the packet reproduces independently: suite counts (605/34), lint/format clean, coverage gate, zero skip/xfail, hermetic determinism, synthetic data only, and all four mutation guards (CSRF missing/forged/form-field, loopback 403, tools PUT 405 with registry unchanged, CSP) verified green. Two conditions convert this to pass:

1. **F-01:** add a test covering the local branch of `PUT /admin/partials/servers/{name}/config`, including the update-time allow-list deny (`routes.py:901-908`) — or record a documented waiver (owner + justification + expiry) per guardrails.
2. **F-04:** attach live-verification evidence for REQ-14's pixel claims (browser measurements at 1440 and 900) to the gate packet — or an owner sign-off narrowing REQ-14 to class-level.

F-02, F-03, F-05, F-06 are Low hygiene items → backlog; they do not hold the gate.

---

## Re-gate addendum 2026-09-23

**Reviewer:** quality-assurance (engineering) — sign-off re-run after the 14-test remediation batch (REQ-H1/H2/H3, REQ-CE-001).
**Verdict:** **conditional** (unchanged) — **fixed 1 · persisting 5 (1 Medium, 4 Low) · new 1 Low (F-07) · 1 hygiene observation (O-1)**.
Independent: every number below comes from my own command runs this cycle (raw logs `/tmp/opencode/qa_regate_*.txt`) or my own file reads; no other reviewer's verdict relied upon.

### 1. Suite re-run (my commands, raw results)

| Claim | Command | Result |
|---|---|---|
| Suite + coverage | `uv run pytest -q --cov=mcp_gway --cov-report=term` | `619 passed in 16.17s`, `Required test coverage of 80.0% reached. Total coverage: 82.26%`, exit=0 (`qa_regate_pytest_cov.txt`) |
| Determinism | `uv run pytest -q` (run 2) | `619 passed in 11.33s`, exit=0 (`qa_regate_pytest_run2.txt`) — two consecutive green runs by me |
| No hidden deselection | `uv run pytest --collect-only -q` | `619 tests collected in 1.08s`, exit=0; 619 `::` ids (`qa_regate_collect.txt`) |
| Admin subset | `uv run pytest tests/test_admin_dashboard.py -q` | `48 passed` (34 pre-existing + 14 new), exit=0 |
| Lint / Format | `uv run ruff check src/ tests/` · `uv run ruff format --check src/ tests/` | `All checks passed!` exit=0 · `89 files already formatted` exit=0 |
| 0 skips/xfails | run summaries show only `passed`; `grep pytest.mark.skip\|xfail\|skipif tests/` | 0 matches; runtime `pytest.skip(` = 4 pre-existing posix guards (`test_edgecases_oauth.py:44,51`, `test_edgecases_models_registry.py:188,199`), none triggered (0 skipped observed) |
| Synthetic data only | read of new-test constants (`tests/test_admin_dashboard.py:542-550`) | placeholder UUID + `synthetic-oauth-secret-001` + pre-existing placeholder bearer marker (`:38`) — no real credentials |
| Uncommitted-state claim honest | `git status --porcelain` · `git log --oneline -2` | batch files M/??; last commit `91dd912` (gate report only) — matches `TEST_MATRIX.md:25` commit-column note |

Coverage gate: 82.26% ≥ `fail_under = 80` (`pyproject.toml:79`) — up from prior 81.56%; 5036 statements, 839 missed.

### 2. Audit of the 14 new tests (behavior vs class, fails-before consistency, mutation-think)

| Group | Behavior or class? | Fails-before log vs test names | Mutation-think (passes with fix reverted?) |
|---|---|---|---|
| REQ-H1 (4 tests, `:553,:578,:604,:627`) | **Behavior** — full-stack PUT → registry-state byte-compare of stored `clientId`/`clientSecret` | `h1_before.txt`: `2 failed, 3 passed, 43 deselected` — failures are exactly T-H1-1 (byte-identical assert at `:573`) and T-H1-4 (sentinel, `:646`); `h1_after.txt`: `5 passed` ✓ consistent with `TEST_MATRIX.md:33` | T-H1-2/T-H1-3 pass on revert (documented complements: blank fields never entered the buggy branch); core fix pinned by 2 fails-before tests |
| REQ-H2 (4 tests, `:651,:685,:701,:728`) | **Behavior** — 6 surfaces incl. mutation PUT → 403 **and registry unchanged** (`:674`), CSRF-ordering probe (`:680-682`, answers "loopback" never "CSRF token mismatch"), 7 loopback variants → 200, non-admin over-block guard | `h2_before.txt`: `1 failed, 3 passed` — `assert 200 == 403` at `:658` (evil Host reached index); `h2_after.txt`: `4 passed` ✓ matches `TEST_MATRIX.md:34` | T-H2-2/3/4 pass on revert — explicitly documented "pass pre-fix by design" (over-block guards); T-H2-1 is the fails-before anchor. Paired design: an over-blocking gate would fail T-H2-2 ✓. **One gap → F-07** |
| REQ-H3 (5 tests, `:747,:773,:790,:814,:827`) | **Behavior** — headers (`HX-Retarget/HX-Reswap`), elapsed budgets, redirect+landing round-trip; clamp matrix is unit but wired straight to `routes.py:1090-1101` | `h3_before.txt`: `3 failed, 2 passed, 43 deselected` — exactly T-H3-1 (`:766`), T-H3-2 (`:785`), T-H3-3 (`:808`) fail; `h3_after.txt`: `5 passed` ✓ matches `TEST_MATRIX.md:35` | T-H3-4/T-H3-5 pass on revert (helpers kept; fast path never timed out pre-fix) — documented complements |
| REQ-CE-001 (1 test, `:841`) | **Class/structure** (not pixel) — container+wrapper adjacency string, pill/trigger classes, hx target | `ce_before.txt`: `1 failed` at the adjacency assert `:845-848`; `ce_after.txt`: `1 passed` ✓ matches `TEST_MATRIX.md:36` | Would pass only if the revert restored the exact structure — the revert IS the structure, so it fails ✓ honest mechanism guard |

**`test_execute_timeout_real_starlark_does_not_hang` (`:773-787`) — honest, not mocked.** No monkeypatch in the test body; code flows HTTP → `p_codemode` (`routes.py:1117,1156-1159` `wait_for(to_thread(...))`) → `code_mode.execute_tool_code` (`code_mode.py:291-303`) → real `StarlarkSandbox`. My solo run: `1 passed in 0.71s`, call duration **0.61s** (`qa_regate_starlark_alone.txt`) — matches the lane's claimed ~0.6-0.64s. The `h3_before` failure (success surface returned, no retarget) proves the eval really executes pre-fix. **Can it hang the suite?** Bounded by the fixed 1e8-iteration workload (GIL defers the route timeout to eval end — documented residual `TEST_MATRIX.md:54`); `elapsed < 8.0` (`:787`) is ~13× above measurement, so a slow machine produces a *failure*, not an infinite hang. Residual: no pytest-timeout watchdog exists (grep `timeout|addopts` in `pyproject.toml` → coverage config only) → **O-1 (Low, backlog)**.

**Tests that pass with the fix reverted:** 7 of 14 (T-H1-2, T-H1-3, T-H2-2, T-H2-3, T-H2-4, T-H3-4, T-H3-5). All are complements/over-block guards documented as such in `TEST_MATRIX.md:33-35`; every REQ keeps ≥1 demonstrated fails-before test (H1×2, H2×1, H3×3, CE×1 = 7). Not a defect.

**Fails-before logs vs names: consistent across all four groups** (failure names, pass/deselect arithmetic 43/44/43/47 = 48−selected, after-counts 5/4/5/1, final `final_pytest.txt` `619 passed` — reproduced by my own two runs).

### 3. Prior conditions — status

| # | Severity | Condition as written | Status | Evidence |
|---|---|---|---|---|
| F-01 | Medium | Test the local branch of `PUT …/config` incl. update-time allow-list re-gate (`admin_update`), **or** record a waiver | **PERSISTS** | `grep admin_update tests/` → **0 matches** (only `routes.py:963` + docs); config-PUT tests all target remote `Demo` (`grep "/config" tests/test_admin_dashboard.py` → 15 hits, none with local command); local branch live at `routes.py:877,912,961-963` still test-free; no waiver — `GATE_REPORT.md:68-71` "Not invoked — no waiver requested". Security-reviewer's runtime spot-check (`security-reviewer.md:37`) proves today's behavior, not regression-proofing. Owner: engineering |
| F-04 | Low | Attach browser measurements for REQ-14 (1440 + 900) to the gate packet **or** owner sign-off narrowing to class-level | **CLOSED** | Attached: `GATE_REPORT.md:61-64` carries `bottoms=91 flush, add.r=1416 ≤ header, 900px wrap, overflowX false` (+ 390 Δ=0 session-supplied for CE-001). **Ruling, stated flat: session-recorded measurements attached to the packet are acceptable evidence for REQ-14 — my checklist demands "manual exploratory testing done (if applicable)", NOT an automated pixel test; my condition as written accepted attach-as-evidence and I will not move the goalpost post-hoc.** Caveat recorded: not CI-enforced — an automated pixel test is optional backlog, not a condition. Independent re-measurement attempted this cycle and unavailable in my channel: `browser.tabs.open` → harness `[browser.disconnected]`; acceptance rests on packet attachment, corroborated by in-repo measurement records `review-refuter.md:23-26` (RF-011/RF-012 rects at 1440/900) |

### 4. Prior Lows — re-verified

| # | Status | Evidence this cycle |
|---|---|---|
| F-02 happy-path add | **PERSISTS** | `grep "Added \|modal_closed" tests/` → 0 matches; add success toast + `modal_closed("add-server-modal")` (`routes.py:589-593` per prior read) still unasserted. Owner: engineering |
| F-03 SSRF-on-save web wiring | **PERSISTS** | No test PUTs a blocked URL to `…/config`; SSRF coverage remains model/transport-level only (`test_models_ssrf.py`, `test_p0_fixes.py:13-18`, `test_transport_client_ssrf.py`). Owner: engineering |
| F-05 class-level gaps | **PERSISTS (5 of 6 sub-items)** | Still absent from tests (grep, 0 matches): hub mark path `M12 6.4` (REQ-04), `mt-4 flex justify-end` (REQ-06), `py-3 border-b` (REQ-07), within-group ≥2 ordering (`test:469-486` = 1 enabled + 1 disabled only, REQ-10), contiguous `hx-get` attr (`test:516-517` still two substrings, REQ-12). **Sub-item closed:** REQ-09 equal-width `flex-1` children now asserted by T-CE-1 (`test:849-850`). Owner: engineering |
| F-06 modal close-X | **PERSISTS** | `test:502` still single presence `for="add-server-modal"` (satisfied by trigger label alone); `grep 'for="edit-config-modal" tests/` → 0 matches (`test:392` asserts `id=` only). Owner: engineering |

### 5. New findings this cycle

**F-07 · Low · T-H2-3 does not assert allow-list exactness; TEST_MATRIX overstates it.**
`tests/test_admin_dashboard.py:715-725` asserts the 4 known hosts ∈ `_ALLOWED_HOSTS` and 6 named hosts ∉ it — it never asserts set equality. Mutation proof: adding a 5th host (e.g. a LAN IP) to `_ALLOWED_HOSTS` (`routes.py:48`) leaves the test green. `TEST_MATRIX.md:15` claims the test proves the set "contains exactly the 4 allowed values" — wording overstates the assert (the source today *is* exactly 4, verified at `routes.py:48`). Impact: an over-allow regression on a security boundary slips this test (T-H2-1 still pins `evil.example.com` specifically). Fix direction (not applied — no freelance fixes): set-equality assert + correct the matrix wording. Owner: engineering (execute lane).

**O-1 · Low hygiene · no suite watchdog behind the real-Starlark timing test.**
`test:787` (`elapsed < 8.0`) is the only bound; no pytest-timeout in `pyproject.toml`; sandbox has timeout-only, no step limit (`sandbox.py:67,113`). Current workload = 0.61s (my solo run) → honest and safe today; workload/interpreter growth would degrade to a multi-minute stall before failing. Documented residual `TEST_MATRIX.md:54-55` covers the GIL root cause; watchdog = backlog. Owner: engineering.

### 6. Traceability refresh (remediation REQs — verified against reality, not trusted from the lane doc)

| REQ | Test IDs (tests/test_admin_dashboard.py) | Type | Evidence chain | Status |
|---|---|---|---|---|
| REQ-H1 OAuth per-field merge | T-H1-1 `:553`, T-H1-2 `:578`, T-H1-3 `:604`, T-H1-4 `:627` | Integration (PUT → registry byte-compare) | `h1_before.txt` 2F/3P (named) → `h1_after.txt` 5P; fix `routes.py:855-867` (sentinel helper), `:948-951` (merge); my runs: 619 green ×2 | verified |
| REQ-H2 Host gate | T-H2-1 `:651`, T-H2-2 `:685`, T-H2-3 `:701`, T-H2-4 `:728` | Integration + unit | `h2_before.txt` 1F/3P (`assert 200 == 403`) → `h2_after.txt` 4P; gate `routes.py:48,104,136`; caveat F-07 | verified (F-07 open) |
| REQ-H3 execute timeout | T-H3-1 `:747`, T-H3-2 `:773`, T-H3-3 `:790`, T-H3-4 `:814`, T-H3-5 `:827` | Integration + unit | `h3_before.txt` 3F/2P (named) → `h3_after.txt` 5P; wiring `routes.py:1090-1101,1104-1114,1156-1170`; T-H3-2 solo 0.61s real eval (`code_mode.py:291-303`); O-1 residual | verified |
| REQ-CE-001 toolbar floors | T-CE-1 `:841` | Unit (class structure) | `ce_before.txt` 1F (adjacency `:845-848`) → `ce_after.txt` 1P; wrapper `servers.py:211-212,228`; pixel Δ=0 @390 session-recorded (not in-repo — info for refuter/orchestrator; my F-04 covers REQ-14 only) | verified (class-level; pixel by attachment) |

**TEST_MATRIX.md reality check:** test names/counts ✓ (all 14 found at the cited behavior, file 48, suite 619 = 605+14, collect 619); fails-before logs ✓ (names, ratios, deselect arithmetic, after-runs, `final_pytest.txt` 619 — reproduced independently); claimed T-H3-2 measurement ✓ (my 0.61s); lint/format/test verdicts ✓ (reproduced); commit column ✓ (git state matches). **One discrepancy → F-07** ("exactly the 4" wording vs membership-only asserts).

### 7. Updated coverage

- Line coverage: **82.26%** (5036 stmts, 839 missed) ≥ 80 gate — run exit 0.
- Suites: **619/619 ×2 consecutive runs** (16.17s with cov, 11.33s); admin subset 48/48; T-H3-2 solo 1/1 (0.61s); 0 skipped, 0 xfailed, collect = 619.
- Acceptance coverage: original batch 12/14 automated + REQ-07/REQ-14 attachment-based (unchanged); remediation batch **4/4** (H1/H2/H3/CE-001) with demonstrated fails-before cycles.

### 8. Re-gate verdict rationale

**conditional** — everything the packet claims reproduces in my own runs (619/619 ×2, 48/48 admin, lint/format clean, coverage 82.26%, zero skips, synthetic-only data, fails-before logs consistent with test names, TEST_MATRIX faithful but for F-07's wording). **F-04 is closed**: measurements are attached to the gate packet and my checklist never demanded an automated pixel test. **One condition remains — F-01 (Medium):** a test covering the local branch of `PUT /admin/partials/servers/{name}/config` including the update-time allow-list deny + `admin_update` audit (`routes.py:877,912,961-963`) — or a recorded waiver (owner + justification + expiry). F-02/F-03/F-05/F-06/F-07 + O-1 are Low hygiene → backlog; they do not hold the gate.

---

## Round-2 re-check addendum 2026-09-23

**Reviewer:** quality-assurance (engineering domain) — final condition re-check after the round-2 batch (F-01 tests, F-07 set-equality, CE-001 wrapper, CE-007 docstring).
**Verdict:** **pass** — the sole remaining condition (F-01) is **CLOSED**; F-07 closed by fix; F-04 already closed; F-02/F-03/F-05/F-06 + O-1 remain Low hygiene → backlog (explicitly not conditions).
Independent: every number below comes from my own command runs this cycle or my own file reads; no other reviewer's or the lane's verdict relied upon. Live server touched **read-only GET only** (never killed/restarted); `~/.config/mcp-gateway` default registry never touched; zero source edits, zero commits by me.

### 1. Suite / gates re-run (my commands, this cycle)

| Claim | Command | Result |
|---|---|---|
| Suite (run 1) | `uv run pytest -q` | **621 passed**, exit=0 |
| Suite + coverage | `uv run pytest -q --cov=mcp_gway --cov-report=term` | **621 passed in 15.72s**; `Required test coverage of 80.0% reached. Total coverage: 82.79%` (5036 stmts, 818 missed), exit=0 |
| Suite determinism + skip/xfail | `uv run pytest -q -rs` (run 3) | **621 passed in 10.97s**; no skip/xfail summary lines (0 skipped, 0 xfailed) |
| No hidden deselection | `uv run pytest --collect-only -q` + count of `::` ids | **621** test ids collected |
| Admin subset | `uv run pytest tests/test_admin_dashboard.py -q` | **50 passed** (48 pre-round-2 + 2 new F-01 tests) |
| Lint | `uv run ruff check src/ tests/` | exit=0, no findings |
| Format | `uv run ruff format --check src/ tests/` | exit=0, `89 files already formatted` |
| No skip markers | `grep -rn "pytest.mark.skip\|pytest.mark.xfail\|skipif" tests/` | **0 matches** |
| Coverage gate | `pyproject.toml` `fail_under = 80` | 82.79% ≥ 80 **met** |
| Synthetic data in new tests | read of T-F01-1/2 bodies | `python3 -m allowed_mod`, `totallynotallowed --flag`, `python3` allow-list env — all synthetic; no secrets/PII |
| Live server (GET-only) | `curl 127.0.0.1:8090/admin/servers` | 200; renders the exact new wrapper markup `<div class="flex gap-3 w-full md:w-auto shrink-0"><div class="flex flex-1 md:flex-none"><button` + 1× `class="relative flex-1 md:flex-none"` — deployed code matches source |

### 2. F-01 — behavior audit of T-F01-1 / T-F01-2 → **CLOSED**

| Test | Behavior or class? | What it really proves | Evidence |
|---|---|---|---|
| T-F01-1 `test_local_config_put_allowed_command_saves_and_audits_admin_update` (`tests/test_admin_dashboard.py:475-512`) | **Behavior** — full-stack `PUT …/Loc1/config` through the real `p_set_config` local branch (`routes.py:907-930`: command required, `shlex.split`, cwd/env parse) and the update-time re-gate + audit (`routes.py:959-966`) | 200 + "Config updated for Loc1."; **registry state read back**: `command == ["python3","-m","allowed_mod"]`, `timeout == 7000`, `enabled is True`; **exact audit** from caplog on `mcp_gway.core.policy`: `local action=admin_update name=Loc1 binary=python3 allowed=True reason=allow_list` — not class-only asserts | mutation `/tmp/opencode/r2_f01_before.txt`: **2 failed, 48 deselected** (this test failed at the exact audit assert `:507` when the route's gate+audit block was removed); `r2_f01_after.txt`: 2 passed; backup `r2_f01_routes.py.bak` present |
| T-F01-2 `test_local_config_put_denied_command_rejected_registry_unchanged` (`tests/test_admin_dashboard.py:515-549`) | **Behavior** — deny path on the same security boundary: env unset → `DEFAULT_ALLOW_LIST` live | normal `_reject` toast surface (`HX-Retarget: #toast`, `HX-Reswap: outerHTML`, no `hx-swap-oob`), message `command not allowed: totallynotallowed` + `[reason=not_allowlisted]`, **registry command+timeout byte-unchanged** vs pre-PUT snapshot (`:536-538`), **exact audit** `binary=totallynotallowed allowed=False reason=not_allowlisted` | same `r2_f01_before.txt`: this test failed at `:531` (`assert None == '#toast'` — with gate removed the save succeeded and returned the success page; the registry-unchanged assert at `:536-538` would also fail); after: 2 passed |

Mutation-proof verdict: **real** — removing the route's local gate+audit block fails both tests (2F before / 2P after, cmp-verified restore per lane log; backups exist on disk). F-01's condition as written ("test covering the local branch … including the update-time allow-list deny + `admin_update` audit, or a waiver") is **met at its security seam**; no waiver needed. Honest residual (hygiene, not a condition): the local branch's non-security sub-paths — empty-command error (`routes.py:909-910`), cwd gate (`:916-923`), env parse (`:924-930`) — are still not exercised via the web PUT; their helpers carry unit coverage elsewhere (`check_cwd` → `tests/test_edgecases_policy.py`; `parse_envs` → `tests/test_edgecases_core.py`, `tests/test_feat006_harden.py`; grep `Command is required for local` in tests → 0).

### 3. F-07 — host-set exactness → **CLOSED**

- Assert is now exact-set equality: `assert set(_ALLOWED_HOSTS) == {"127.0.0.1", "localhost", "::1", "[::1]"}` at `tests/test_admin_dashboard.py:798` (test at `:784-807`), alongside the unchanged fail-closed matrix.
- Mutation-proof (the exact QA-cited mutation): `/tmp/opencode/r2_f07_before.txt` — 5th host `0.0.0.0` injected into `_ALLOWED_HOSTS` → **1 failed** at `:798` (`Extra items in the left set: '0.0.0.0'`); `r2_f07_after.txt` → 1 passed; backup `r2_f07_routes.py.bak` present. The prior falsification ("adding a 5th host leaves the test green") no longer holds.

### 4. Round-2 items (c) CE-001 wrapper and (d) CE-007 docstring — verified in my channel

- **CE-001 source:** `src/mcp_gway/admin/pages/servers.py:211-212` — container `div({"class": "flex gap-3 w-full md:w-auto shrink-0"})` wraps wrapper `div({"class": "flex flex-1 md:flex-none"})` (now a flex container carrying the shared basis); modal root `cls="flex-1 md:flex-none"` at `:228`. Strengthened test `test_toolbar_flex_children_share_identical_floors` (`tests/test_admin_dashboard.py:923-937`) asserts the **contiguous** container→wrapper→`<button` adjacency string (`:927-931`) + modal root class + pill classes + hx/label intact.
- **Mutation:** `/tmp/opencode/r2_ce_before.txt` → 1 failed at the `:927` adjacency assert (wrapper class reverted to block) / `r2_ce_after.txt` → 1 passed; backup `r2_ce_servers.py.bak` present.
- **Live corroboration (read-only):** the served HTML on `127.0.0.1:8090` contains the exact adjacency string and 1× modal root class (table §1).
- **Pixel Δ=0 @375/390/414/600:** session-supplied by the orchestrator — **not located in-repo** by my greps (`Δ=0`, width-sweep tables across `docs/specs/40_workspace/execute/` + `quality-gate/` return only the *pre-fix* refuter sweeps and the TEST_MATRIX fails-before Δs). Informational for the refuter/COND-CE owner: CE-001's pixel equality is **refuter's condition, not mine**; my verified facts are source + strengthened test + mutation proof + live markup. md+ Δ7.34 = natural pill widths on the desktop layout is consistent with the refuter's own table (`review-refuter.md:95`); scope call (mobile/tablet equal-row) belongs to the requirement owner, not this review.
- **CE-007 docstring:** `src/mcp_gway/admin/routes.py:1091-1098` matches the matrix quote — clamp `[0.1, 30]`s default 10, "response fires at eval completion", GIL-held eval can delay response and briefly stall the loop until the sandbox gains interrupt/step-limit, worker abandoned after deadline; the old "Neither pins nor starves" claim is gone. Function body `:1099-1105` unchanged in shape and still pinned by T-H3-4, which passes in all three of my 621-runs.

### 5. TEST_MATRIX.md round-2 rows vs reality

| Round-2 row | Claimed | Reality (mine) | Match |
|---|---|---|---|
| T-CE-1 strengthened | `tests/test_admin_dashboard.py:923`, adjacency with `flex flex-1 md:flex-none` | found at `:923`, assert at `:927-931` exact | ✓ |
| E-H3-doc-1 | docstring `routes.py:1091-1098`, no behavior change | read confirms; T-H3-4 green in 621-run | ✓ |
| T-F01-1 / T-F01-2 | `:475` / `:515`, mutation 2F→2P | found at `:475`/`:515`; logs show 2 failed→2 passed, 48 deselected (50−2) | ✓ |
| T-H2-3 strengthened | `:784`, equality at `:798`, mutation `0.0.0.0` 5th host 1F→1P | found at `:784`/`:798`; logs 1 failed→1 passed, 49 deselected (50−1) | ✓ |
| Round-2 verdicts | lint PASS · format 89 · tests 621 (619+2) | reproduced exactly ×3 runs; admin file = 50 = 48+2 | ✓ |
| Mutation demo logs | `r2_ce/f01/f07_{before,after}.txt` + 3 backups | all 9 files exist, contents consistent with row descriptions (incl. matrix's "denied one on registry-changed/saved" = first failure at `:531` success surface — substance faithful) | ✓ |
| Commit column `uncommitted¹` | no commits this cycle | `git status` shows batch files M/?? (incl. `tests/test_admin_dashboard.py`, `src/mcp_gway/admin/`); last commit `91dd912` | ✓ |
| Lint history "fixed 2 pre-existing ISC004" | historical claim | not post-hoc verifiable; current lint clean (my run) | unverifiable-history, immaterial |

No round-2 discrepancy found. (Pre-existing F-07 wording issue at matrix line 15 — "contains exactly the 4" vs old membership asserts — was corrected by the fix itself: the assert at `:798` now *is* exact equality.)

### 6. Prior Lows — re-verified, none rose above Low

| # | Status | Evidence this cycle |
|---|---|---|
| F-02 happy-path add toast | **Low → backlog (not a condition)** | `grep -rn "Added \|modal_closed" tests/` → 0 matches; unasserted surface unchanged (`routes.py:627-637`). Hygiene only: error paths are covered, success toast is display-only |
| F-03 SSRF-on-save web wiring | **Low → backlog** | no test PUTs a blocked URL to `…/config` (grep 0); guard itself tested at model/transport level. Docstring claim at `routes.py:865-869` unchanged |
| F-05 class-level gaps | **Low → backlog (unchanged)** | grep `M12 6.4` / `mt-4 flex justify-end` / `py-3 border-b` in tests → 0 matches (REQ-04/06/07 sub-items); REQ-09 sub-item already closed by T-CE-1. All remain live/curl-verifiable hygiene |
| F-06 modal close-X presence-only | **Low → backlog (unchanged)** | `grep 'for="edit-config-modal"' tests/` → 0; `for="add-server-modal"` still satisfied by trigger label alone. Live evidence (prior cycles) confirms both X buttons exist today |
| O-1 no suite watchdog | **Low hygiene → backlog (unchanged)** | `grep -n "addopts\|timeout" pyproject.toml` → no matches; T-H3-2 still bounded only by `elapsed < 8.0` (real workload measured ~0.6s by me last cycle) |

None of F-02/F-03/F-05/F-06 carries new impact evidence this cycle (no severity driver changed: no auth/secret/data-loss surface added) → they stay **backlog-class Lows, explicitly not conditions**.

### 7. Updated condition table

| # | Severity | Condition as written | Status | Evidence |
|---|---|---|---|---|
| F-01 | Medium | Test the local branch of `PUT …/config` incl. update-time allow-list re-gate + `admin_update` audit, **or** record a waiver | **CLOSED** | T-F01-1 `:475`, T-F01-2 `:515` — behavior tests (registry read-back + exact audit strings); mutation 2F→2P (`r2_f01_*.txt` + backup); `grep admin_update tests/` now → 5 matches in `test_admin_dashboard.py`; no waiver needed |
| F-04 | Low | Browser measurements for REQ-14 attached **or** sign-off narrowing | **CLOSED** (prior cycle) | `GATE_REPORT.md:61-64` attachments; ruling recorded in re-gate addendum §3 |
| F-07 | Low | Set-equality assert on `_ALLOWED_HOSTS` + matrix wording | **CLOSED** | `:798` exact equality; mutation `0.0.0.0` → 1 failed (`r2_f07_*.txt` + backup) |
| F-02 | Low | Happy-path add toast assert | backlog (not a condition) | unchanged, §6 |
| F-03 | Low | Web-level SSRF-on-save test | backlog (not a condition) | unchanged, §6 |
| F-05 | Low | Six class-level test gaps | backlog (not a condition; REQ-09 sub-item closed) | unchanged, §6 |
| F-06 | Low | Modal close-X assertions | backlog (not a condition) | unchanged, §6 |
| O-1 | Low hygiene | pytest-timeout watchdog | backlog (observation, not a condition) | unchanged, §6 |

### 8. Round-2 re-check verdict rationale

**pass** — my sole condition F-01 is closed by two demonstrated, mutation-proof behavior tests on the security seam it named; F-07 is closed by a mutation-proof exact-equality assert; every round-2 claim in TEST_MATRIX reproduces in my own three suite runs (621/621 ×3, 50/50 admin, collect 621, coverage 82.79% ≥ 80, lint/format clean, 0 skips/xfails), mutation logs exist on disk and are consistent with the asserted test names/line numbers, the deployed live server (read-only GET) serves the fixed markup, and no finding carries evidence of rising above Low. Remaining Lows (F-02/03/05/06, O-1) are backlog hygiene by their original severity — **no condition remains open from this review**. Non-blocking info to other owners: CE-001 round-2 Δ pixel numbers were not found in-repo by my greps (session-supplied; refuter's COND-CE to accept), and the local-branch cwd/env/empty-command sub-paths stay web-untested (unit-covered helpers).
