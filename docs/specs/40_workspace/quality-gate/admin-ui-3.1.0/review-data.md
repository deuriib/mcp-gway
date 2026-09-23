# Data Review: admin-ui-3.1.0 (mcp-gateway v3.1.0)

**Reviewer:** review-data (data lens, engineering owner's delegate)
**Date:** 2026-09-23
**Verdict:** conditional
**Scope:** NEW WRITE PATH `Registry.set_config` + admin config edit form (`p_set_config`) over `~/.config/mcp-gway/servers/*.json` (credential-adjacent store: headers values, OAuth clientSecret, env values). Read-only audit of the working tree; no source or store files modified.

## Checklist

- [ ] **Schema changes versioned** — FAIL. No `schema_version` in the payload; `set_config` rewrites the whole JSON from a fixed whitelist (`registry.py:83-111`), so any key outside the whitelist (incl. the model's own `retry_on_transport_error`) is destroyed on first dashboard save — proof A3 below. → DAT-003
- [~] **Data lineage documented** — PARTIAL. Lineage is code-traceable: form (`pages/servers.py:493-603`) → validation (`routes.py:834-908`, SSRF re-gate via model validator `models.py:744-749`, allow-list re-gate + audit `routes.py:901-908`) → atomic write (`registry.py:123-129` → `secureio.py:14-84`) → re-render **from the in-memory model, not a fresh store read** (`routes.py:920-926`). → DAT-005
- [~] **Quality checks (nulls, types, ranges)** — PARTIAL. Null/required handling correct (command/URL required, blank-secret-preserves for headers/env verified); timeout has no range bound. → DAT-006
- [x] **PII handling compliant** — PASS. No PII collected. Credential checkpoint clean: admin logs carry only server name + exception type (`routes.py:279-280, 617-618, 657-658, 731-742, 788-789, 947-948`); `audit_local_action` logs action/name/binary-basename/reason only (`core/policy.py:436-448`); toasts are static messages; env validation errors echo key names only (`policy.py:427-432`). Read-time masking verified (proofs C1-C3). privacy-engineer consult still owed inside DAT-004.
- [ ] **Migration path defined** — FAIL (same root as schema versioning): destructive canonicalization on save with no version gate or warning. → DAT-003
- [-] **Backfill strategy** — N/A (no new required fields; no backfill needed).
- [x] **Analytics impact assessed** — PASS. No analytics/telemetry path added; only the Prometheus label `registry_operations_total{op="set_config"}` (`registry.py:129`).

## Findings

| ID | Severity | Finding | Location | Owner | Mitigation |
|----|----------|---------|----------|-------|------------|
| DAT-001 | **High** | Partial OAuth edit silently destroys stored credentials. When any one of `oauth_client_id` / `oauth_client_secret` / `oauth_scope` is non-blank, the handler replaces the **whole** `oauth` object with only the typed fields; blank siblings become `None`, and the model validator then rotates `clientId` to a fresh UUID. The form promises per-field "blank keeps current" — proof B: PUT with only `oauth_scope` → HTTP 200, stored `clientSecret` gone, `clientId` changed, scope updated. Silent credential loss on an invited action. | `src/mcp_gway/admin/routes.py:888-896`; promise at `src/mcp_gway/admin/pages/servers.py:550-568, 593-596`; rotation at `src/mcp_gway/models.py:751-778` | engineering owner (admin UI) | Per-field merge with stored oauth (blank → keep stored), same semantics as headers; add a round-trip test covering partial oauth edits (current suite only covers headers: `tests/test_admin_dashboard.py:363-383`) |
| DAT-002 | Medium | `retry_on_transport_error` never reaches the store: the new add-form checkbox is read (`routes.py:470`) and built into the config (`routes.py:507, 547`) but `_config_data` omits the key, so `registry.add` discards it — proof A1. Operator opts in, save returns 200, flag is off after reload and the detail view never shows it. Root cause pre-exists in `add` (identical payload at HEAD) and violates feat-007 BR-112 intent; the new UI makes it user-facing. | `src/mcp_gway/registry.py:83-111` (missing key) via `routes.py:575`; field declared at `src/mcp_gway/models.py:720`; form control `src/mcp_gway/admin/pages/servers.py:313` | engineering owner (registry) | Add the key to `_config_data` (shared by `add` + `set_config`); persistence round-trip test |
| DAT-003 | Medium | Destructive rewrite without schema versioning: `set_config` persists only the whitelist, so an on-disk JSON carrying `retry_on_transport_error: true` (manual edit / foreign writer) is reset to default on the next dashboard save — proof A3 (PUT 200 → key gone, other fields updated). Single-source-of-truth store rewrites itself canonically with no version field, no detection, no warning. Escalates to High the moment any writer legitimately persists that key (see DAT-002). | `src/mcp_gway/registry.py:123-129` + `83-111`; consume side `src/mcp_gway/admin/routes.py:846, 910` | engineering owner (registry) | Include full model schema in payload (fixes DAT-002/003 together) and/or add `schema_version` + preserve-unknown-keys until versioned migration exists |
| DAT-004 | Medium | Governance gap: credential fields in `servers/*.json` (header values, OAuth `clientSecret`, env values) have no declared purpose + TTL + deletion procedure + owner, despite REQ-NF-005 (`docs/specs/15_requirements/REQUIREMENTS-PERF-001.md:28`) and `docs/briefs/BRIEF-performance.md:53`. At-rest protection is good (`0o600` via `secureio.py:43, 82`) and deletion exists (`p_remove` → `routes.py:930-949` incl. token unlink), but the declaration itself is absent from docs. | store `~/.config/mcp-gway/servers/*.json`; deletion `src/mcp_gway/admin/routes.py:930-949` | engineering owner + privacy-engineer consult | Document purpose/TTL(=until server removal)/deletion/owner for this store in the data map; TTL = none-by-design is an acceptable *declared* answer |
| DAT-005 | Low | Success path re-renders from the in-memory `updated` model instead of re-reading the store after `set_config` (`routes.py:920-926` uses `config=updated`). Today every field the detail view renders is in the payload, so no visible divergence — but combined with DAT-003 the UI can assert state that differs from disk on the next full page load. | `src/mcp_gway/admin/routes.py:917-926` | engineering owner (admin UI) | Re-load via `registry.get_config(name)` after a successful write |
| DAT-006 | Low | Timeout range unbounded on the new write path: any integer (incl. negative) passes handler + model (`routes.py:834-838`; `models.py:716` has no range validator). Type/null checks are solid; range check missing. | `src/mcp_gway/admin/routes.py:834-838`; `src/mcp_gway/models.py:716` | engineering owner | Range validation (e.g. >0, sane max) at the model validator |
| DAT-007 | Low | Validation-lineage docstring overclaims: "URL is revalidated through the SSRF guard (live DNS) on every save" — the model validator runs with `use_cache=True` and `SSRF_CACHE_TTL = 60.0`, so DNS is at most 60s stale. Fail-closed behavior itself holds (gate always runs, cache cannot bypass IP checks). | `src/mcp_gway/admin/routes.py:810-812` vs `src/mcp_gway/models.py:27, 748-749` | engineering owner (admin UI) | Correct the docstring ("SSRF guard on every save, DNS cached ≤60s") |

**Finding count: 7** (1 High, 3 Medium, 3 Low).

## Verified PASS (with proof)

- **Atomicity / integrity:** temp `O_EXCL` + `fsync` + `chmod 0o600` + `rename`, symlink fail-closed at every step (`secureio.py:14-84`). No partial-write window on the final path; a crash leaves at most an orphan `.tmp` (unlinked on next write). Concurrent CLI+dashboard writers share the fixed tmp name → the loser fails *loudly* ("Save failed" toast, `routes.py:909-912`), store stays consistent — matches the declared last-write-wins contract.
- **Masking (read path):** header values rendered as `••••••` with keys visible (`pages/servers.py:434-437`); OAuth shown as a badge only (`:438-445`); secret inputs are blank write-only fields (`:542-568`). Proof C1-C3: synthetic header value and client secret absent from rendered detail pages; key present. Test parity: `tests/test_admin_dashboard.py:204-213, 363-383`.
- **`.pyi` untouched by config save:** `set_config` writes only `json_path` (`registry.py:123-129`). Proof D1: byte-identical `.pyi` after PUT save; plus `tests/test_registry.py:214-227`.
- **OAuth token store:** dashboard never reads or writes token *contents*. `p_remove` unlinks `{name}.json` / `{name}_client.json` only (`routes.py:940-949`), disclosed in the confirm dialog (`pages/servers.py:485`); `p_auth` delegates to the same `refresh_server`/`oauth.FileTokenStorage` machinery as CLI `refresh --auth` (`routes.py:724-745`, `oauth.py:43-88`) — unchanged, `0o600`.
- **Secrets out of logs/toasts/artifacts:** see PII checkpoint above — no config values logged anywhere in `admin/routes.py` (grep of all `extra={...}`: only `server`, `tools` count, `reason` as exception type name).
- **Validation before persist:** SSRF re-gate runs inside `MCPServerConfig(**data)` on every save (`routes.py:897-900` → `models.py:744-749`); local commands re-gated + audited after model build (`routes.py:901-908`); env denylist enforced by model validator (`models.py:806-813`). Fail-closed on all rejection paths (no write on error — proven by `tests/test_admin_dashboard.py:402-418` asserting store unchanged).
- **Test evidence re-run (targeted):** `pytest tests/test_admin_dashboard.py tests/test_registry.py -q` → **57 passed** (34 in the admin file, matching the packet).

## Evidence log (commands, masked)

```
git diff -- src/mcp_gway/registry.py        # extract-refactor of add() payload + new set_config
git show HEAD:src/mcp_gway/registry.py      # HEAD payload identical: retry key never persisted (pre-existing)
PYTHONPATH=src .venv/bin/python /tmp/opencode/gw_data_review.py   # synthetic values, DNS stub per tests/conftest.py
  A1 add() persists retry key: False
  A2 get_config reads retry: True
  A3 PUT status: 200 | retry key after save: False | timeout: 7000
  B1 PUT status: 200
  B2 secret preserved: False | clientId preserved: False | scope now: openid profile
  C1 header value masked on detail page: True
  C2 clientSecret never on detail page: True
  C3 header key shown: True
  D1 PUT: 200 | pyi unchanged: True
.venv/bin/python -m pytest tests/test_admin_dashboard.py tests/test_registry.py -q  # 57 passed
```

No real secrets or PII appear in this artifact; test credentials are synthetic placeholders shown masked as «…».

## Verdict Rationale

**Conditional.** The store's integrity foundations are solid — atomic symlink-safe writes, fail-closed validation before every persist, `.pyi` contract isolated, masking correct on every read path, and zero secret leakage into logs/toasts. The gate does not pass because **DAT-001 (High)** is a silent credential-loss defect on an invited UI action with a clear fix-forward, and **DAT-002 + DAT-003 (Medium)** prove the payload schema drifts from the model schema with no versioning — the exact checklist failure this lens exists to catch. **Conditions to clear:** fix DAT-001 (per-field oauth merge + partial-edit test); fix the `_config_data` drift for DAT-002/003 (one root cause); declare purpose/TTL/deletion/owner for the credential store (DAT-004) with privacy-engineer consult. Lows (DAT-005..007) may ride the same PR but do not block. Residual risk if shipped unfixed: stored OAuth secret silently dropped on partial edit (High) and resilience flag opt-in that never persists (Medium).

---

## Re-gate addendum 2026-09-23

**Reviewer:** review-data (data lens, independent re-run)
**New verdict:** **conditional — narrowed**. The sole blocking High (**DAT-001**) is **CLOSED with fresh proof**. Open conditions are now Medium-tier waiver candidates (DAT-002/003/004, owner-deferred) plus one **newly found Medium (DAT-008)** surfaced while validating the DAT-001 fix. The line-5 header (`conditional`) remains the accurate verdict; its rationale above is superseded by this section.
**Method:** independent live probe against the check instance `http://127.0.0.1:8090` (temp registry `/tmp/opencode/gw-admin-check/servers`, seeded by me and self-cleaned to its original 3 servers), plus static file:line re-verification of every row. No source edits, no commits, no touch of `~/.config/mcp-gway`. Remediation scope reviewed: 3 gate Highs + CE-001; DAT-002/003/004 were owner-deferred by the orchestrator.

**Counts:** 7 original findings → **fixed 1** (DAT-001), **persisting 6** (DAT-002..007), **new 1** (DAT-008) = 8 rows total. **0 High open**, 4 Medium, 3 Low.

### Findings — re-verified status (updated rows)

| ID | Severity | Status | Evidence (file:line / command output) | Owner |
|----|----------|--------|---------------------------------------|-------|
| DAT-001 | High → *closed* | **CLOSED** | Fix: `_oauth_field` treats blank + bullet/asterisk sentinels as keep-stored (`src/mcp_gway/admin/routes.py:854-861`); per-field merge — blank keeps stored per field, non-blank replaces that field only (`routes.py:945-954`). Tests: 4 round-trip tests `tests/test_admin_dashboard.py:553-648` (scope-only byte-identical, all-blank keep, no-stored-stays-None, mask-sentinel). My live probe: P1/P2/P3/P5 below — all PASS. Remediation author's fails-before log `/tmp/opencode/h1_before.txt` (2 of 5 failed pre-fix) vs `h1_after.txt` (5 passed) consistent with my results. | engineering owner (admin UI) — **done** |
| DAT-002 | Medium | **PERSISTING** | `_config_data` still omits `retry_on_transport_error`: `grep -n "retry_on_transport_error\|schema_version" src/mcp_gway/registry.py` → **no match (exit 1)**; whitelist at `src/mcp_gway/registry.py:83-111`, consumed by `add` (`registry.py:114`) and `set_config` (`registry.py:126`). Checkbox read at `admin/routes.py:515,552,592`, control `admin/pages/servers.py:315`, model field `models.py:720`, runtime consumer `server_factory.py:77,119`. Operator opts in → 200 → flag absent after reload (unchanged from first review). | engineering owner (registry) — waiver candidate, expiry 2026-10-23 or v3.1.1 first |
| DAT-003 | Medium | **PERSISTING** | Destructive rewrite without schema versioning unchanged: `set_config` rewrites from whitelist `registry.py:123-129` + `83-111`; `schema_version` absent repo-wide (same grep, exit 1). Consume side: `routes.py:903` (`data = config.model_dump()`), `routes.py:967-968`. Any unknown/legacy key in an on-disk JSON is destroyed at first dashboard save; escalates to High the moment any writer legitimately persists a whitelisted-out key (DAT-002 is that writer-in-waiting). | engineering owner (registry) — waiver candidate, expiry 2026-10-23 or v3.1.1 first |
| DAT-004 | Medium | **PERSISTING** | Purpose/TTL/deletion/owner still undeclared: credential fields written at `registry.py:98-99` (environment), `registry.py:102-103` (headers), `registry.py:104-108` (oauth); at-rest `0o600` `secureio.py:43,59,82`; deletion = `p_remove` `routes.py:988-1011` incl. token unlink-only `routes.py:998-1007`. Requirements cite unchanged: `docs/specs/15_requirements/REQUIREMENTS-PERF-001.md:28` (REQ-NF-005, "Purpose+TTL+deletion por store") + `docs/briefs/BRIEF-performance.md:53`. `grep -rniE "purpose\|propósito\|TTL" docs/` for this store → only `GATE_REPORT.md:60` and this artifact — **no data-map declaration exists**. | engineering owner + privacy-engineer consult — waiver candidate, expiry 2026-10-23 |
| DAT-005 | Low | **PERSISTING** | Success path still re-renders from the in-memory model: `routes.py:978-980` (`config=updated`), no fresh `registry.get_config` after write. | engineering owner (admin UI) — backlog |
| DAT-006 | Low | **PERSISTING** | Timeout still unbounded: int-parse only `routes.py:891-895`; no range validator `models.py:716`. | engineering owner — backlog |
| DAT-007 | Low | **PERSISTING** | Docstring still overclaims "live DNS … on every save" `routes.py:865-869` vs `SSRF_CACHE_TTL = 60.0` `models.py:27` + `use_cache=True` `models.py:749`. Fail-closed gate itself unchanged (still runs every save). | engineering owner (admin UI) — backlog |
| **DAT-008** | **Medium (new)** | **NEW — input-side sibling of DAT-001** | **A user-typed non-UUID `clientId` is NOT persistable: it is silently replaced by a random `uuid4()` at construction.** Proof (live probe P4): typed value sha256 `197e333c518c…` → stored sha256 `1b99c6da29d6…`, stored parses as a UUID → silent replacement, HTTP 200, no warning. Code: `models.py:692-701` (`validate_client_id` returns `uuid4()` on any non-UUID — fires first, at the merge construction `routes.py:950`); second net `models.py:751-778` (`validate_oauth` dict/instance paths). Impact made real by the consumer: `oauth.py:451-466` — the replacement value IS a UUID → `is_manual=True` → the **random** UUID is used as pre-registered `client_id` → manual OAuth flow fails against the AS, while the UI accepted and "saved" the operator's real client ID. Affects AS-issued non-UUID client IDs (Google/GitHub/Okta style); dynamic-registration flows unaffected; no previously stored credential destroyed. **Pre-existing at HEAD** (`models.py` unmodified per `git status`; the same rotation was cited inside the original DAT-001 location), out of approved remediation scope this cycle. | engineering owner (models) — waiver candidate, expiry 2026-10-23 or v3.1.1 first |

**Checklist deltas:** PII/masking re-confirmed PASS (below); schema-versioning + migration path remain FAIL (DAT-003); lineage/quality remain PARTIAL (DAT-005/006). No checklist item regressed.

### DAT-001 closure proof — fresh live probe (hashes only, no values)

Script `/tmp/opencode/gw_data_recheck.py`, log `/tmp/opencode/gw_data_recheck.log` — **30 checks, 0 FAIL**. Synthetic credentials seeded into the temp registry, then removed (registry restored to its original 3 servers).

- **P1 scope-only PUT** (only `oauth_scope` non-blank, HTTP 200): stored `clientId` sha256 `11e594f48195…` → `11e594f48195…` (**byte-identical**); `clientSecret` sha256 `226f1770655c…` → `226f1770655c…` (**byte-identical**); scope updated to the typed value; all non-oauth fields equal; whole file changed by scope only; `.pyi` sha256 unchanged; response body contains neither secret nor header value.
- **P2 all-blank PUT** (HTTP 200): whole-file sha256 `6633a4bd8fc8…` → `6633a4bd8fc8…` — **byte-identical**, credentials kept.
- **P3 mask-sentinel PUT** (`••••••••` / `********`, HTTP 200): whole file **byte-identical** (`6633a4bd8fc8…`), no bullet/asterisk string persisted.
- **P5 no-stored-stays-None** on a server without oauth (HTTP 200): no `oauth` key created, whole file **byte-identical**.
- **Masking on read (G1–G7):** detail page HTTP 200; header value, `clientSecret`, and `clientId` all **absent** from rendered HTML (form prefill never echoes any of them — write-only inputs with placeholder only, `admin/pages/servers.py:553-571`); masked bullets rendered (`pages/servers.py:436-439`); OAuth shown as badge only (`pages/servers.py:440-447`); "blank keeps current" promise present.
- **Hygiene:** store perms `0o600` after all PUTs; zero `.tmp` leftovers; seeds self-removed.

**Verdict on DAT-001: fully closed as filed** (stored-credential wipe on partial edit — output side). The input-side sibling observed during closure is carved out as **DAT-008** (pre-existing, separately owned, Medium).

### Verified PASS — re-confirmed after this cycle's routes.py/registry churn

- **Atomicity:** unchanged single impl `secureio.py:15-84` — `O_EXCL 0o600` (:43), `fsync` (:49), `chmod 0o600` (:59,:82), symlink fail-closed at every step (:16-32, :62-75), fixed `.tmp` name (`:26`) → concurrent writers fail loudly (last-write-wins preserved).
- **Masking:** probe G2–G7 above; test parity `tests/test_admin_dashboard.py:204-213, 363-383`.
- **`.pyi` untouched by config save:** `set_config` writes only `json_path` (`registry.py:123-129`); probe P1 byte-identical `.pyi`.
- **Token store:** `p_remove` unlink-only, contents never read/written (`routes.py:998-1007`), dialog discloses token removal (`pages/servers.py:487`).
- **Zero secrets in logs:** post-churn grep of every `extra={…}` in `admin/routes.py` → only `server` / `tools` count / `reason` (exception type) / `timeout_s`; no config values logged.
- **Validation before persist:** SSRF re-gate inside model build every save (`routes.py:955-958` → `models.py:744-749`); local allow-list re-gate + audit (`routes.py:959-966`); rejection paths never write (probes returned error paths untouched store in suite).
- **Tests (my run):** `uv run pytest tests/test_admin_dashboard.py tests/test_registry.py -q` → **71 passed** (was 57; +14 incl. the 4 new OAuth round-trip tests). Full suite 619 + ruff clean: orchestrator re-run (cited, not mine).

### Evidence log (commands, masked)

```
.venv/bin/python /tmp/opencode/gw_data_recheck.py    # live 127.0.0.1:8090, temp registry → 30 checks, 0 FAIL
  G1..G7 masking PASS | P1 scope-only: cid 11e594f48195..= csec 226f1770655c..= byte-identical, .pyi unchanged
  P2 all-blank: file 6633a4bd8fc8..= byte-identical | P3 sentinels: byte-identical, no bullet persisted
  P4 non-UUID cid typed 197e333c518c.. → stored 1b99c6da29d6.. (random UUID) — NOT persisted
  P5 no-stored stays None, byte-identical | H1 0o600 | H2 no .tmp | cleanup: registry restored (3 servers)
grep -n "retry_on_transport_error\|schema_version" src/mcp_gway/registry.py   # no match, exit 1 (DAT-002/003)
grep -rn "extra={" src/mcp_gway/admin/routes.py | grep -v "server|tools|reason|timeout_s"   # empty (no secrets in logs)
grep -rniE "purpose|propósito|TTL" docs/ | grep <store>                        # only GATE_REPORT + this artifact (DAT-004)
uv run pytest tests/test_admin_dashboard.py tests/test_registry.py -q          # 71 passed
git status --porcelain -- src/                                                # models.py unmodified → DAT-008 pre-existing
```

No real secrets or PII appear in this artifact; all credential material is recorded as sha256 prefixes (12 hex chars) or masked forms of synthetic test placeholders only.

### Updated verdict rationale

**Conditional (narrowed).** DAT-001 — the High that blocked the gate — is closed with a fresh, independent live probe: per-field merge holds byte-identical under scope-only, all-blank, and mask-sentinel saves, masking never echoes on any read path, and `.pyi`/atomic-write/token/log PASS items survived this cycle's churn. The gate still does not pass cleanly because three owner-deferred Mediums persist exactly as filed: **DAT-002 + DAT-003** (payload schema drift with no versioning — top persisting risk: the checkbox offers an opt-in that deterministically never persists, 200 OK, same silent-loss class as DAT-001 at config-flag level) and **DAT-004** (REQ-NF-005 purpose/TTL/deletion/owner declaration still absent — regulatory exposure under Ley 172-13). Additionally, validating the fix exposed **DAT-008 (Medium)**: non-UUID user-entered `clientId` silently uuid4-replaced and then used as a "pre-registered" client — broken manual OAuth with accepted-then-discarded input. **Conditions to clear (waiver candidates, owner + expiry assigned in rows):** DAT-002/003 one-root fix (registry owner) by 2026-10-23 or v3.1.1; DAT-004 data-map declaration + privacy-engineer consult by 2026-10-23; DAT-008 reject-or-preserve non-UUID clientId (models owner) by 2026-10-23 or v3.1.1; Lows DAT-005..007 backlog, non-blocking. Residual risk if shipped with waivers: resilience flag silently non-persisting (Medium), unknown-key destruction on save (Medium), undeclared credential-store governance (Medium), manual OAuth broken for non-UUID client IDs (Medium). Zero Highs remain open.
