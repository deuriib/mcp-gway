# SPEC-PASCALCASE-STORAGE-001 — Canonical PascalCase server names on add + auto-rename on refresh

**Brief ref:** chat-BRIEF-montilla 2026-09-20 (PascalCase) · **Execution mode:** `single` · **DOMAINS:** `[engineering]` · **Owner:** vasquez (CTO)
**Date:** 2026-09-20 · **Skills cited:** `frame-ship:using-frame-ship` + `frame-ship:translate-to-spec`
**Prior art:** SPEC-SERVER-CAPS-001 (f66c0ea) did sandbox dual-binding + `.pyi` comments only; storage (`config.name`, `servers/*.json|*.pyi` stems) stayed as-typed.

## Context

`to_pascal_case_identifier` (`code_mode.py:45`) is canonical. Registry filenames + `config.name` are still raw user input, so `add my_server` stores `my_server.json` while Code Mode shows `MyServer`. Intent: canonicalize at the storage layer so new + saved servers converge on PascalCase.

## REQ-IDs

| REQ-ID | Type | Description | Acceptance |
|---|---|---|---|
| REQ-F-001 | Functional | `cli add` canonicalizes `name` via `to_pascal_case_identifier` BEFORE validation/storage; all downstream (config, discovery, audit, registry, echo) uses canonical | `add my_server` stores `MyServer.json/.pyi` with `config.name=="MyServer"`; already-canonical `add Filesystem` no-op |
| REQ-F-002 | Functional | `cli refresh` auto-renames each saved server whose stem != PascalCase(stem): atomic `.json`+`.pyi` rename, `config.name` updated in JSON, old stems removed, tokens (`<old>.json`, `<old>_client.json`) renamed when present; collision (canonical target exists, different server) → warn + skip, keep original | lowercase fixture renamed on refresh; collision fixture untouched with warning |
| REQ-F-003 | Functional | `Registry.rename(old, new)` atomic helper: validates both names, no-op when equal, raises `FileNotFoundError` when source missing, `FileExistsError` on collision; writes new `.json` (with updated `name`) + `.pyi` atomically then removes old pair | unit-tested directly |
| REQ-F-004 | Functional | `cli refresh <name>` resolves case-insensitively (exact first, then casefold match) so pre-rename lowercase invocations still work | `refresh myserver` finds `Myserver`/`MyServer` |
| REQ-NF-001 | Non-functional | `ruff check`, `ruff format --check`, full `pytest` green; no behavior change for already-canonical names | CI parity |
| REQ-NF-002 | Non-functional | Local-first + atomicity preserved: `secure_atomic_write_text` path, no secrets in logs, `127.0.0.1` default untouched | review |

## Architecture contract

- Single normalizer: `code_mode.to_pascal_case_identifier` (no duplicate impl; `cli` + `registry` import it).
- `Registry.rename` lives in `registry.py`; `cli.refresh` orchestrates (rename → `get_config` → `refresh_server` → `update`).
- Collision policy: never overwrite — `FileExistsError` → CLI warns and continues with original name (reversible, no loss).
- Out of scope: `remove`/`inspect`/`update`/`list` rename logic; Code Mode sandbox (already done); token contents (only file stems).

## Test trace

REQ-F-001 → `tests/test_pascalcase_storage.py::test_add_canonicalizes_*` · REQ-F-002 → `test_refresh_renames_*` + collision test · REQ-F-003 → `test_registry_rename_*` · REQ-F-004 → `test_refresh_case_insensitive` · REQ-NF-001 → full suite + ruff.
