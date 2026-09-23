# Security Review — Admin Dashboard UI (v3.1.0 Unreleased)

**Reviewer:** security-reviewer (security domain, security owner's delegate)
**Date:** 2026-09-23
**Scope:** UNCOMMITTED working tree — new `src/mcp_gway/admin/**` (24+ endpoints), modified `registry.py` (set_config), `gateway.py` (CSP + route registration), `cli.py`, `observability/middleware.py`
**Verdict:** **closed** — gate CLOSED pending remediation of 1 High (SEC-001) before v3.1.0 ships. Conditional would undersell a probable-exploit finding on a brand-new attack surface.

## Findings by severity

| Severity | Count |
|----------|-------|
| Critical | 0 |
| High | 1 |
| Medium | 2 |
| Low | 3 |

## Checklist

- [x] Threat model complete (STRIDE) — see §STRIDE below; new trust boundary = 24 admin endpoints + `p_set_config` write path.
- [~] AuthN/AuthZ verified — loopback gate **verified** (403 when `serve_host` non-loopback, even if bound `0.0.0.0`: `routes.py:94-101`, test `test_loopback_gate_blocks_admin_when_exposed` passes); CSRF verified on all 24 handlers. **Gap:** no Host-header validation → DNS-rebinding bypass (SEC-001).
- [x] Input validation at all boundaries — SSRF guard fail-closed on save proven live (link-local + unresolvable-host both rejected, URL unchanged); `type` immutable (form never reads it — only `p_add_server` at `routes.py:453`); allow-list re-check + `check_cwd` + env denylist all re-run via `MCPServerConfig(**data)`.
- [x] Secrets not in code — grep over `src/mcp_gway/admin/` source: no hardcoded credentials/tokens (only a compiled `__pycache__` mirror of the source identifiers matched). Test placeholder secrets quoted below are masked.
- [~] Dependencies scanned — `htpy==26.5.1` floor in `pyproject.toml:12`, exact pin via `uv.lock`; htmx CDN SRI **re-verified against the live artifact** (computed sha384 matches `layout.py:37-39`). **No CVE scanner run in this review** — no silent PASS claimed on dependency CVEs; owner runs SCA in CI (not evidenced here).
- [x] Data handling compliant (PII, retention, Ley 172-13) — no personal data collected (server names/URLs/commands only); `notice` query param maps through a fixed dict (`routes.py:50-71`), never reflected raw; secrets masked in all views (see claims).
- [x] Audit logging in place — `audit_local_action` on `admin_add` (`routes.py:512`), `admin_add_regate` (`:570`), `admin_refresh` (`:651`), `admin_update` (`:904`) → structured log (`core/policy.py:436-448`); config-unreadable warnings log exception type only, never values (`routes.py:279-281, 617-619`).

## Claim verification (prove or refute each)

| # | Claim | Verdict | Evidence |
|---|-------|---------|----------|
| C1 | Admin loopback-only gate → 403 when `serve_host` non-loopback, even if bound `0.0.0.0` | **VERIFIED** | `routes.py:94-101` checks `app.state.serve_host` (`gateway.py:370`); all 24 handlers in `create_admin_routes` call `_gate` first (manual audit of `routes.py:1114-1159` + handlers); test passes (34/34). Fail-closed default `127.0.0.1` when state unset (`routes.py:96`). |
| C2 | CSRF on every mutation (per-process token, `X-CSRF-Token` header or `_csrf` field) | **VERIFIED** | `_MUTATING = {POST,PUT,PATCH,DELETE}` (`routes.py:47,102-108`); `hmac.compare_digest`, empty expected token → 403 fail-closed (`routes.py:86-91`); `secrets.token_urlsafe(32)` per process (`gateway.py:375`); live: `POST /admin/partials/refresh` w/o token → **403**; tests `test_mutation_requires_csrf`, `test_csrf_form_field_fallback`, `test_config_edit_requires_csrf` pass. |
| C3 | Secrets/headers/OAuth masked in detail views (never rendered back raw) | **VERIFIED** | `detail_config_inner` renders header **keys** with bullet values (`pages/servers.py:434-437`), OAuth = badge only (`:438-445`), environment never displayed; edit form is write-only (blank placeholders, no value=) (`pages/servers.py:539-570`); tests `test_detail_page_masks_header_secrets` + `test_config_edit_roundtrip_preserves_secrets` pass (fixture value masked: `TOP****123` absent from HTML); registry JSON is never served by any route. Live probe on the temp registry was inconclusive only because its 3 configs contain **zero** headers/OAuth/env (inventory: 0/0/0 each). |
| C4a | Full re-validation on config save — SSRF guard fail-closed with live DNS | **VERIFIED** (nuance) | `p_set_config` rebuilds via `MCPServerConfig(**data)` (`routes.py:897-898`) → `@field_validator("url")` → `validate_url_ssrf` (`models.py:744-749`, structure + literal blocklist + DNS `models.py:348-354`). Runtime: save to `http://169.254.169.254/...` → rejected, stored URL unchanged, `HX-Retarget: #toast`; save to `https://host.invalid/mcp` → rejected (DNS fail-closed), URL unchanged. Nuance: validation uses 60 s DNS cache (`use_cache=True`); connect path re-resolves uncached + pins (`models.py:433-437`) — no gap. |
| C4b | Type immutable | **VERIFIED** | `p_set_config` never reads `form["type"]` (grep: only `routes.py:453` in `p_add_server`); runtime: submitted `type=local` on a remote server → stored type stays `remote`. |
| C4c | Blank secret fields keep stored values | **PARTIALLY REFUTED → SEC-002** | All-blank → stored OAuth **kept** (runtime proof). Headers blank → kept (test passes). **But** partially filling the OAuth group replaces the whole group: scope-only edit wiped stored `clientSecret` (→ None) and the stored `clientId` (validator auto-minted a fresh UUID) — runtime proof, while the UI promises "blank fields keep current values" (`pages/servers.py:593-596`). |
| C4d | Local command allow-list re-check + `admin_update` audit on save | **VERIFIED** | `routes.py:901-908` (`check_local_command` + `audit_local_action("admin_update", ...)`); runtime: save with `totallynotallowed --flag` → denied ("not allowed") and stored command unchanged (`npx`); `.pyi` untouched by `set_config` (runtime mtime+content proof; `registry.py:123-129`). |
| C5 | Single relaxed CSP constant in `gateway.py` | **VERIFIED on the wire** (code hygiene gap → SEC-005) | Live `GET /` **and** `GET /health` both return the `CSP` constant (middleware assignment `gateway.py:58` overrides handler-level literals). `grep Content-Security-Policy`: only that one write + 3 stale literals in `observability/health.py:64,108,123` that are shadowed dead code. Supply-chain/no-SRI assessment → SEC-003, residual risk stated below. |
| C6 | Tools strictly read-only over web | **VERIFIED** (exact path in packet corrected) | `create_admin_routes` registers tools as `GET` only (`routes.py:1132`); live: `PUT /admin/partials/servers/Demo/tools` → **405**, tools unchanged (test asserts `.pyi` still `[ping]`); `PUT /admin/servers/Demo/tools` (page path as literally written in the packet) → **404**, not 405 — no such route exists either way; no mutation path either way. |
| C7 | htpy auto-escaping + `markupsafe` Markup regression fix — no XSS via names/URLs/toast | **VERIFIED for all current call sites** (latent trap → SEC-004) | Empirically (`htpy 26.5.1` / `markupsafe 3.0.3`): `<script>` in text child, attribute value and `href` all escape; `_render(Element)` / `_render(list)` return escaped HTML (regression test `test_config_edit_returns_unescaped_html` passes — no double-escape). Every `_frag`/`_render`/`_notice_frag` call site passes an htpy element or element list (audited: `routes.py:183,187,700` + all partials); toast/notice text flows through htpy escaping; `q` search param never reflected. **But** `_render(raw str)` marks user-shaped strings safe unescaped (proof: `_render('<script>...')` returns it verbatim) — no current caller does this (SEC-004). |

**Live server evidence** (`127.0.0.1:8090`, read-only + intentionally-rejected probes only; nothing killed or restarted): `GET /` → 200 with exact `CSP` constant, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`; CSRF-less `POST` → 403; tools `PUT` → 405/404; forged `Host` → 200 (SEC-001).
**Test evidence:** `tests/test_admin_dashboard.py` **34/34 pass**; `tests/test_wave2_api.py + tests/test_registry.py` **24/24 pass** (ruff claimed green by packet; not re-run — no contrary evidence).

## STRIDE (new surface)

- **Spoofing:** loopback gate + CSRF token hold for browser origins; **Host header unvalidated → DNS rebinding lets an attacker page become a same-origin "local" client and read the CSRF token from the DOM** (SEC-001). No user auth exists by design (local-first, accepted).
- **Tampering:** `p_set_config` is the only config write path — re-validates everything (SSRF/live-DNS, type immutable, allow-list, cwd, env denylist) and never touches `.pyi` (proven). CSRF gates all 24 handlers. SEC-002 = credential *loss* on partial OAuth edit (tamper-adjacent data integrity).
- **Repudiation:** `audit_local_action` covers local-command decisions on add/refresh/save; JSON request logging pre-existing. Remote-config edits and `p_remove` are not separately audited (observation, owner: engineering — CLI parity doesn't audit them either; no claim broken).
- **Info disclosure:** masking verified (C3); no raw-JSON route; errors log types only. CSP/CDN script compromise would expose the DOM + enable the URL-swap exfil chain (SEC-003).
- **Denial of service:** mutations CSRF-gated; `path_template` collapses `/admin*` label cardinality (`middleware.py:42-58`, test passes) — no unbounded metric labels from the new routes.
- **Elevation of privilege:** local command execution stays behind allow-list + syntax validation + break-glass (env **and** marker); admin can create the marker but activation still requires `MCP_GWAY_ALLOW_UNRESTRICTED_LOCAL=1` in the server env (UI says so, `pages/policy.py:83-91`). Code Mode execute runs the existing hermetic Starlark sandbox (`routes.py:1065-1075`), same capability already exposed via `/mcp` — not a new trust boundary.

## OWASP Top-10 screen (new endpoints / adapters / payloads)

Injection/XSS: escaped empirically + audit (SEC-004 latent only). Broken authZ: gate verified; Host gap = SEC-001. Sensitive data exposure: masked, no raw config route. Misconfig: SEC-003/SEC-005. Insecure design: tools read-only, type immutable, atomic `set_config`. Cryptographic failures: 256-bit `token_urlsafe`, constant-time compare. SSRF: fail-closed proven at save + pin at connect. Software supply chain: htmx SRI verified against CDN, tailwind unpinned = SEC-003; **CVE scan not run** (checklist note). Logging/audit: present for policy-relevant actions. Injection (command): no shell ever — `shlex.split` + `validate_command_syntax` (basename-only, forbidden `;&$()|\`` and `..`, `policy.py:263-294`) + allow-list. SSRF/parsing: `json`+pydantic only, no deserialization of untrusted data.

