# PROPOSED_CHANGES — Canonical PascalCase storage: add + refresh auto-rename (SPEC-PASCALCASE-STORAGE-001)

**Spec refs (reference-only):** `docs/specs/40_workspace/engineering/SPEC-PASCALCASE-STORAGE-001.md` · prior `SPEC-SERVER-CAPS-001` (sandbox dual-binding, f66c0ea — untouched).
**Execution mode:** `single` (engineering-only direct execution, no dispatch).
**DOMAINS:** `[engineering]`.
**Skills cited:** `frame-ship:using-frame-ship` → `frame-ship:translate-to-spec` → `frame-ship:propose-changes` (this proposal) → `frame-ship:review-architecture` → `frame-ship:execute-spec` → `frame-ship:quality-gate` → `frame-ship:verify-handoff`.
**Date:** 2026-09-20. **Owner:** vasquez (CTO, engineering chain owner).

---

## 1. Summary

Canonicalize server names at the storage layer using the single existing normalizer `to_pascal_case_identifier` (`code_mode.py:45`):
(1) `cli add` normalizes the requested name BEFORE validation/storage — new servers are born PascalCase;
(2) `cli refresh` auto-renames saved lowercase servers to PascalCase (atomic `.json`+`.pyi` + `config.name` + token stems), collision-safe;
(3) new `Registry.rename(old, new)` atomic helper; (4) `refresh <name>` resolves case-insensitively.

## 2. REQ-ID Traceability

| REQ-ID | Target File | Action | Description |
|---|---|---|---|
| REQ-F-001 | `src/mcp_gway/cli.py::add` | Modify | `canonical = to_pascal_case_identifier(name)` first; use canonical for config/audit/discovery/registry/echo. Import inside function (avoid `code_mode→registry` cycle at module import). |
| REQ-F-002 | `src/mcp_gway/cli.py::refresh` | Modify | Per saved server: if stem != PascalCase(stem) → `registry.rename` (+ token stems `$HOME/.config/mcp-gway/tokens/<old>[,_client].json`), continue under new name; `FileExistsError` → warn + keep original. |
| REQ-F-003 | `src/mcp_gway/registry.py` | Add method | `Registry.rename(old, new)`: validate both, no-op if equal, `FileNotFoundError` if source missing, `FileExistsError` on collision; write new `.json` (name updated) + `.pyi` via `_atomic_write_text`, then unlink old pair. |
| REQ-F-004 | `src/mcp_gway/cli.py::refresh` | Modify | Resolve `name` arg: exact → casefold match over `registry.list()` → not-found warning (existing behavior). |
| REQ-NF-001 | `tests/test_pascalcase_storage.py` | Create | add-canonicalizes (local, no network), already-canonical no-op, refresh-renames, collision-skip, case-insensitive resolve, rename unit tests. |
| REQ-NF-002 | repo | Verify | `pytest`, `ruff check`, `ruff format --check` green. |

## 3. Files to Create / Modify (no others touched)

- Modify: `src/mcp_gway/cli.py` (add + refresh only), `src/mcp_gway/registry.py` (+`rename` only).
- Create: `tests/test_pascalcase_storage.py`, this proposal + spec (docs only).
- Untouched: `code_mode.py`, `gateway.py`, `models.py` (validator unchanged — canonical output always passes `^[A-Za-z_][A-Za-z0-9_]{0,63}$`), OAuth/policy/transport.

## 4. Risk Assessment & Blast Radius

- **Systems:** Low-medium. `add` changes stored stems for non-canonical input (one-way rename of NEW servers only; old files never created so nothing orphans). `refresh` renames saved pairs — atomic-write-then-unlink keeps a crash from losing both; worst case old pair lingers (re-run converges).
- **Collision:** Two stems mapping to one canonical (`my_server` + `MyServer`) → second wins nothing; we warn + skip, both servers keep working (Code Mode resolves case-insensitively). No overwrite by construction.
- **Security:** No new trust boundary (names already flow to filesystem via `_safe_path`; canonical output is a strict subset of the validator alphabet). Token stems renamed with `os.replace` semantics via rename; no contents touched, no secrets logged. No PII (server names are operator-chosen, not user data).
- **Customers/regulators/revenue:** None — local-first CLI, no external surface, no prod env.
- **Rollback:** `git revert`; already-renamed servers keep working (canonical names are valid everywhere old ones were). No migration needed.

## 5. Approvers

- Engineering owner (vasquez, self as author — architecture review records verdict, no self-approval of proposal).
- Security review: not required (no auth/data/API/PII surface change) — noted explicitly, `review-security` skipped with rationale.
- Prior failed attempt (agy session, test failed): root cause unknown from this lane; this proposal de-risks via new isolated test file + full-suite gate before handoff.
