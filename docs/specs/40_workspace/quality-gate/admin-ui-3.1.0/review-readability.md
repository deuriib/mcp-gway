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