## Findings

| ID | Severity | Finding | Location | Evidence | Remediation | Owner |
|----|----------|---------|----------|----------|-------------|-------|
| SEC-001 | **High** | **No Host-header validation on the admin surface → DNS-rebinding bypass of the loopback-only gate.** `_gate` checks only `app.state.serve_host`, never `request.headers["host"]`. An attacker page served from their own host on the same port number, then rebound to `127.0.0.1`, becomes *same-origin* with the gateway: it reads the CSRF token from `hx-headers` (`layout.py:255`) and can drive every mutation. Impact chain (proven components): rebind-read token → `PUT .../config` swapping `url` to an attacker-controlled **public** host while blank header fields keep stored Authorization/OAuth values (`routes.py:875-896`) → `POST .../refresh` makes the gateway connect out with those credentials → secret exfiltration; plus server removal/DoS, break-glass marker creation, sandbox execution. | `src/mcp_gway/admin/routes.py:94-109` (`_gate`); missing check would live here; no host check anywhere in `src/` (grep `headers.get("host")` → 0 hits) | Live: `curl -H 'Host: evil.attacker.example' http://127.0.0.1:8090/` → **200** (expected: 403/421) | Reject requests whose Host authority is not `127.0.0.1[:port]`, `localhost[:port]` or `[::1][:port]` (421/403) — fail closed; add a rebinding regression test | engineering owner (gateway) |
| SEC-002 | Medium | **OAuth partial-fill destroys stored credentials while the UI promises otherwise.** `p_set_config` replaces the whole `oauth` group when *any* of client-id/secret/scope is non-blank: blank siblings are dropped (secret → None) and a blank/invalid `clientId` is silently re-minted by the validator. Claim "blank secret fields keep stored values" is refuted for mixed fills; the form explicitly promises per-field semantics. No exposure — silent credential **loss** + auth breakage with a success toast. | `src/mcp_gway/admin/routes.py:888-896` vs promise at `src/mcp_gway/admin/pages/servers.py:593-596`; validator `src/mcp_gway/models.py:692-701` | Runtime proof: scope-only edit → stored `clientSecret` None, `clientId` ≠ original; all-blank edit → all three preserved | Merge each non-blank OAuth field into the stored config (per-field write-through) instead of group replace; keep all-blank = keep-current | engineering owner |
| SEC-003 | Medium | **Relaxed CSP allows an unpinned, non-SRI third-party script (`cdn.tailwindcss.com`) — supply-chain → admin takeover.** `script-src` whitelists both CDNs for all origins' scripts; htmx is pinned + SRI-verified (good), but the Tailwind Play CDN tag carries no `integrity` (SRI infeasible on that endpoint) and jsdelivr is allowlisted by origin, not by hash. Compromise of either CDN yields arbitrary JS in the admin origin: CSRF-token theft (token is a readable DOM attribute) → all mutations, including the SEC-001 exfil chain. CSP also omits `form-action`/`base-uri`, so an injected script could exfiltrate via form POST despite `connect-src 'self'`. | `src/mcp_gway/gateway.py:39-47` (CSP), `src/mcp_gway/admin/layout.py:36-40, 242-248` (script tags) | Live header shows `script-src 'self' https://cdn.jsdelivr.net https://cdn.tailwindcss.com`; `curl`+`openssl` of the htmx artifact matches the pinned SRI exactly; Tailwind tag has no integrity attribute | Vendor/self-host both assets (then tighten `script-src` to `'self'`), or pinned-version URL + SRI where possible; add `form-action 'self'; base-uri 'self'` | engineering owner |
| SEC-004 | Low | **`_render` coerces raw strings to `Markup` unescaped — latent XSS trap.** `Markup(str(node))` on a plain `str` marks it safe; today every call site passes htpy elements (audited, escaping proven), but the next caller passing a formatted string reintroduces XSS with no type error to catch it. | `src/mcp_gway/admin/routes.py:170-179` | Runtime: `_render('<script>alert(1)</script>')` → returns verbatim; `_render(div['<script>'])` → escaped | Escape non-element input in `_render` (or assert Element/list) so fail-closed is structural | engineering owner |
| SEC-005 | Low | **Stale duplicate CSP literals contradict the "single CSP constant" claim at code level.** Three handlers build `Content-Security-Policy: default-src 'self'` that the middleware silently overwrites — wire is correct (proven), but the dead literals invite divergent behavior if middleware order changes. | `src/mcp_gway/observability/health.py:64,108,123` vs `gateway.py:58` | Live `GET /health` returns the relaxed constant, not the handler's strict one (middleware wins) | Remove the handler-level literals; set CSP only in `_SecurityMiddleware` | engineering owner |
| SEC-006 | Low | **Accepted risk: no authentication on admin beyond loopback — any local process/user on a shared host can mutate the registry.** Inherent to the documented local-first model and equivalent to the pre-existing unauthenticated `/mcp` surface; the admin adds destructive mutations (remove/break-glass marker). | `src/mcp_gway/admin/routes.py:94-101` (design), AGENTS.md local-first stance | Code + docs review (no credential check exists by design; not an implementation bug) | Document the single-operator assumption; if a multi-user/host-shared deployment is ever supported, add a loopback auth token before release — this finding escalates to High in that condition. **Expiry:** re-evaluate at v3.1.0 GA | engineering owner + product |

