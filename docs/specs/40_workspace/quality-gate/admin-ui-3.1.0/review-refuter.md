# Refuter Review: Admin UI 3.1.0 (14-item batch)

**Reviewer:** review-refuter (engineering domain, adversarial)
**Date:** 2026-09-23
**Verdict:** conditional

## Mission

Attempt to **falsify** the implementation against the 14-item requirement batch. Success = finding a counterexample. All probes read-only against the live server (127.0.0.1:8090, temp registry `/tmp/opencode/gw-admin-check/servers`); no source edits. Registry sha256 captured before/after every interaction probe — byte-identical after each (proof: no probe mutated state).

## Attack Vectors Tried

| ID | Hypothesis | Attempt | Result |
|----|-----------|---------|--------|
| RF-001 | Type sections show-hide both directions via `:has(option:checked)` | Live: open add modal, `select` local→remote→local, read computed `display` of `[data-type-section=*]` | Confirmed: `local flex/remote none` → `remote flex/local none` → reverse |
| RF-002 | Modal close X actually closes (add + edit) | Live click `form label[for=<modal-id>]`; read checkbox state + backdrop display | Confirmed: add `true→false`, backdrop `grid→none`; edit `true→false` |
| RF-003 | Edit error keeps modal open, toast retarget, input preserved | Live: fill timeout=`not-a-number`, Save; measure modal/typed/toast/#detail-config + registry hash | Confirmed: modal open, typed preserved, toast "Timeout must be an integer (ms).", `#detail-config` unchanged, hash identical |
| RF-004 | Edit success closes modal | Live: Save with unchanged values; measure checkbox/backdrop/toast + registry hash | Confirmed: closed (`checked=false`, backdrop `none`), toast "Config updated for Notes.", registry **byte-identical** |
| RF-005 | Tools strictly read-only, `PUT /admin/servers/<name>/tools → 405` | `curl -X PUT` on both the packet's literal path and the partials path | **Falsified (literal path): 404, not 405** → CE-002; partials path 405 (read-only intent holds on both) |
| RF-006 | Tools list auto-updates every 5s, correct URL | Live 12s network capture on detail page | Confirmed: 2× `GET /admin/partials/servers/Notes/tools` 200 (~5s cadence). Mechanism is `hx-trigger="every 5s"`, not the `hx-poll` attribute — htmx-equivalent |
| RF-007 | `Save tools` / any web tools mutation exists | `grep -io "save tools"` on served detail+servers HTML; route table audit | Confirmed absent (0 hits); no tools mutation route exists (test asserts registry tools unchanged) |
| RF-008 | Active servers first, stable sort | Live `/admin/servers` row order vs registry `enabled` flags + `data.py:63` | Confirmed: Notes, Weather (enabled) before Calendar (disabled); `sort(key=lambda r: not r.enabled)` is stable |
| RF-009 | REFRESH ALL / ADD SERVER **equal-width** row (mobile) | Live `getBoundingClientRect` at 375/390/414/600/768/900 | **Falsified at every width**: 174/142, 181/149, 193/161, 286/254 (Δ=32 mobile); 169/162 (md) → CE-001 |
| RF-010 | Search full-width own line (mobile) | Same sweep, search label rect vs `main` content width and button-row top | Confirmed <768: own line + full width at 375/390/414/600; tablet ≥768 is 320px fixed → CE-005 |
| RF-011 | Toolbar: no horizontal overflow; ADD pill in container @1440; wraps @900 | `scrollWidth-clientWidth` + pill/main rects at 1440/900/768/600/414/390/375 | Confirmed: overflow 0 at every width; pill 1416≤1440 @1440; actions wrapped below title @900 (top 101 > title bottom 85) |
| RF-012 | All header bottoms flush | Title-block rects across all 5 pages @1440×900 | **Contested**: within-row flush on Servers (91=91) ✓, but cross-page bottoms 91 (Servers) vs 85 (other four), top 30 vs 24 → CE-003 |
| RF-013 | Nav drawer open/close (mobile/tablet) | Live @375: click burger, click drawer X; inspect computed display | Confirmed <768 (open: `checked/block`, close: `false/none`); at ≥768 drawer is `md:hidden` — rail instead → CE-005 |
| RF-014 | Probes values/badges flush right + REFRESH right-aligned | Live rects: probe value right edge vs card padding edge (5 rows); refresh vs wrap/card right | Confirmed: delta 0 on all 5 rows; refresh right-aligned in wrap and card |
| RF-015 | kv row vertical spacing | Computed padding/height on 5 kv rows | Confirmed: uniform 46px rows, 12px/12px padding, 1px divider (last none) |
| RF-016 | .pyi signatures block scrolls internally | Served HTML `<pre>` classes on detail page | Confirmed: `max-h-[300px] overflow-y-auto` present (`code_block` appends `cls`, components.py:298-307) |
| RF-017 | Hub logo replaces old logo | Live brand-block DOM + repo grep for legacy logo refs | Confirmed: hub SVG (w15) in green circle, 0 `<img>` in brand, no legacy logo references under `src/mcp_gway/admin/` |
| RF-018 | Edit form sections type-conditional by Type select (both directions) | Live: field inventory in edit form of a remote server | **Contested**: server-side conditional holds (url/headers present, command/cwd absent) but `hasTypeSelect=false` — edit has no Type select to toggle → CE-004 |
| RF-019 | Claims: 605 tests, ruff green | `uv run pytest -q`; `uv run ruff check` + `ruff format --check` | Confirmed: 605 passed; ruff 0 findings; 89 files formatted |

