# Readability Review: admin-ui-3.1.0

**Reviewer:** review-readability (engineering domain, frame-ship quality gate)
**Date:** 2026-09-23
**Verdict:** conditional

**Scope:** read-only review of the working tree per `quality-gate/references/engineering/readability-review.md`.
Files reviewed: `src/mcp_gway/admin/**` (NEW), `tests/test_admin_dashboard.py` (NEW),
modified `src/mcp_gway/{registry,gateway,cli}.py`, `src/mcp_gway/observability/middleware.py`,
modified tests. No source edits, no commits.

**Verification commands run:**

- `uv run ruff check src/ tests/` → no findings
- `uv run ruff format --check src/ tests/` → `89 files already formatted`
- Grep sweeps for icon usage, `notice=` producers, `oauth_port`, `add_server_form` (evidence per finding)

## Checklist

- [x] Naming is intention-revealing — one shadowing violation (RD-001); `h_*`/`p_*` handler
      prefixes and fragment docstrings ("INNER content for #id") are exemplary
- [~] Functions have single responsibility — helpers are small and focused; two route
      handlers are 4x over the length budget (RD-003)
- [x] Nesting depth <= 3 — no violation found
- [~] Comments explain WHY, not WHAT — WHY comments are strong (gateway.py CSP block,
      middleware.py cardinality note, theme.py shadow rationale); token section labels
      are WHAT (RD-016)
- [~] Public APIs documented — most public functions carry docstrings; gaps at RD-013
- [~] No dead code or commented-out blocks — no commented-out code anywhere; unused icons,
      unreachable notice keys, a dropped form field and a dead parameter found
      (RD-002, RD-006, RD-007, RD-008, RD-012)
- [~] Consistent style with surrounding code — ruff green, uniform module structure and
      `from __future__ import annotations` in all substantive modules; copy-paste and
      style-token drift found (RD-004, RD-005)

## Findings