## Verdict rationale

Seven claimed controls were tested, not trusted: five verified outright (C1, C2, C3, C4a/b/d, C6, C7-current-call-sites), one partially refuted (C4c → SEC-002), one verified on the wire with a hygiene gap (C5 → SEC-005). The controls the team built — loopback gate, per-process CSRF, write-only secrets, full re-validation on save, read-only tools, escaping — all hold under live and runtime proof.

They do **not** yet hold the *boundary itself*: SEC-001 shows the loopback gate authenticating the wrong thing (bind address instead of request authority), and the demonstrated exfil chain runs on top of the already-proven blank-keeps-headers behavior. That is a probable exploit with major impact on a new surface shipping in this release → **closed** until SEC-001 is fixed and re-proven (Host rejection test green). SEC-002/SEC-003 should land in the same cycle per severity rubric (Medium: within sprint); SEC-004..006 to backlog/accepted-risk register above.

**Residual risk after remediation (explicit):** admin remains unauthenticated to anything that can reach loopback (SEC-006 accepted, single-operator assumption); CDN trust remains until assets are vendored (SEC-003 — until then a Tailwind/jsdelivr compromise bypasses all app-layer controls); DNS-rebinding fix does not replace CSRF (both stay); no CVE/SCA scan was executed inside this review — CI dependency scanning is assumed, not verified. No secrets, tokens, or PII appear in this artifact; all quoted credential values are masked test placeholders.