## Counterexamples Found

| ID | Counterexample | Impact | Reproduction |
|----|---------------|--------|--------------|
| CE-001 | REFRESH ALL / ADD SERVER are never an equal-width row. Measured pill widths: 375→174/142, 390→181/149, 414→193/161, 600→286/254 (constant Δ=32px); md 768/900→169/162. Root cause: both children carry `flex: 1 1 0%`, but the sibling boxes are asymmetric — the padded `<button>` (px-4 = 32px) floors its border-box flex base at its padding while the unpadded wrapper `<div>`'s base is 0; equal grow leaves the button exactly +32px wider at every mobile width. | **Medium** — explicit acceptance criterion ("equal-width row") fails at all measured mobile widths; visual only, no functional/security loss. | `agent-browser set viewport 375 812; open /admin/servers;` measure `refresh.getBoundingClientRect().width` vs `label[for=add-server-modal].getBoundingClientRect().width` → 174 vs 142. Location: `src/mcp_gway/admin/pages/servers.py:211-228` (+ `components.py:69-87`, `modal()` 348-403). Owner: engineering. |
| CE-002 | `PUT /admin/servers/<name>/tools` returns **404**, not the required 405 (no route matches that path). 405 only holds on `PUT /admin/partials/servers/<name>/tools`. Read-only intent is satisfied on both paths (neither can mutate; test `test_admin_dashboard.py:272-287` proves tools unchanged). | **Low** — literal status-code acceptance mismatch; no mutation surface exists anywhere, security intent fully intact. | `curl -X PUT http://127.0.0.1:8090/admin/servers/Notes/tools` → 404; same verb on `/admin/partials/...` → 405. Location: `src/mcp_gway/admin/routes.py:1114-1159`. Owner: engineering / requirement clarification (confirm intended path). |
| CE-003 | "All header bottoms flush" fails under the cross-page reading: @1440 Servers title sits at top 30 / bottom 91 (the `items-end` header row pushes it down 6px to meet the taller actions block) while Overview, Tools, Observability and Policy all render top 24 / bottom 85. Within-row flush on Servers itself holds (91 = 91). | **Low** — 6px header jump when navigating Overview ↔ Servers; cosmetic; contested requirement reading (within-row vs cross-page). | Measure `section_title` block rects on all five pages at 1440×900 → `{24,85} {30,91} {24,85} {24,85} {24,85}`. Location: `src/mcp_gway/admin/pages/servers.py:190-231`. Owner: engineering / product — confirm which reading the requirement intends. |
| CE-004 | The edit form contains **no Type select**, so "show-hide by Type select, both directions" cannot apply to edit as literally worded. Edit sections are chosen server-side from the stored type (`servers.py:512` `if config.type == "local"`), and Type is intentionally immutable (`servers.py:500` docstring). Live proof on a remote server: url/headers present, command/cwd absent, `hasTypeSelect=false`. The add form fully satisfies the mechanism (RF-001). | **Low** — behaviorally correct (only the relevant section renders; type immutable by design); literal mechanism absent in edit. Contested reading. | Live field inventory on `/admin/servers/Notes` edit modal. Location: `src/mcp_gway/admin/pages/servers.py:493-603`. Owner: product / requirement clarification. Note: local-side edit branch has static proof only — no local server in the live fixture and no detail-page test covers it (coverage gap, Low, engineering). |
| CE-005 | The mobile/tablet bullet diverges at the `md` (768) boundary: (a) at ≥768 there is **no nav drawer** — the whole bar is `md:hidden` (`layout.py:127-135`) and the desktop sidebar rail renders instead; (b) at ≥768 the search input is fixed 320px, not full-width (`servers.py:200` `md:w-[320px]`). Drawer open/close and full-width search verified working below 768 (RF-010, RF-013). | **Low** — if "mobile/tablet" includes tablets ≥768, the drawer and full-width search are absent there (by design: rail + inline toolbar); if the bullet scoped the stacked layout to <768, compliant. Contested reading. | `set viewport 768` → burger/drawer absent, sidebar visible, search 320px; `set viewport 600` → drawer works, search full-width. Location: `src/mcp_gway/admin/layout.py:127-135`, `pages/servers.py:200`. Owner: product / requirement clarification. |

## Requirements That Withstood (strongest probe each)

- **Type-conditional add sections (both directions)** — live computed-style flip both ways (RF-001).
- **Modal close X** — both add and edit, checkbox + backdrop measured (RF-002).
- **Edit error path** — live end-to-end with byte-identical registry hash; matches `HX-Retarget: #toast` test (`test_admin_dashboard.py:402-418`) (RF-003).
- **Edit success closes** — live closed state + toast, registry byte-identical (RF-004).
- **Read-only tools / poll** — no save UI, 405 on the real endpoint, live 5s cadence on the exact polled URL (RF-005..007).
- **Active-first stable sort** — live order matches flags (RF-008).
- **Overflow / wrap / in-container / flush-within-row / probes flush-right / kv spacing / signature scroll / hub logo / test+lint claims** — RF-011, RF-012 (within-row), RF-014..RF-019.

## Verdict Rationale

