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