**Evidence on record:** 34/34 `test_admin_dashboard.py`, 24/24 `test_wave2_api.py` + `test_registry.py`, live probes on `127.0.0.1:8090` (read-only + intentionally-rejected requests only), runtime config-save proofs executed in throwaway temp registries (no source files touched).

---

## Re-gate addendum 2026-09-23

**Reviewer:** security-reviewer (independent re-verification)
**Date:** 2026-09-23
**Scope:** Re-prove or refute every prior finding against the remediated tree; hunt new attack surface introduced by the remediation; re-verify the scorecard; assess the execute-timeout abandoned-worker path. Update-in-place — history above preserved, nothing rewritten.
**Verdict:** **conditional** — no Highs remain. SEC-001 (High) and SEC-002 (Medium) are **FIXED with fresh live proof**; the original rebinding exfil chain is **dead (proven)**. SEC-003 (Medium) persists → waiver candidate; SEC-004/005 (Low) persist to backlog; SEC-006 accepted risk stands; the abandoned-worker path cross-references risk gate RK-008 (Medium, engineering owner) — no duplicate finding opened.

### Re-gate counts

| Outcome | Count | IDs |
|---------|-------|-----|
| Fixed (re-proven live) | **2** | SEC-001 (High), SEC-002 (Medium) |
| Persisting | **4** | SEC-003 (Medium, waiver candidate), SEC-004 (Low), SEC-005 (Low), SEC-006 (Low, accepted) |
| New findings from the remediation surface | **0** | — (abandoned-worker overlaps risk RK-008, cross-referenced not duplicated) |

