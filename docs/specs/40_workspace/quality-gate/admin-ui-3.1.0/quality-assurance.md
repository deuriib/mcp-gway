# Quality Assurance Review: admin-ui-3.1.0 (v3.1.0 Unreleased)

**Reviewer:** quality-assurance (engineering domain, final engineering reviewer)
**Date:** 2026-09-23
**Verdict:** conditional
**Findings:** 6 (1 Medium, 5 Low; 0 Critical, 0 High)

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
