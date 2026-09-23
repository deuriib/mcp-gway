# Reliability Review: admin-ui-3.1.0 (v3.1.0 Unreleased batch)

**Reviewer:** review-reliability (engineering domain, quality-gate)
**Date:** 2026-09-23
**Verdict:** closed (2 High findings block; remediate + re-run gate)

**Scope:** reliability only — route-handler correctness, error paths, failure modes,
htmx vs non-htmx divergence, error surfacing, determinism, timeouts. Read-only: no
source edits, no commits. Artifact is the only file written.

**Files reviewed:** `src/mcp_gway/admin/{routes,data,components,layout,pages/*}.py`,
`src/mcp_gway/registry.py`, `src/mcp_gway/gateway.py` (admin mounting, app.state),
`src/mcp_gway/core/client.py`, `src/mcp_gway/{sandbox,code_mode,models,oauth,cli}.py`,
`tests/test_admin_dashboard.py`, `tests/conftest.py`.

**Commands run (evidence):**
- `uv run python /tmp/opencode/reliability_proofs.py` (scratch, /tmp only; DNS stubbed
  the same way `tests/conftest.py:18-57` does) → proofs 1-9, quoted per finding.
- Three sandbox timing probes (`uv run python -u -c ...`) → quoted under RL-002.
- `uv run pytest tests/test_admin_dashboard.py::test_config_edit_roundtrip_preserves_secrets -q`
  → `1 passed` (spot check of the on-record suite).

---

## Checklist

- [ ] **Error paths handled explicitly** — PARTIAL. Config-save and policy paths degrade
      honestly (`routes.py:609-620`, `909-912`, `977-1008`); registry write paths and the
      `.pyi` read path do not (RL-003, RL-004).
- [ ] **No swallowed exceptions** — PARTIAL. Swallowed failures that have a surfaced
      fallback are fine (`routes.py:558-559` detect-transport → orange 0-tools toast);
      ones that reach the user as a misleading/empty state are findings (RL-009) or raw
      500s (RL-003, RL-004).
- [ ] **Input validation at boundaries** — PARTIAL. Values are validated (int parse,
      shlex, parse_envs/headers, policy gates, `MCPServerConfig` model), but one input is
      accepted and discarded (RL-005) and *absent* fields have three different semantics
      in one handler (RL-006); no upper bound on `timeout` (RL-012).
- [x] **Deterministic behavior** — `server_rows` stable enabled-first sort
      (`data.py:63`), notice keys allowlisted (`routes.py:154`), per-process CSRF stable
      (`gateway.py:375`). Caveat: non-idempotent toggle under double-click (RL-011, Low).
- [ ] **Edge cases tested (empty, null, max, boundary)** — PARTIAL. Suite covers empty
      name, duplicates, CSRF, loopback gate, unreadable-config redirect, non-htmx config
      save (`tests/test_admin_dashboard.py:130,148,158,237,402,421`). Gaps: OAuth fields
      on edit (RL-001), registry write IO errors (RL-003), `.pyi` read errors (RL-004),
      partial-form PUT semantics (RL-006 — the suite's own `:394` PUT silently disables
      the fixture server, unasserted).
- [ ] **Idempotency where required** — PARTIAL. Policy marker create/remove idempotent
      + `OSError` caught (`routes.py:977-1008`; `FileNotFoundError ⊂ OSError`). Toggle is
      inherently non-idempotent with no double-click guard (RL-011).
- [ ] **Timeouts on external calls** — FAIL. Bounded: `detect_transport`
      (`routes.py:554`), `discover_tools` (`core/client.py:294-299`), OAuth callback wait
      300s (`models.py:28`, `oauth.py:183`). **Not bounded in practice:** sandbox
      execution via `p_codemode` (RL-002) — nominal timeout empirically does not fire.

---

## Failure Modes Analyzed