| ID | Severity | Location | Finding |
|----|----------|----------|---------|
| RD-001 | Medium | `src/mcp_gway/admin/routes.py:846` | Local variable `data = config.model_dump()` shadows the module-level import `from mcp_gway.admin import data` (`routes.py:27`). Two different meanings for one name in a 1,159-line module; adding `data.server_rows(...)` inside `p_set_config` later would raise a confusing `AttributeError`. Owner: engineering. |
| RD-002 | Medium | `src/mcp_gway/admin/pages/servers.py:286` | Dead form field: the add-modal input `oauth_port` is rendered but never read — `p_add_server` (`routes.py:435-593`) reads only `oauth_client_id/secret/scope`; grep of `src/` shows no `form.get("oauth_port")` anywhere. `_refresh_one` always runs with the default 8989 (`routes.py:677,695`). The field silently drops user input — misleading UI + dead code. Cross-check with the functional reviewer (likely a functional gap too). Owner: engineering. |
| RD-003 | Medium | `src/mcp_gway/admin/routes.py:435-593` | Oversized handlers: `p_add_server` is 159 lines (parse → validate → policy gate → transport detect → discover tools → regate → persist → render) and `p_set_config` is 119 lines (`routes.py:809-927`). Each mixes multiple responsibilities beyond "one handler = one step"; at 4x the 40-line soft budget they resist review and testing of individual steps. Owner: engineering. |
| RD-004 | Medium | `src/mcp_gway/admin/pages/servers.py:85-91`, `pages/overview.py:37-43` | Verbatim copy-paste (banned anti-pattern): `_type_badge` duplicated identically incl. docstring (`servers.py:85-91` = `overview.py:37-43`); `_field` duplicated (`servers.py:80-82` = `pages/tools.py:50-52`); uptime formatter duplicated under two names (`routes.py:112-120` `_fmt_uptime` = `pages/policy.py:35-44` `_fmt_seconds`); `_LOOPBACK` tuple defined three times (`routes.py:46`, `pages/observability.py:20`, `pages/policy.py:20`). Four copies that must change in lockstep. Owner: engineering. |
| RD-005 | Low | `src/mcp_gway/admin/components.py:31-49` vs `pages/servers.py:44-58`, `pages/overview.py:19-29`, `pages/policy.py:22-30` | Pill/variant class strings duplicated across four modules and already diverging: components' `green` appends `font-bold` while `overview._GREEN_PILL` does not; `policy._PILL_BASE` omits the `disabled:` utilities present in `servers._PILL_BASE`. Style drift risk instead of single source in `components._VARIANTS`. Owner: engineering. |
| RD-006 | Low | `src/mcp_gway/admin/icons.py:35,91,103,113,122,126,130,153` | Dead code: 8 of ~20 icon functions are never referenced outside `icons.py` (`icon_play`, `icon_check`, `icon_overview`, `icon_server`, `icon_terminal`, `icon_activity`, `icon_shield`, `icon_code` — grep evidence). The module docstring itself admits `icon_play` is "legacy mark, unused by the shell" (`icons.py:5-6`). Owner: engineering. |
| RD-007 | Low | `src/mcp_gway/admin/routes.py:51,53,54,57-60` | Dead code: `NOTICE_MESSAGES` keys `"added"`, `"updated"`, `"refreshed"`, `"auth-started"` have no producer — grep of `notice=` in `src/` yields only `config-unreadable`, `config-not-saved`, `config-saved`, `removed`, `policy-enabled`, `policy-disabled`, `executed`; tests reference only those keys too. Owner: engineering. |
| RD-008 | Low | `src/mcp_gway/admin/routes.py:190-191` | `_form_token` is a pure alias of `_csrf_token` (`routes.py:82-84`) — two names for one behavior, and call sites are split inconsistently (`_csrf_token` at `:160`, `_form_token` at `:305,:326,:403,:924`). Owner: engineering. |
| RD-009 | Low | `src/mcp_gway/admin/routes.py:698-700` | The same tone value computed twice on adjacent lines in inverted forms: `"red" if not success else "green"` inline at `:698`, then `tone = "green" if success else "red"` at `:699`. Owner: engineering. |
| RD-010 | Low | `src/mcp_gway/admin/routes.py:1107-1110` | `p_empty` re-implements the loopback branch of `_gate` (`routes.py:94-101`) by hand instead of calling it; the two checks can drift independently. Owner: engineering. |
| RD-011 | Low | `src/mcp_gway/admin/routes.py:126-134,218-230,351-372,1084-1098` | Duplicated assembly blocks: health try/except appears in both `_status_node` (`:131-134`) and `h_index` (`:227-230`); the 5-key `stats` dict + exposition try/except is copied verbatim between `h_observability` (`:351-361`, `:369-372`) and `p_metrics` (`:1084-1098`). Owner: engineering. |
| RD-012 | Low | `src/mcp_gway/admin/pages/servers.py:225` | `add_server_form(csrf_token="")` — the only call site passes an empty string, so the `csrf_token` parameter and the hidden `_csrf` input (`servers.py:251`) never carry a real token (the token rides the body-level `hx-headers` instead). The parameter advertises a contract it never fulfills. Owner: engineering. |
| RD-013 | Low | `src/mcp_gway/admin/components.py:168,212,233,246`; `admin/data.py:11-19` | Missing docstrings on public functions while immediate siblings have them: `label_text`, `textarea`, `select`, `checkbox` (contrast `badge`, `stat_card`, `section_title`); `ServerRow` dataclass and its fields undocumented. Repo convention requires docstrings on public functions. Owner: engineering. |
| RD-014 | Low | `src/mcp_gway/admin/routes.py:267` vs `:596-599` | Inconsistent indirection: `h_server_detail` local-imports `mcp_gway.cli._resolve_saved_name` directly while every other handler goes through the `_resolve_name` wrapper (which does nothing but re-import the same symbol). The function-level import pattern (used ~10x in the module) carries no WHY note — presumed circular-import avoidance, but a reader can't tell. Owner: engineering. |
| RD-015 | Low | `tests/test_admin_dashboard.py:330-336` | Inconsistent/imprecise typing: `monkeypatch: object` plus two `# type: ignore[attr-defined]` suppressions, while `test_add_local_command_denied_by_policy` types the same fixture correctly as `pytest.MonkeyPatch` (`:171-174`). Owner: engineering. |
| RD-016 | Low | `src/mcp_gway/admin/theme.py:14,21,26,31,36,48` | WHAT-comments (section labels `# Surfaces`, `# Text`, `# Semantic`, ...) deviate from the repo convention "No comments unless explicitly requested" (AGENTS.md → Code Conventions). The WHY comments in the same file (`theme.py:41-46`) and elsewhere (`gateway.py` CSP block, `middleware.py` cardinality note) are exemplary and should stay. Owner: engineering. |
| RD-017 | Low | `src/mcp_gway/admin/__init__.py:1`, `admin/pages/__init__.py:1-3` | Convention nit: both `__init__.py` files omit `from __future__ import annotations` while the convention asks for it in all modules (harmless here — neither declares annotations). Owner: engineering. |