- pass = attempted falsification, no counterexamples found → **not met**: CE-001 is a hard falsification of an explicit criterion, measured at every mobile width.
- conditional = counterexample with mitigations available → **chosen**: one Medium visual defect (contained, root cause precisely identified), plus four Low items of which three are requirement-reading clarifications rather than behavioral failures. The security-critical invariant of the batch (tools read-only via web) holds under every probe.
- fail = counterexample invalidates spec → not warranted: core behaviors (modals, type-conditional sections, edit flow, sorting, polling, layout metrics) all verified live.

**Residual risk (explicit):** CE-001 ships as-is until engineering remediates; CE-002/003/004/005 need requirement-owner reading confirmation before any of them is called a defect. Evidence claims verified: 605 tests pass, ruff clean, live server behavior as stated. No secrets/PII recorded in this artifact (CSRF token read from page markup was used in-session only and never persisted; registry probed via sha256 hashes, which are content digests).

---

## Re-gate addendum 2026-09-23

**Reviewer:** review-refuter (engineering domain, ADVERSARIAL) — re-run after remediation of the 3 gate Highs (REQ-H1/H2/H3) + CE-001. Checklist per `frame-ship/skills/quality-gate/references/engineering/refuter-review.md`. All probes read-only against live server `http://127.0.0.1:8090` (temp registry `/tmp/opencode/gw-admin-check/servers`); OAuth merge mutations confined to a **scratch TestClient registry in a tempdir** (never the live fixture, never `~/.config/mcp-gway`); no source edits, no commits, server never restarted. Live fixture sha256 of all 6 files **byte-identical** to session-start baseline after every probe (verified at end: `sha256sum /tmp/opencode/gw-admin-check/servers/*` → `a7b5fbfb…/fac19b4d…/de800f5d…/ff41e5df…/29d3def5…/588b329e…` unchanged).

**New verdict: conditional**
**Counts:** gate Highs fixed & verified: **3/3** (REQ-H1, REQ-H2, REQ-H3 clamp/surface) · prior CEs: **0 fixed, 1 retracted (CE-004), 4 persisting** (CE-001 Medium partial-fix, CE-002/003/005 Low-contested) · new findings: **3** (CE-006 Medium, CE-007 Medium, CE-008 Low).

### Re-gate attack vectors

| ID | Hypothesis | Attempt | Result |
|----|-----------|---------|--------|
| RG-01 | REQ-H1 per-field OAuth merge: blank/mask keeps stored, non-blank replaces that field only | 8 POST/PUT probes on scratch registry via TestClient (`p_set_config`, routes.py:864-955): P1 mask-only secret → P2 id+mask → P3 mask id/real scope → P4 real secret → P5 whitespace-only → P6 unknown oauth keys → P7 `••admin` hybrid → P8 keys absent | **Withstood**: P1 file sha unchanged/oauth None; P3 kept stored clientId while replacing scope only; P4 stored secret verbatim; P5/P6/P8 zero wipe/inject (state identical); P9 no-CSRF → 403; P10 evil Host → 403. No wipe, no leak. (But value *substitution* at model layer found → CE-006.) |
| RG-02 | REQ-H2 Host gate fail-closed on forged Hosts | 14 live `curl -H "Host: …"` + 11 raw-socket probes (exact bytes: absolute-form, missing/duplicate Host, padded values) + 21-case `_normalize_host` unit sweep | **Withstood on all attacker-meaningful vectors**: `127.0.0.1.`→403, `%00.evil`→403, `127.0.0.1.evil`→403, `evil127.0.0.1`→403, `0x7f.1`→403, `evil.com`→403, `127.0.0.1.nip.io`→403, `hOsT: Evil.Com`→403, HTTP/1.1 missing Host→400, HTTP/1.0 missing Host→403, dup Host both orders→400, absolute-form→404 (never reaches admin), `[::1]evil`/`127.0.0.1:80:90`/empty→deny. Controls 200: `127.0.0.1[:8090]`, `Localhost`, `LOCALHOST:8090`, `[::1]:8090`, `::1`. 3 cosmetic normalizations pass → CE-008 |
| RG-03 | `_gate` covers every admin route | AST audit of `create_admin_routes()` (routes.py:1204-1249) vs handler bodies | **Confirmed**: 24 Route entries → 23 distinct handlers, **23/23 contain `await _gate(request)`, UNGATED=[]** |
| RG-04 | REQ-H3 timeout clamp matches docstring `[0.1,30]` default 10 | 17-case `_exec_timeout` unit sweep | **Confirmed**: `''/None/nan/inf/-inf/abc→10.0; 0→0.1; 0.05→0.1; -5→0.1; 31→30; 100→30; 1e9→30; 0.5→0.5` (routes.py:1090-1101, consts :52-54) |
| RG-05 | Timeout contract as documented: "can neither pin the route open nor starve it" (routes.py:1093-1094) | Live: 100M-iteration snippet, `timeout=0.1`, measure route latency + concurrent light execute (baseline 17-30ms, 2 runs) | **Falsified → CE-007**: route answered **731ms** (7.3× bound) with correct `303 location: /admin/tools?notice=exec-timeout`; concurrent light execute starved **609ms** (~20-35× baseline) → GIL-held eval blocks the event loop; wait_for only fires at eval end |
| RG-06 | htmx timeout = single response, no double-swap | Live HX-Request execute (200, content-length 184, single `<pre>` body) + repo test asserts `hx-retarget=#toast` and **no** `hx-swap-oob` (test_admin_dashboard.py:747-770) | **Withstood**: no double-response mechanism; timeout toast retargets to #toast, `#cm-output` untouched |
| RG-07 | Notice key allowlist covers timeout notices; unknown keys safe | `NOTICE_MESSAGES` audit (routes.py:56-81) + lookup `.get(key, ("",""))` (routes.py:199) + live GET `?notice=exec-timeout` / `?notice=executed` | **Withstood**: both keys present (lines 67-71) and render exact copy; unknown keys render empty (no 500) |
| RG-08 | REQ-CE-001: REFRESH ALL = ADD SERVER at **all** widths | Live `getBoundingClientRect` at 375/390/414/600/768/900 + class/display forensics | **Falsified → CE-001 persists**: Δ=0 only at 375/390; Δ=8.11 @414, Δ=101.11 @600, Δ=7.34 @768/900 (table below) |
| RG-09 | Modal still opens/positions correctly with new floors | Live click @375×812: checkbox, backdrop, card rect; close click | **Withstood**: `checked=true`, backdrop `fixed inset-0` 375×812, card DIV `top 65 left 16 w 343 h 682` (centered, in-viewport); close → `checked=false` |
| RG-10 | Tests/lint claims: 48 admin / 619 total / ruff clean | `uv run pytest -q` → **619 passed**; `pytest tests/test_admin_dashboard.py -q` → **48 passed** (48 `def test_`); `ruff check` → `[]`; `ruff format --check` → 89 files clean | **Confirmed** |
| RG-11 | CE-002 (404 vs 405) | Re-run: PUT/POST/DELETE `/admin/servers/Notes/tools` → **404 ×3**; PUT `/admin/partials/…/tools` → **405** | **Persists unchanged → keep** |
| RG-12 | CE-003 (cross-page header bottoms 91 vs 85) | 5 pages @1440×900, `section_title` wrapper (`p[class*=text-[24px]` parent, components.py:151-158) | **Persists unchanged → keep**: index/tools/observability/policy `[24,85]`, servers `[30,91]` |
| RG-13 | CE-004 (edit form has no Type select) | Static re-read: servers.py:502-504 docstring "Type is immutable", :514 server-side `if config.type == "local"`, fields :508-573 | **Retracted as defect — by design**; residual coverage gap persists (grep `type="local"`/`command=` in test_admin_dashboard.py → **0 hits**: local-branch edit fields untested) |
| RG-14 | CE-005 (md = rail, not drawer) | Live @768: navs + search | **Persists unchanged → keep**: rail `hidden shrink-0 md:flex md:w-60` computed `flex` w=240; drawer width 0; search **320px** |