### Open findings (severity table)

| ID | Severity | Status | Location | Owner | Disposition |
|----|----------|--------|----------|-------|-------------|
| SEC-003 | **Medium** | Persisting — **waiver candidate** | `src/mcp_gway/gateway.py:42-50` (CSP), `src/mcp_gway/admin/layout.py:40` (unpinned Tailwind), `layout.py:242` (no integrity) | engineering owner | Vendor/self-host both CDN assets (then `script-src 'self'`) or pinned-version + SRI where feasible; add `form-action 'self'; base-uri 'self'`. Until waived or fixed: a CDN compromise bypasses every app-layer control (`form-action`/`base-uri` still absent from `CSP`). |
| SEC-004 | **Low** | Persisting (latent trap) | `src/mcp_gway/admin/routes.py:215-224` (`_render` raw-`Markup`) | engineering owner | Backlog: narrow to Element/list input (fail closed). All current call sites element-only (re-audited this re-gate). |
| SEC-005 | **Low** | Persisting (hygiene) | `src/mcp_gway/observability/health.py:64,108,123` | engineering owner | Backlog: delete the stale handler-level CSP literals; wire unaffected (middleware wins). |
| SEC-006 | **Low** | Accepted risk | `src/mcp_gway/admin/routes.py:129-154` (gate design) | engineering owner + product | Single-operator local-first assumption; **expiry: v3.1.0 GA** re-evaluation; escalates to High if multi-user/host-shared deployment ships. |
| RK-008 (cross-ref) | **Medium** | Owned by risk gate — not re-opened here | `src/mcp_gway/sandbox.py:110-119` + GIL behavior | engineering owner | See §Abandoned-worker path; tracked in `review-risk.md`. |