**Severity summary:** 4 Medium (RD-001..RD-004), 13 Low. No Critical, no High.

## Checklist notes (positive evidence)

- Every substantive new module opens with `from __future__ import annotations` and a module
  docstring that states the layer contract (`pages/__init__.py` even documents the
  innerHTML/outerHTML fragment rule).
- WHY-commenting quality is high where it matters: `gateway.py` CSP relaxation block,
  `middleware.py` `path_template` cardinality note, `components.modal` peer-checkbox
  rationale, `components.kv_row` flush-right rationale, `data.server_rows` sort contract.
- Naming is intention-revealing across the package: `h_*` full-page vs `p_*` partial,
  `*_content` vs `*_fragment` vs `INNER content for #id` docstrings, `_gate`, `_reject`,
  `_notice_frag`. No `data`/`tmp`/`x` style names apart from RD-001's shadow.
- No commented-out code blocks found in the reviewed tree.
- Tests mirror `src/` layout, use purpose-revealing names, synthetic-only data, and WHY
  docstrings where the regression story is non-obvious (`:273, :387`).

## Verdict Rationale

**conditional.** The package is consistently styled (ruff check + format green over
89 files), well-layered, and mostly documented; nesting stays within bounds and naming is
strong. The condition: 4 Medium findings must be addressed or explicitly waived before
CLOSED — the `data` module-name shadowing (RD-001), the silently-dropped `oauth_port`
form field (RD-002, functional reviewer should cross-check), the two oversized route
handlers (RD-003), and the four-way copy-paste cluster (RD-004). The 13 Low findings are
hygiene/backlog material and do not block the gate on their own.

Findings are reported for the owning team; no fixes were made by this reviewer
(report severity + location + owner only). No secrets or PII appear in this artifact.

---

## Re-gate addendum 2026-09-23

**Reviewer:** review-readability (engineering domain) — re-verification after the
remediation cycle (scope: gate Highs H1–H3 + CE-001 only; this reviewer's Mediums
explicitly deferred to backlog by the user).

**Re-gate verdict:** **pass** — with the 4 Mediums recorded below as
*accepted-deferred* (owner: engineering, backlog), not fixed.

**Assumption behind the judgment call (stated per guardrails):** readability Mediums
are non-blocking severity (only Critical/High block release), and the user's explicit
deferral of RD-001..RD-004 to backlog is the documented waiver path my original
condition allowed ("addressed *or explicitly waived*"). Pass = no readability
blocker for this cycle — it does not mean the 19 open findings are resolved.

**Counts:** 1 fixed · 16 persisting from prior 17 (4 Medium deferred + 12 Low) ·
3 NEW Low. Regressions: none. Severity after re-gate: 4 Medium (deferred),
15 Low (12 prior + 3 new). Total open: 19.

**Verification commands run (this re-gate):**

- `uv run ruff check src/ tests/` → exit 0, no findings
- `uv run ruff format --check src/ tests/` → `89 files already formatted`
- `grep -cE '^(async )?def test_' tests/test_admin_dashboard.py` → `48` (14 new tests)
- `grep -rn 'data =' src/mcp_gway/admin/` → only `routes.py:28` (import) and `routes.py:903` (shadow)
- `grep -rn 'notice=' src/` → 9 hits; no producer for `added|updated|refreshed|auth-started`
- `grep -rn 'oauth_port' src/` → zero `form.get("oauth_port")`; field still rendered `servers.py:288`
- `grep -rn 'HX-Retarget' src/mcp_gway/admin/` → identical header dicts `routes.py:847` and `routes.py:1112`

### Updated finding table (status re-verified against current tree)