### Counterexamples — status after re-gate

| ID | Status | Evidence (updated) |
|----|--------|--------------------|
| CE-001 (prior, Medium) | **PERSISTS — partial fix only** | Visible pill widths: 375→157.5/157.5 (Δ0 ✓), 390→165/165 (Δ0 ✓), **414→168.89/177 (Δ8.11)**, **600→168.89/270 (Δ101.11)**, 768→168.89/161.55 (Δ7.34), 900→same (Δ7.34); `sameTop=true` at all mobile widths. Root cause (live forensics @600): the refresh pill **does** carry `flex-1 justify-center md:flex-none` (rendered class verified), but its wrapper `div.flex-1 md:flex-none` computes **`display:block`** (servers.py:212) → the pill is not a flex item → `flex-1` inert → shrink-to-fit at intrinsic **168.89px** (icon+label+px-4); the ADD label compensates via `w-full` (fills block wrapper). Equality materializes only where wrapper < 168.89px (≤~410px viewport). The add-side wrapper (servers.py:224-230) same block issue, masked by `w-full`. **Why the suite stayed green**: `test_toolbar_flex_children_share_identical_floors` (tests/test_admin_dashboard.py:841-854) asserts class **substrings only** — no rendered-width assertion at any viewport. Severity **Medium** stands (explicit criterion fails at 4 of 6 widths). Owner: engineering. |
| CE-002 (prior, Low) | **PERSISTS (contested)** | RG-11: literal path 404 (PUT/POST/DELETE), partials 405 — unchanged. Owner: engineering/requirement clarification. |
| CE-003 (prior, Low) | **PERSISTS (contested)** | RG-12: numbers identical to first run — servers `[30,91]` vs all others `[24,85]`. Owner: engineering/product. |
| CE-004 (prior, Low) | **RETRACTED as defect** | By design: Type immutable (servers.py:502-504), server-side section selection (:514); add-form mechanism proven RF-001. Residual: local-branch edit fields have **0 test coverage** (Low, owner: engineering). |
| CE-005 (prior, Low) | **PERSISTS (contested)** | RG-14: fresh @768 evidence — rail visible (w=240), drawer absent, search 320px. Owner: product (reading of "tablet"). |
| **CE-006 (NEW, Medium)** | Silent OAuth client-ID substitution | Submitted `oauth_client_id=real-id-123` → stored `clientId=<uuid4>` (scratch-registry probe P2/P3); isolated repro `OAuthConfig(clientId="real-id-123").model_dump()` → fresh UUID. Mechanism: `validate_client_id` **models.py:692-701** (non-UUID → `str(uuid.uuid4())`) + `validate_oauth` mode="before" **models.py:751-778** (dict/object/True branches all enforce UUID). Consequence: `oauth.py:352-353` manual pre-registered path uses stored cid at **oauth.py:464-466** → a non-UUID AS-issued client id is silently replaced and the flow authenticates with the wrong id; the admin field invites free text with no format hint (**servers.py:554-558**, placeholder "blank keeps current"). **Pre-existing, not a remediation regression** — intentional per commit `6baf711` (2026-08-25 "100% web OAuth with UUID") and enforced by tests (test_models.py:96-99, test_edgecases_models_registry.py:100-101). The REQ-H1 *merge* itself is correct (P1-P8) — substitution happens at model validation after the merge. Severity **Medium** (silent data discard → broken OAuth, conditional on non-UUID ids). Owner: engineering — decide: accept arbitrary ids (drop UUID coercion) or disclose the UUID-only format in UI+CLI. |
| **CE-007 (NEW, Medium)** | Timeout *latency* contract falsified | Docstring claims (routes.py:1093-1094) the clamp means a client "can neither pin the route open nor starve it". Live: 100M snippet @`timeout=0.1` → **731ms** response (vs baseline execute 17-30ms); concurrent light execute **609ms**; correct notice/redirect fired (`303 …notice=exec-timeout`) but only at eval end — GIL-held starlark eval blocks the event loop, so `asyncio.wait_for` cannot fire until the snippet finishes; snippet runtime is not bounded by [0.1,30]. In-repo acknowledgment: real-starlark test budget is `elapsed < 8.0` (**tests/test_admin_dashboard.py:787**) vs `< 1.5` for the mocked path (:770). Distinct from the co-reviewer's 11.9s@0.5s measurement (theirs = absolute latency; this entry = contract conformance + concurrent-starvation + baseline ratio). Trigger requires loopback + CSRF (admin-only) → no external DoS surface; full-server stall (including probes) lasts the snippet runtime. Severity **Medium** (availability + docstring overclaim). Owner: engineering — options: document the GIL caveat honestly, release the GIL in the starlark eval loop, or enforce a sandbox-level execution deadline. |
| **CE-008 (NEW, Low)** | Host-gate cosmetic fail-open on malformed Hosts | `_normalize_host` strips at first `:` (routes.py:124-125) and `.strip()`s (routes.py:113): live **200** for `127.0.0.1:8090@evil`, `127.0.0.1:8090.evil`, `127.0.0.1:` (empty port), whitespace/tab-padded ` 127.0.0.1`. **No exploit path found**: no browser-reachable URL host both (a) parses to these values and (b) resolves to an attacker origin (`@` is the userinfo delimiter so `http://127.0.0.1:8090@evil/` sends `Host: evil`; invalid ports make browsers refuse navigation); the threat model is DNS-rebinding browsers, and a non-browser client already speaking raw HTTP to loopback is local. Severity **Low** (defense-in-depth hygiene: validate port digits + reject non-reg-name chars before allowing). Owner: engineering. |