### Re-proof of prior findings

**SEC-001 (High) — FIXED.** Remediation: `_gate` now validates the request Host authority (`_ALLOWED_HOSTS` `routes.py:48`, `_normalize_host` `routes.py:104-126`, host check first in `_gate` `routes.py:129-154`) *before* CSRF; regression tests `test_admin_dashboard.py:651` (evil host → 403 on every admin surface), `:685` (legit variants pass), `:701` (fail-closed matrix), `:728` (non-admin unaffected).
Live re-proof on this instance (`127.0.0.1:8090`, nothing killed/restarted):
- Original PoC `curl -H 'Host: evil.attacker.example' http://127.0.0.1:8090/` → **403** (was 200 at first gate — the exact regression is closed).
- Normalization matrix (live + unit `:701`): trailing-dot, IPv4-mapped `::ffff:127.0.0.1`, double-colon, decimal/octal/short-IP, NUL-byte, userinfo, whitespace-in-host → **all 403/denied**; mixed-case / port-suffixed / whitespace-stripped legitimate loopback forms → pass (`:685`).
- Raw-socket **duplicate Host** headers → `400 Bad Request` (server rejects; the earlier "200" was curl collapsing duplicate headers — extraction artifact, not a bypass).
- Absolute-form request line carrying an evil authority → `404`.
- 403 body is static (63 bytes, byte-identical across paths): no host reflection, no token, no information leak.
- Ordering proven: an evil-Host **mutation** request is answered by the Host gate (loopback text) before CSRF — not "CSRF token mismatch".
- Gate coverage: enumeration of all **24 `Route(` entries → 23 unique handlers** (`h_index` shared by `/` + `/admin`) → **23/23 call `_gate` first**.