| ID | Severity | Status | Current location (line shifts from remediation) |
|----|----------|--------|--------------------------------------------------|
| RD-001 | Medium | **persisting** (moved) | Shadow now `src/mcp_gway/admin/routes.py:903` (`data = config.model_dump()`) vs module import `routes.py:28`; module `data` used at `routes.py:261,297,338,476,623,648`. Latent, not live: `p_set_config` stops touching module `data` after `:903` (row lookup goes through `_find_row` at `:975`). Owner: engineering. |
| RD-002 | Medium | **persisting** (moved) | Field still rendered `src/mcp_gway/admin/pages/servers.py:288`; `p_add_server` (`routes.py:480-638`) reads only `oauth_client_id/secret/scope` (`:574-576`). Port hardcoded in 3 places, user input still dropped: `routes.py:685` (default param) and `routes.py:773` (literal in `p_auth`). Owner: engineering. |
| RD-003 | Medium | **persisting** (moved, slightly worse) | `p_add_server` `routes.py:480-638` = 159 lines (unchanged, 4x budget); `p_set_config` `routes.py:864-985` = 122 lines — grew +3 from the OAuth merge (was 119). Owner: engineering. |
| RD-004 | Medium | **persisting** (moved) | `_type_badge` verbatim incl. docstring: `servers.py:85-91` = `overview.py:37-43`; `_field` body: `servers.py:80-82` = `tools.py:50-52`; uptime formatter body: `routes.py:157-165` `_fmt_uptime` = `policy.py:35-44` `_fmt_seconds` (routes copy lacks the docstring the policy copy has); `_LOOPBACK` ×3: `routes.py:47`, `pages/observability.py:20`, `pages/policy.py:20`. Owner: engineering. |
| RD-005 | Low | **persisting** (moved) | Four pill-base sources: `components.py:31-40,79-85`, `servers.py:44-48`, `policy.py:22-26`, `overview.py:19-29`. Verified drift: `policy._PILL_BASE` omits `transition-colors disabled:opacity-50 disabled:pointer-events-none` present in `servers._PILL_BASE` and `components.pill_button`. Correction: the prior `font-bold` sub-claim is **not reproducible** in the current tree (both `components._VARIANTS["green"]` `:33` and `overview._GREEN_PILL` `:25-29` contain `font-bold`) — that sub-claim is refuted on re-check; the structural duplication + disabled-utility drift stand. Owner: engineering. |
| RD-006 | Low | **persisting** (unchanged) | 8 unreferenced icons still dead: `icons.py:35,91,103,113,122,126,130,153` (grep: definitions only, no callers outside `icons.py`). Owner: engineering. |
| RD-007 | Low | **persisting** (moved) | Dead keys now `routes.py:57` (`added`), `:59` (`updated`), `:60` (`refreshed`), `:63-66` (`auth-started`) — `grep notice= src/` yields no producer. Positive: the new `exec-timeout` key (`routes.py:68-71`) IS live via `routes.py:1114`. Owner: engineering. |
| RD-008 | Low | **persisting** (moved) | `_form_token` alias at `routes.py:235-236`; split call sites persist: `_form_token` at `:350,:371,:448,:982` vs `_csrf_token` at `:97,:205`. Owner: engineering. |
| RD-009 | Low | **persisting** (moved) | Inverted-tone pair at `routes.py:743-744` (`"red" if not success else "green"` then `tone = "green" if success else "red"`). Owner: engineering. |
| RD-010 | Low | **FIXED** | `p_empty` now delegates to the gate: `routes.py:1197-1201` = `denied = await _gate(request)` → return; the hand-rolled loopback branch is gone (one source of truth). Evidence: full read of `p_empty` + REQ-H2 gate restructure. |
| RD-011 | Low | **persisting** (moved, expanded) | Health try/except: `routes.py:176-179` (`_status_node`) = `routes.py:272-275` (`h_index`). 6-key `stats` dict + exposition try/except: `routes.py:396-417` (`h_observability`) = `routes.py:1179-1193` (`p_metrics`). **New duplicate pair added by remediation:** identical `HX-Retarget` toast-response construction at `routes.py:845-848` (`_reject`) vs `routes.py:1110-1113` (`_exec_timeout_response`) — the new helper's docstring declares it "mirroring `_reject`", which documents but does not deduplicate. Owner: engineering. |
| RD-012 | Low | **persisting** (moved) | `add_server_form(csrf_token="", ...)` at `servers.py:227`; hidden `_csrf` input at `servers.py:253` still carries the empty value. Owner: engineering. |
| RD-013 | Low | **persisting** (unchanged) | Missing docstrings: `components.py:168` (`label_text`), `:212` (`textarea`), `:233` (`select`), `:246` (`checkbox`) vs documented siblings `badge:141`, `stat_card:118`, `section_title:151`; `ServerRow` + fields `data.py:11-19`. Owner: engineering. |
| RD-014 | Low | **persisting** (moved) | Direct import `routes.py:312` (`h_server_detail`) vs wrapper `_resolve_name` `routes.py:641-644` used at `:690,:739,:753,:809,:827,:882,:993`; no WHY note on the pattern. Owner: engineering. |
| RD-015 | Low | **persisting** (moved) | `monkeypatch: object` now `tests/test_admin_dashboard.py:340` with `# type: ignore[attr-defined]` at `:343-344`; correct typing at `:181-183`. Owner: engineering. |
| RD-016 | Low | **persisting** (unchanged) | WHAT section labels `theme.py:11,14,21,26,31,36,41,45,48`; WHY comments (`:41-46`) exemplary and to stay. Owner: engineering. |
| RD-017 | Low | **persisting** (unchanged) | `admin/__init__.py:1` and `admin/pages/__init__.py:1-3` still omit `from __future__ import annotations`. Owner: engineering. |
| RD-018 | Low | **NEW** | `src/mcp_gway/admin/routes.py:47-48` — two loopback host constants in one module with different membership: `_LOOPBACK = ("127.0.0.1", "::1", "localhost")` vs `_ALLOWED_HOSTS = frozenset({..., "[::1]"})`, consumed two lines apart in `_gate` (`:136` then `:142`) with no comment explaining why both exist (answer is only discoverable by reading `_normalize_host`: it can return the bracketed form). Compounds RD-004's triple `_LOOPBACK`. Owner: engineering. |
| RD-019 | Low | **NEW** | `src/mcp_gway/admin/routes.py:137-140` vs `:143-146` — REQ-H2 introduced the identical 403 `HTMLResponse` literal twice on adjacent branches of `_gate`; copy-paste within one new function. Owner: engineering. |
| RD-020 | Low | **NEW** | `tests/test_admin_dashboard.py:532-546` — `_seed_oauth` re-builds the exact Demo config + tool of `_seed_demo` (`:33-41`) verbatim instead of reusing it, and hardcodes the OAuth credential literals at `:542-544` while module constants for the same values sit 6 lines below (`_OAUTH_CID`/`_OAUTH_SECRET`, `:549-550`) and are what the assertions use — two sources of truth for one test credential (drift ⇒ confusing assertion failures). Values are synthetic; no real secrets. Owner: engineering. |