### Requirements that withstood the re-gate (strongest probe each)

- **REQ-H1 merge semantics** — 8-probe matrix incl. mask-only, mixed, whitespace, unknown keys; byte-level no-wipe/no-inject (RG-01); secrets never rendered: live scratch page contained neither stored secret nor clientId (write-only inputs, servers.py:554-571 — no `value=` attr).
- **REQ-H2 gate** — 25 hostile Host probes; all rebinding-meaningful vectors 400/403/404; 23/23 handlers gated (RG-03); CSRF + Host both fire before body parsing (P9/P10).
- **REQ-H3 clamp + surface** — 17-case clamp sweep exact; notice keys complete + live-rendered; htmx single-response only (RG-04..07).
- **Modal with new floors** — opens, centers (343px card in 375 viewport), closes (RG-09).
- **Fixture integrity** — all 6 live-registry sha256 byte-identical start↔end; pytest 619/619, ruff clean (RG-10).

### Verdict rationale (re-gate)

- **pass** — not met: CE-001 still falsifies the explicit equal-width criterion at 414/600/768/900, and CE-006/CE-007 are new Mediums.
- **conditional — chosen**: the three gate Highs demonstrably withstood adversarial re-probe (merge, gate, clamp/surface), the security invariants (loopback, CSRF, write-only secrets, read-only tools) held under every attack, and every counterexample has a named, bounded mitigation; CE-001's fix location is now precise (wrapper needs `flex` or the pill needs `w-full`) with the test gap identified.
- **fail** — not warranted: no security bypass landed; no spec-level invalidation.

**Residual risk (explicit):** CE-001 ships as *partial* (375/390 fixed, ≥414 broken) until engineering adds rendered-width coverage; CE-006 silently corrupts non-UUID client IDs until the product decision lands; CE-007's stall is bounded only by snippet runtime and co-reviewer's latency measurement stands alongside it; CE-002/003/005 remain requirement-owner readings. No secrets/PII persisted: the43-char CSRF token was used in-session only; the OAuth probe values (`real-id-123`, `REALSECRET…987`) are synthetic markers written only to a throwaway tempdir registry; live registry probed via sha256 digests alone.

---

## Round-2 re-probe addendum 2026-09-23

**Reviewer:** review-refuter (engineering domain, ADVERSARIAL) — final re-probe of the round-2 remediation (a) CE-001 wrapper `servers.py:212` → `flex flex-1 md:flex-none`, pill `flex-1 justify-center md:flex-none px-4 py-2`; (b) CE-007 docstring rewritten `routes.py:1090-1098`. Role re-read: `frame-ship/skills/quality-gate/references/engineering/refuter-review.md`. All probes read-only against the live server `http://127.0.0.1:8090` (`agent-browser` 0.38.1, session `AGENT_BROWSER_SESSION=/tmp/opencode/gw-admin-check/.session`, open-then-set-viewport, IIFE evals); no source edits, no commits, server never killed/restarted (`health=200` end-to-end, uptime footer continuous), `~/.config/mcp-gway` untouched.