**SEC-002 (Medium) — FIXED.** Remediation: per-field OAuth write-through (`_oauth_field` `routes.py:854-861`, merge `routes.py:945-955`) replaces the old group-replace.
Live PoC (temp server `SecProof`, synthetic client id `11111111-1111-4111-8111-111111111111`, placeholder secret len 23; server deleted after the proof — registry back to Calendar/Notes/Weather):
- Scope-only PUT → stored client id **byte-identical**, secret len **23 preserved**, scope updated.
- Mask-sentinel PUT (`••••`/`****` bullets) → stored values **kept** (masks never overwrite real credentials).
- Mass-assignment probe (extra `oauth.*` keys, `type=local`, `name=Hacked`, `command=...`) → all ignored; stored name/type/command unchanged.
- Detail page + edit form: `secret_hits=0` (no credential material in HTML).
- Fails-before/passes-after logs on record: `/tmp/opencode/h1_before.txt`, `/tmp/opencode/h1_after.txt`.

**SEC-003 (Medium) — PERSISTS.** Wire `CSP` still `script-src 'self' https://cdn.jsdelivr.net https://cdn.tailwindcss.com` with no `form-action`/`base-uri` (re-read `gateway.py:42-50`); Tailwind tag still unpinned, no `integrity` (`layout.py:40`, used at `:242`); htmx still pinned — SRI re-extracted against the live CDN: `sri_match=YES` (`HTMX_INTEGRITY` `layout.py:36-38`, tag `:243-248`). Top open severity → waiver candidate.

**SEC-004 (Low) — PERSISTS.** `_render` (`routes.py:215-224`) still coerces raw `str` → `Markup` unescaped; every current call site passes htpy elements (re-audited).

**SEC-005 (Low) — PERSISTS.** Three stale CSP literals remain at `health.py:64,108,123`; wire still correct (`_SecurityMiddleware` `gateway.py:58` wins — re-verified on `/` and `/health`).

**SEC-006 (Low) — ACCEPTED, unchanged.** Design stance; expiry v3.1.0 GA as recorded above.

### Original rebinding exfil chain — DEAD (proven)

Chain: rebind → read CSRF token from admin DOM → drive mutations → URL-swap exfil.
- **Hop 1 (rebind → DOM):** every admin surface answers evil Host with **403 before CSRF** (matrix above; tests `:651`). The token lives only in admin HTML (`hx-headers`) → unreachable.
- **Independent negative on hop 2 (token anywhere else):** value-grep of the live 43-char token (extracted from the DOM) across every non-admin response — `/metrics`, `/health`, `/ready`, `tools/list`, `executeToolCode` results, and all 403 bodies → **0 hits**.
- **Independent negative on hop 3 (mutation via `/mcp`):** `/mcp` exposes only the 4 code-mode meta-tools (read/sandbox: `executeToolCode`, `getToolDocs`, `listToolFiles`, `readToolFile`) — grep confirms **no registry-write verbs**; no admin-equivalent mutation exists outside the gate.

Verdict: the chain fails at hop 1 **and** has no fallback at hops 2–3. Dead and proven dead.

### New-surface hunt (remediation-introduced)

| Probe | Result |
|-------|--------|
| `_exec_timeout` hostile inputs (`routes.py:1090-1101`: injection strings, negatives, NaN/inf, huge values) | All clamp/default to safe floats — no injection |
| `notice` query param (closed-set dict `routes.py:50-71`) | Unknown notice not reflected; exec-timeout notice renders fixed text — no reflected XSS |
| CSRF-less POST to the new codemode-timeout path | **403** — CSRF coverage extends to the new handler |
| Host-gate 403 body | Static 63 B, no token/host reflection — no info leak |
| Host normalization edge forms | Fail-closed deny (`:701`), no 500s |
| Secrets re-scan of `src/mcp_gway/admin/` | No hardcoded credential literals |

### Scorecard re-verification