### New-code readability review (remediation helpers) — positive evidence

- `_oauth_field` (`routes.py:854-861`): intention-revealing name, docstring explains
  the WHY of mask sentinels; per-field merge at `:945-955` reads top-down.
- `_normalize_host` (`routes.py:104-126`): docstring states the fail-closed contract
  and every branch; nesting ≤ 3.
- `_exec_timeout` (`routes.py:1090-1101`) + named bounds `routes.py:52-54`: no magic
  numbers, clamp logic explicit; `_exec_timeout_response` (`:1104-1114`) documents its
  mirroring of `_reject`.
- Toolbar floors (`pages/servers.py:211-231`): plain composition, classes asserted by
  the named test `test_toolbar_flex_children_share_identical_floors`
  (`tests/test_admin_dashboard.py:841-854`).
- The 14 new tests follow house style: purpose-revealing names, synthetic-only
  credentials, matrix tests (`test_normalize_host_fails_closed_matrix:701`,
  `test_exec_timeout_clamps_and_defaults:814`) keep per-case asserts readable.

### Verdict Rationale (re-gate)

**pass.** The remediation code itself is readable: helpers are small, single-purpose,
documented with WHY, and introduced only 3 Low findings (RD-018–RD-020) plus one
duplicate pair folded into RD-011 — hygiene, not blockers. 1 of 17 prior findings is
fixed (RD-010); 16 persist with updated line numbers, of which the 4 Mediums
(RD-001..RD-004) are *accepted-deferred to backlog by explicit user decision,
recorded here with owner=engineering* — they remain open findings and must be
re-surfaced if the deferral expires. ruff check/format stay green; the admin test
module is at 48 tests. No regressions, no Critical/High from this reviewer.
No source edits, no commits; no secrets or PII in this artifact.