**Fixture note (assumption stated):** the temp registry `/tmp/opencode/gw-admin-check/servers` was **empty (0 files, "0 connected") this entire round** — `find … -mindepth 1 | wc -l` → `0` before and after every probe, so no probe could mutate state and none did. The CE-001/CE-007 targets (toolbar header, `_exec_timeout` docstring) are independent of grid contents; the REFRESH click returned the standard empty-state partial (no server list to perturb).

**New verdict: conditional**
**Counts:** CE-001 **Medium → Low** (mobile band fixed & independently verified; residual md + sub-375) · CE-007 **RETRACTED** (every docstring claim now defensible) · CE-006 **Medium persists** (pre-existing) · CE-008/002/003/005 **Low persist** · CE-004 remains retracted · **NEW: CE-009 (Low)**.

### Round-2 attack vectors

| ID | Hypothesis | Attempt | Result |
|----|-----------|---------|--------|
| R2-01 | Δ0 at 375/390/414/600 holds independently of orchestrator's numbers | Live `getBoundingClientRect` sweep (open → set viewport → IIFE) | **Withstood**: 157.5/157.5, 165/165, 177/177, 270/270 — **Δ=0 at all four**, byte-for-byte matching orchestrator's claim; `wrapDisp=flex`, `wrapFlex="1 1 0%"`, `pillFillsWrap=0`, `fits=true`, `ox=false` at every width |
| R2-02 | Wrapper-flex change broke pill visuals at the fix widths | Computed styles + span-line forensics + screenshots at 375/390/414/600 | **Mostly withstood, one new defect**: no clipping (`pillClip/addClip=false`) everywhere, labels centered, heights equal at 375/414/600 — **but @390 heights diverge** (refresh 44px vs add 32px; refresh span h=28 = 2 lines vs add h=14) → **CE-009 (NEW, Low)** |
| R2-03 | Modal open/close/position intact after wrapper change | Live @390 and @1440: trigger click, rects, card-X close | **Withstood**: @390 `checked=true`, backdrop `grid` 390×844, card `[16, 67.52, 358×708.95]` (leftGap=rightGap=16, top=8vh) → card X → `checked=false`, backdrop `none`; @1440 backdrop 1440×900, card `[400, 72, 640×756]` (gaps 400/400 = perfectly centered, top=8vh) → close → `checked=false` |
| R2-04 | `flex flex-1 md:flex-none` at the md reset shrinks the desktop row | Computed `flex` at 768/900/1440 + width vs pre-fix intrinsic + overflow/clip | **Withstood**: computed `flex:"0 0 auto"` (flex-shrink 0) on wrapper and pill; refresh width **168.89 = its max-content (unchanged from the pre-fix intrinsic)**, `pillClip=false`, `ox=false`, `fits=true` — **no shrink** |
| R2-05 | Modal overlay no longer centers (nested-flex edge) | See R2-03 rects | **Withstood**: symmetric gaps at both widths (16/16 mobile incl. px-4, 400/400 desktop), top = `8vh` exactly |
| R2-06 | Every CE-007 docstring claim is defensible vs measurements | Claim-by-claim audit of `routes.py:1090-1098` vs `routes.py:1158-1169`, `sandbox.py:99-119`, `code_mode.py:291-301`, my 731ms@0.1s / 609ms starvation, co-reviewer 11.9s@0.5s | **Withstood → CE-007 RETRACTED** (5/5 claims, detail below) |
| R2-07 | Equal-width holds at the extreme mobile floor (320) | Same IIFE sweep at 320×700 | **Falsified**: refresh 132.7 / add 127.3 → **Δ5.4** (min-content floor: refresh label can't shrink below icon+word+padding), but `ox=false` (scrollW=320=vw), no overflow, both pills 44px → folded into CE-001 residual |
| R2-08 | Desktop row flush-right (orchestrator: `addRight==hdrRight` @1440) | Rects @1440 + `flushRight` (add vs actions-row right) at all 7 widths | **Withstood**: `addRight=1416 == hdrRight=1416` (deltaHdr 0) @1440; `flushRight=0` at every width |
| R2-09 | Refresh still functions post-change (wrapper is now a flex container around the hx button) | Live click `button[hx-post=/admin/partials/refresh]` @600 | **Withstood**: `#server-grid` present, standard empty-state partial returned, no error |
| R2-10 | Tests/lint claims (621 / ruff clean) | Independent `uv run pytest -q`; `ruff check`; `ruff format --check` | **Confirmed**: **621 passed**, `[]`, 89 files formatted |
| R2-11 | Mutation logs are consistent with the fix | Read `/tmp/opencode/r2_{ce,f01,f07}_{before,after}.txt` | **Consistent**: `r2_ce` = new markup assertion (`test_admin_dashboard.py:927-931`) fails against pre-fix render, passes after; `r2_f01`/`r2_f07` = unrelated guards (policy audit log, `_ALLOWED_HOSTS` mutation) fail-before/pass-after |

### CE-001 — status: **PERSISTS, DOWNGRADED Medium → Low**

Independent numbers (mine, computed before reading the orchestrator's — identical):

| viewport | REFRESH | ADD | Δ | label lines (R/A) | pill h (R/A) | ox | fits |
|---|---|---|---|---|---|---|---|
| 375 | 157.5 | 157.5 | **0** | 2/2 | 44/44 | false | true |
| 390 | 165 | 165 | **0** | **2/1** | **44/32** | false | true |
| 414 | 177 | 177 | **0** | 1/1 | 32/32 | false | true |
| 600 | 270 | 270 | **0** | 1/1 | 32/32 | false | true |
| 768 | 168.89 | 161.55 | 7.34 | 1/1 | 32/32 | false | true |
| 900 | 168.89 | 161.55 | 7.34 | 1/1 | 32/32 | false | true |
| 1440 | 168.89 | 161.55 | 7.34 | 1/1 | 32/32 | false | true |
| 320 | 132.7 | 127.3 | **5.4** | 2/2 | 44/44 | false | true |

**Root-cause fix verified live**: served HTML contains `<div class="flex flex-1 md:flex-none">` before the refresh button (curl grep); computed wrapper `display:flex` at mobile → pill is a real flex item → `flex-1` engages → equal grow materializes at every 375–600 width. The round-1 root cause (block wrapper, `flex-1` inert) is gone.

**Scope position (stated, not hedged):** the original request is *"mobile/tablet toolbar equal-width."* **My call: md+ natural pill width (Δ7.34 @768/900) does NOT violate it** — three grounds: (1) ≥768 is a different composition (sidebar rail + inline content-sized `md:w-auto` row where the two labels' max-content legitimately differ by 7.34px ≈ 4%, flush-right `deltaHdr=0`, no overflow/clip); (2) the **approved round-2 remediation itself codified `md:flex-none`** — the plan accepted natural widths at md; (3) equal-width is not even mechanically well-defined at md without first giving the row a fixed width (today it is content-sized), i.e., it would be a new design decision, not a defect fix. *Break condition named:* if the requirement owner defines "tablet" as ≥768, CE-001 stays alive at 768/900 — that reading flips only on the owner's word, not on new evidence. **Why it still doesn't fully retract:** at 320 (unambiguously mobile) Δ5.4 stands — a literal in-scope failure, cosmetic, min-content floor, no overflow. Residual = Low: one narrow sub-375 width + contested md reading. Owner: engineering (optional: shorten/tracking-adjust the refresh label or set a shared `min-w` to hold Δ0 to 320). Evidence: this table + `/tmp/opencode/r2_{390_heightmismatch,600_equalrow,1440_desktoprow}.png`.

### CE-007 — status: **RETRACTED**

Claim-by-claim against `routes.py:1090-1098`:

1. *"Clamped … Missing/blank/garbage/NaN → 10s default; bounded to [0.1, 30]s"* — code `routes.py:1099-1105` + prior 17-case sweep (RG-04): **defensible**.
2. *"the response fires at eval completion"* — my 731ms response for `timeout=0.1` (303 `notice=exec-timeout` at eval end) and co-reviewer's 11.9s@0.5s are both exactly this behavior: **defensible** (it is the honest inverse of the old overclaim — the clamp bounds the *deadline*, not the eval).
3. *"CPU-bound Starlark eval (which holds the GIL) can still delay the response and briefly stall the event loop"* — my 609ms concurrent-light starvation vs 17–30ms baseline, co-reviewer 11.9s, pyo3 eval holding the GIL: **defensible**.
4. *"until the sandbox gains an interrupt/step-limit"* — static: `sandbox.py:99-119` has only `future.result(timeout=…)`, no interrupt/step-limit; inner deadline 30s default (`code_mode.py:291-301`): **defensible** (states the absence as future work).
5. *"on deadline the worker thread is abandoned (threads cannot be cancelled)"* — static: `routes.py:1160-1163` `asyncio.wait_for(asyncio.to_thread(…))` — cancelling the wrapping future does not stop the running thread: **defensible**.

The falsified sentence ("can neither pin the route open nor starve it") is gone; no claim now contradicts my measurements or the co-reviewer's. **Residual (Low, restated — behavior unchanged, now disclosed):** for a *non-terminating* snippet there is still no absolute route bound — "briefly" is snippet-bounded, not clamp-bounded (an infinite loop would pin the route until the loop ends). Not re-probed live by design: an infinite-loop POST would pin the shared live server, which this role is forbidden to risk; static evidence (no step limit) + both measured latencies (0.73s, 11.9s) bound every terminating case. Owner: engineering — sandbox interrupt/step-limit, exactly as the docstring now promises.

### CE-006 / CE-008 / CE-002 / CE-003 / CE-005 — status (restated, unchanged, no rework done)

| ID | Status | One-line evidence |
|---|---|---|
| CE-006 | **PERSISTS, Medium (pre-existing)** | `validate_client_id` `models.py:692-701` coerces non-UUID → fresh uuid4; intentional per `6baf711`; needs the product decision (accept arbitrary ids vs disclose UUID-only in UI+CLI). Not touched by round-2. |
| CE-008 | **PERSISTS, Low** | `_normalize_host` strips at first `:` + `.strip()` (`routes.py:113-125`); cosmetic fail-open, no browser-reachable exploit path. Not touched by round-2. |
| CE-002 | **PERSISTS, Low (contested)** | RG-11: PUT/POST/DELETE `/admin/servers/Notes/tools` → 404, partials path → 405; read-only intent intact on both. Awaiting requirement-owner reading. |
| CE-003 | **PERSISTS, Low (contested)** | RG-12: Servers header `[30,91]` vs other four pages `[24,85]`; within-row flush holds. Awaiting product reading. |
| CE-005 | **PERSISTS, Low (contested)** | RG-14: at ≥768 rail renders (`md:w-60`), drawer absent, search `md:w-[320px]`; below 768 both verified working. Awaiting product reading of "tablet". |
| CE-004 | **RETRACTED (prior round)** | Type immutable by design; add-form mechanism proven RF-001. Residual: local-branch edit fields still 0 test coverage (Low). |

### NEW findings from the round-2 diff

| ID | Finding | Impact | Reproduction |
|----|---------|--------|--------------|
| **CE-009 (NEW)** | Equal-width squeezes the REFRESH pill below its max-content (168.89px) at viewports ≲403, so the `REFRESH ALL` label wraps to 2 lines (span h=28 vs 14). In the **~389–403 band only the refresh wraps → ragged pill heights 44 vs 32** (tops aligned, bottoms uneven; measured @390); below ~389 both pills wrap (both 44 — equal but two-line labels @375 and @320). **Not caused by the wrapper-display change** — at 390 the button was already 165px wide in the round-1 partial state (same Δ0 → same wrap); it is a side-effect of the equal-width *criterion* colliding with the label's intrinsic width. Screenshot: `/tmp/opencode/r2_390_heightmismatch.png`. | **Low** — cosmetic, narrow width band (≈389–403px), no clipping/overflow, widths stay Δ0. | Sweep @390: `refresh.getBoundingClientRect()` h=44, add h=32, refresh `span` rect height 28, add 14. Location: `servers.py:212-230` + label max-content. Owner: engineering (e.g., `whitespace-nowrap` + smaller tracking at base, or shorter label). |
| Test-coverage gap (restate) | The updated guard `test_toolbar_flex_children_share_identical_floors` (`tests/test_admin_dashboard.py:923-937`) now pins the new **markup** (fails-before/pass-after proven in `r2_ce_*.txt`) but still asserts **class substrings only — no rendered-width or height assertion at any viewport**. CE-009 and the 320 floor are therefore unguarded; a future class regression that keeps substrings but breaks computed layout would pass. | **Low (residual of CE-001)** | Read of lines 923-937: 15 substring asserts, 0 layout metrics. Owner: engineering. |
| Process hygiene (observation, pre-existing) | `git status` shows the entire admin implementation **untracked** (`?? src/mcp_gway/admin/`, `?? tests/test_admin_dashboard.py`) while gate docs are committed (`91dd912 "record CLOSED verdict …"`). The round-2 fix exists only in the working tree. | **Low (hygiene)** — review history could record a CLOSED gate for code not yet in version control. | `git status --porcelain` + `git show HEAD:src/mcp_gway/admin/pages/servers.py` → *exists on disk, but not in HEAD*. Owner: orchestrator/engineering — commit before shipping. |

### Requirements that withstood the final re-probe (strongest probe each)

- **CE-001 remediation (mobile core)** — independent Δ0 at 375/390/414/600 with computed-style proof of the root-cause fix (R2-01), matching orchestrator's numbers exactly.
- **Modal system under the wrapper change** — open/center/close at mobile *and* desktop, symmetric gaps, top=8vh (R2-03/R2-05).
- **No md regression from the flex reset** — `flex:"0 0 auto"`, natural width preserved, zero overflow/clip at 768/900/1440 (R2-04), flush-right deltaHdr=0 (R2-08).
- **CE-007 docstring** — 5/5 claims defensible against live measurements + static code (R2-06).
- **Suite/lint** — independent 621 passed, ruff `[]`, format clean (R2-10); fixture dir byte-empty start↔end (R2-integrity).

### Verdict rationale (round-2 re-probe)

- **pass** — not met: CE-001 still literally fails at 320 (Δ5.4) inside pure mobile scope, CE-006 (Medium, silent non-UUID client-id substitution) is untouched, and CE-009 is a fresh visual defect; the test-coverage gap that let round-1 ship unrendered widths persists (markup-pinned, metrics-unasserted).
- **conditional — chosen**: both round-2 remediations did exactly what they claimed and nothing more — I could not falsify the wrapper fix at any target width, could not falsify a single sentence of the new docstring, and found no regression in modals, desktop row, overflow, flush-right, or function. Remaining items are one Low with a named break-condition (CE-001), one pre-existing Medium awaiting a product decision (CE-006), two retracted (CE-004/CE-007), four Lows (CE-008/002/003/005), one new Low (CE-009).
- **fail** — not warranted: no security invariant weakened (loopback, CSRF, write-only secrets, read-only tools all untouched by round-2), no spec-level invalidation, orchestrator's stated measurements reproduced exactly.

**Residual risk (explicit):** CE-001 ships *Low* — Δ0 holds across the measured mobile band but 320 fails (Δ5.4) and md's Δ7.34 stands under the strict "tablet≥768" reading (my default: out of scope per the approved `md:flex-none` plan — flips only on requirement-owner word); CE-006 still silently replaces non-UUID OAuth client IDs (Medium, pre-existing, decision pending); CE-009's ragged-height band ≈389–403px cosmetic; non-terminating snippets remain unbounded at the route (Low, disclosed in the new docstring, sandbox step-limit is the named fix); no rendered-width/height test exists. No secrets/PII persisted: no CSRF token was read or stored this round (DOM clicks only), fixture registry had zero files start↔end, screenshots contain no server data (empty fixture) or credentials. All claims above carry command output or `file:line`.