| Control | Re-gate result |
|---------|----------------|
| C1 loopback + Host gate | **VERIFIED** — host now validated first in `_gate`; 24 routes / 23 handlers gated; tests `:651/:685/:701`; non-admin unaffected (`:728-736`) |
| C2 CSRF on mutations | **VERIFIED** — incl. the new timeout path (CSRF-less → 403); `secrets.token_urlsafe(32)` per process (`gateway.py:375`) |
| C3 secret masking | **VERIFIED live** — SecProof detail + edit form `secret_hits=0` |
| C4a SSRF fail-closed | **VERIFIED live** — link-local PUT rejected, stored URL unchanged, toast = pydantic error |
| C4c blank keeps secrets | **VERIFIED** (was refuted → SEC-002 now fixed; scope-only + mask-sentinel proofs) |
| C6 tools read-only | **VERIFIED** — `PUT` → 405/404 |
| C5 single CSP on wire | **VERIFIED** — constant on `/` + `/health`; stale literals persist → SEC-005 |
| C7 escaping | **VERIFIED** for all current call sites; raw-`Markup` trap persists → SEC-004 |
| htmx SRI | `sri_match=YES` (re-extracted against live CDN) |
| Tailwind pin / `form-action` / `base-uri` | **ABSENT** → SEC-003 |
| Audit coverage | `audit_local_action` present at `routes.py:557,615,678,962` |

### Abandoned-worker / execute-timeout path

Question: does returning a timeout toast abandon a still-running sandbox worker?
- Mechanics: `sandbox.py:110-119` — `ThreadPoolExecutor(max_workers=1)` used as a context manager → `shutdown(wait=True)` joins the worker; the worker is never truly orphaned at scope exit.
- Empirics: GIL experiment — `sl.eval` **holds the GIL** for the whole evaluation (event loop starved **6.32 s**). Live: 300M-iteration exec with a 0.1 s timeout returned the "timed out after 0.1 s" toast in **6.16 s**, and the sandbox counter incremented immediately after the response (worker completed; the loop was GIL-starved, not abandoned).
- Impact: **availability/latency only** — a timeout does not bound response latency while a heavy eval runs, and process exit blocks on `wait=True`. No confidentiality/integrity impact; requires loopback + gate already passed (single-operator model).
- Disposition: same root cause as risk gate **RK-008 (Medium, engineering owner, `review-risk.md`)** — cross-referenced, **no duplicate security finding opened**. Residual accepted until RK-008 lands.

### Dependency scan (own rerun)

`uvx pip-audit -r /tmp/opencode/pg-req.txt` → **"No known vulnerabilities found"** (29 packages). Independent scanner run by this reviewer — the first pass's "no CVE scan run" checklist gap is closed for this re-gate.

### Test & lint evidence

- Full suite: **619 passed**.
- `ruff check src/ tests/` → `[]`; `ruff format --check` → **89 files clean**.

### Residual risk after re-gate (explicit)

- SEC-003 is the top open item: until assets are vendored/SRI'd (or waived), a Tailwind/jsdelivr compromise bypasses every app-layer control (`form-action`/`base-uri` still absent from `CSP`).
- Admin remains unauthenticated beyond loopback+Host (SEC-006 accepted, single-operator; expires v3.1.0 GA).
- RK-008 GIL/timeout latency is risk-owned (Medium, engineering owner) — availability only.
- `/mcp`, `/metrics`, `/health`, `/ready`, `/live` stay intentionally outside the admin Host gate (design-asserted `test_admin_dashboard.py:728-736`); re-verified as no residual for the chain (token 0 hits; `/mcp` read-only meta-tools).
- No secrets, tokens, or PII in this artifact — the token is referenced by length only (43), the OAuth client id is a synthetic all-`1`s test UUID, the secret by length/placeholder only; the test server was deleted from the temp registry.

**Evidence on record:** 619-test suite green, `ruff check` `[]`, format 89 files clean, `pip-audit` clean (own rerun), live probes on `127.0.0.1:8090` (rejections + read-only; nothing killed or restarted), temp-registry PoCs cleaned up (`SecProof` removed), orchestrator fails-before/passes-after logs `/tmp/opencode/h1_{before,after}.txt`.