| ID | Failure Mode | Expected Behavior | Handled? |
|----|--------------|-------------------|----------|
| FM-001 | Missing/corrupt config on read | honest notice/404, never 500 | yes (`routes.py:271-284, 609-620`; tests `:237,253`) |
| FM-002 | Registry write IO error (disk full/perm) on add/toggle/remove/refresh | toast + state kept | **no → RL-003** (raw 500, no htmx feedback) |
| FM-003 | `.pyi` read PermissionError on detail page | same degrade as config read | **no → RL-004** (500 vs graceful redirect) |
| FM-004 | Partial/malformed config PUT body | absent field = keep stored value | **no → RL-006** (3 inconsistent semantics in one handler) |
| FM-005 | Missing/invalid CSRF on mutation | 403 fail-closed | yes (`routes.py:86-108`; tests `:130,140,446`) |
| FM-006 | Admin hit while `serve_host` non-loopback | 403 | yes (`routes.py:96-101`; test `:148`) |
| FM-007 | Remote detect/discover hang | bounded wait | yes (`routes.py:554`; `client.py:299`) |
| FM-008 | OAuth callback never returns | bounded | yes, 300s (`models.py:28`); note: row Refresh on a remote+OAuth server runs the flow inline up to 300s + opens a browser (`client.py:356-378`) — CLI-parity, bounded, accepted |
| FM-009 | Runaway sandbox code from Code Mode execute | timeout delivered, request bounded | **no → RL-002** (timeout never fires; process-wide stall) |
| FM-010 | htmx receives 500 | error toast/retarget | **no → RL-003** (htmx default: no swap → user sees nothing) |
| FM-011 | Unknown `notice` key / unknown codemode `mode` | empty / explicit error | notice yes (`routes.py:154`); mode **no → RL-009** |
| FM-012 | Toast lifecycle after render | auto-dismiss | **no → RL-010** (dismiss endpoint orphaned) |
| FM-013 | Non-htmx submit of Add form | POST reaches handler | **no → RL-007** (no method/action → 405) |
| FM-014 | OAuth edit fills only one of three fields | blank fields keep stored values (per-field placeholder contract) | **no → RL-001** (stored id/secret destroyed) |
| FM-015 | Add form `oauth_port` entered | persisted or used | **no → RL-005** (silently dropped) |
| FM-016 | Double-click Enable/Disable or Refresh | serialized or disabled elt | **no → RL-011** (lost flip race; last-write-wins otherwise) |
| FM-017 | Background auth task fails | logged + user can refresh | partial — log-only by design (message tells user to refresh); task has no strong ref → **RL-013** (Low) |
| FM-018 | Empty registry | empty states | yes (`servers.py:113-118`, `routes.py:673-674`) |
| FM-019 | `timeout` input ≤0 or huge | rejected or clamped | ≤0 clamped to 5s (`client.py:295-296`); no upper bound → **RL-012** (Low) |

---

## Findings

