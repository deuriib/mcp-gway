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