| ID | Severity | Location | Finding | Evidence | Owner |
|----|----------|----------|---------|----------|-------|
| RL-001 | **High** | `admin/routes.py:888-896` (vs contract `admin/pages/servers.py:550-569`) | **Config edit wipes stored OAuth credentials on partial fill.** Each OAuth input renders placeholder "blank keeps current" (per-field contract), but the handler replaces the whole `OAuthConfig` whenever *any* of the three fields is non-blank: `clientId=client_id or None, clientSecret=client_secret or None`. Saving with only `oauth_scope` filled destroys stored `clientId` (replaced by the model's uuid4 default) and `clientSecret` (→ `None`) — silently, behind a green "Config updated" toast. Stored secrets are masked in the UI (`servers.py:436`), so the values are unrecoverable from the app. | Proof 1 (`reliability_proofs.py`): PUT with `oauth_scope=write` only → `oauth AFTER partial fill: clientId='f25686a1-965f-4bbb-8ed9-622dbb2efcdc' (stored value destroyed) clientSecret=None scope='write'`, HTTP 200, toast "Config updated for Demo." No test exercises OAuth fields on edit (`tests/test_admin_dashboard.py:363-383` covers headers only). | engineering (admin routes) |
| RL-002 | **High** | `admin/routes.py:1065-1075` (root cause `sandbox.py:110-119`, pre-existing) | **Code Mode execute is not effectively timeout-bounded and stalls the whole gateway process.** `p_codemode` runs `asyncio.to_thread(code_mode.execute_tool_code, source)` with no route-level timeout; `_validate_code` (`code_mode.py:19-39`) blocks only imports/classes/`open(`/`__`/`os.`/`sys.`/subprocess/socket — loops and heavy computation pass. The nominal `future.result(timeout)` bound does not fire: the starlark worker monopolizes the GIL, so the waiting thread never enforces its deadline, and `ThreadPoolExecutor.__exit__(wait=True)` blocks until the worker finishes. Impact: uvicorn event loop starved → `/health`, `/ready`, `/live`, `/metrics`, `/mcp` and all admin pages unresponsive for the code's runtime — indefinitely for a runaway loop. Loopback+CSRF-gated, hence High not Critical. Root cause is pre-existing (`sandbox.py` untouched by this batch) but the NEW admin route adds a second UI trigger and inherits it — same flaw affects the pre-existing `executeToolCode` meta-tool path. | Proof: `s.execute(<500M-iteration loop>, timeout=1.0)` → `returned normally after 6.8s` (no `SandboxTimeoutError`; nominal bound 1.0s). GIL probe: background ticker expecting ~135 ticks in 6.7s recorded **2** → `GIL starved: True` (process-wide, not request-scoped). | engineering (admin routes trigger; core owner for `sandbox.py` root cause) |
| RL-003 | Med | `admin/routes.py:575` (add), `:768` (toggle), `:663` (refresh write), `:936-939` (remove — `FileNotFoundError` only) | **Registry write IO errors surface as raw 500 with zero UI feedback.** `registry.add`, `registry.patch_enabled`, `registry.update` and non-`FileNotFoundError` from `registry.remove` are unwrapped; contrast `p_set_config` which correctly wraps `set_config` → toast (`routes.py:909-912`). On 500, htmx performs no swap → the click appears to do nothing (silent failure from the user's view). Inconsistent with the module's own "degrade to UI states, never 500s" doctrine (`routes.py:609-611`). | Proofs 2/4/5: forced `OSError` on each → `HTTP: 500 | body head: Internal Server Error` for add, toggle, remove. | engineering (admin routes) |
| RL-004 | Med | `admin/routes.py:285-292` | **`.pyi` read errors other than `FileNotFoundError` → 500 on the detail page**, while the config read immediately above handles any exception → graceful `config-unreadable` redirect (`routes.py:271-284`). Same page, two IO paths, two failure behaviors. | Proof 3: `read_pyi` raising `PermissionError` → `HTTP: 500`; unknown server still `404`. | engineering (admin routes) |
| RL-005 | Med | `admin/pages/servers.py:286` vs `admin/routes.py:435-593, 640, 728` | **Add form "OAuth port" input is silently discarded.** The handler never reads `form.get("oauth_port")` and `MCPServerConfig` has no such field; every web-driven OAuth flow later hardcodes 8989 (`_refresh_one` default `routes.py:640`, `p_auth` literal `routes.py:728`). A user configuring a non-default port gets a silently ignored input and a callback-port mismatch at auth time. | Proof 7: `handler reads 'oauth_port': False`, `model has oauth_port field: False`. CLI parity: `cli.py:127,272,282` does consume `--oauth-port`. | engineering (admin routes) |
| RL-006 | Med | `admin/routes.py:834-849` | **Inconsistent absent-field semantics in `p_set_config` — and the fail-open direction is a policy field.** Absent `timeout` → keeps stored value (`:834-836`); absent `enabled` → `False` (silently disables, `:839`); absent `tools_filter` → `"*"` (`:840`), which **widens** a customized Code Mode allow-list to everything. The real htmx form always posts all three, so the trigger is a partial/malformed PUT — but that is precisely the "malformed htmx request" failure mode, and the suite itself does it: `tests/test_admin_dashboard.py:394` PUTs without `enabled`/`tools_filter` and never asserts the (now disabled) state. | Code lines above; test PUT data `{"timeout": "5000", "url": ...}` at `test_admin_dashboard.py:394` with no post-condition on `enabled`/`tools_to_execute`. | engineering (admin routes) |
| RL-007 | Low | `admin/pages/servers.py:250` (`_ADD_HX` only) vs `:575-584` (edit form) | **htmx/non-htmx divergence on Add:** the add form carries no `method`/`action`, so if htmx fails to load (CDN outage) a native submit POSTs to the GET-only `/admin/servers` → 405. The edit form degrades correctly (`method=post action=...`). | Proof 6: `add form has method=: False | has action=: False`; `edit form has method=: True | has action=: True`. | engineering (admin pages) |
| RL-008 | Low | `admin/routes.py:154` | **Server-rendered notice toasts lose their tone** — `notice_text, _tone = NOTICE_MESSAGES.get(...)` discards `_tone`, and `layout.py:272` renders with default white. Error notices (e.g. `config-unreadable`, meant red per `routes.py:62-65`) arrive visually neutral; message text survives. | Proof 9: `notice=config-unreadable` → toast class `bg-white/10 text-[#ffffff]`, `red tone class present: False`. | engineering (admin routes) |
| RL-009 | Low | `admin/routes.py:322-325`, `:1025-1029`, `:1076` | **Broad `except` maps all failures — and an unknown codemode `mode` — to the misleading empty-state "No servers connected."** A real listing error or a malformed htmx request is reported as a healthy empty state instead of an error. | Code lines; `p_codemode` fallthrough at `:1076` returns the listing fragment with no toast. | engineering (admin routes) |
| RL-010 | Low | `admin/routes.py:1158`, `admin/components.py:343-345` | **Toast auto-dismiss endpoint is orphaned:** nothing in the admin pages issues `hx-get /admin/partials/empty` (grep: only the route registration and a docstring mention it). Toasts persist indefinitely until the next OOB toast replaces them — a stale red error outlives the condition it described. | Proof 8: `files referencing /admin/partials/empty outside routes.py: ['components.py']` (docstring only). | engineering (admin pages) |
| RL-011 | Low | `admin/pages/servers.py:125-165` | **No `hx-disabled-elt` on row action buttons; toggle is a non-idempotent read-modify-write.** Double-click on Enable/Disable can compute `not enabled` twice from the same read → one lost flip (end state ≠ two toggles). Double-click Refresh runs two concurrent discovery storms (writes are atomic last-write-wins, end state consistent — wasted work only). Add/edit forms do carry `hx-disabled-elt` (`servers.py:41,583`). | Code lines; `routes.py:759-772` reads config then toggles from that snapshot. | engineering (admin pages) |
| RL-012 | Low | `admin/routes.py:464-468`, `models.py:716` | **No upper bound on the `timeout` input.** Boundary check is int-parse only; `MCPServerConfig.timeout: int = 5000` has no `ge/le`. A huge value propagates to `asyncio.timeout` in `discover_tools` → an htmx refresh/add request blocks for the configured duration (≤0 is safely clamped to 5s at `client.py:295-296`). | Code lines above. | engineering (models/admin) |
| RL-013 | Low | `admin/routes.py:745` | **Background auth task has no strong reference.** `asyncio.create_task(_run())` without storing the task is the documented asyncio GC hazard — a task can be collected mid-flight; failures are log-only (acceptable per the toast copy, which tells the user to refresh). | Code line; failure logging at `:739-743`. | engineering (admin routes) |

**What holds up (recorded so the owner trusts the rest):** `_load_config` honest-degrade
(`routes.py:609-620`), `_reject` dual htmx/non-htmx path with retarget-keeps-modal-open
(`routes.py:795-806`, tests `:402,421`), success path closing the edit modal by
re-rendering `#detail-config` (`servers.py:412-415`), CSRF fail-closed on empty token
(`routes.py:86-91`), loopback gate (`routes.py:96-101`), policy marker `OSError` handling
(`routes.py:977-1008`), token-cleanup `OSError` caught (`routes.py:946-949`), stable
enabled-first sort (`data.py:63`), read-only tools surface (route table `routes.py:1132`
— GET only; test `:272`), bounded detect/discover/OAuth waits (`routes.py:554`,
`client.py:299`, `models.py:28`), path-traversal guarded by `_safe_path` on every
registry read (`registry.py:48-60`).

---

## Verdict Rationale

**closed.** Two High findings block the gate:

1. RL-001 is silent credential data loss inside the exact feature this batch ships
   (config edit modal), contradicting the UI's own per-field contract, with zero test
   coverage on that path. Unrecoverable-from-app values make it worse than an ordinary
   bug.
2. RL-002 makes a NEW route able to freeze the entire gateway (probes and transports
   included) with no effective timeout — empirically demonstrated, not inferred. The
   root cause is pre-existing, but the batch adds a second trigger surface for it.

Four Mediums (RL-003..RL-006) are error-surfacing/consistency defects on the same
handler family — same session, same owner, fix together. The seven Lows are hygiene.
No waiver path was requested or granted; per guardrails a High finding without owner
acknowledgment cannot pass. Re-run this review after RL-001..RL-006 are addressed.

## Top risks (file:line)

1. `src/mcp_gway/admin/routes.py:888-896` — OAuth partial-fill destroys stored
   clientId/clientSecret behind a success toast (RL-001, High).
2. `src/mcp_gway/admin/routes.py:1065-1075` + `src/mcp_gway/sandbox.py:110-119` —
   Code Mode execute: nominal timeout never fires; GIL starvation freezes the whole
   process (RL-002, High).
3. `src/mcp_gway/admin/routes.py:575, 663, 768, 936-939` — registry write IO errors →
   raw 500, no user feedback (RL-003, Med).
4. `src/mcp_gway/admin/routes.py:285-292` — `.pyi` read error → 500 while config read
   degrades gracefully (RL-004, Med).
5. `src/mcp_gway/admin/pages/servers.py:286` — add-form `oauth_port` input silently
   dropped (RL-005, Med).
6. `src/mcp_gway/admin/routes.py:834-849` — absent `tools_filter` widens allow-list to
   `*`, absent `enabled` disables: three semantics in one handler (RL-006, Med).
