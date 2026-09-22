# Requirements Index: Universal Casing Ingestion & Canonical PascalCase Exposure

**Owner:** vasquez (CTO)
**Brief Reference:** BRIEF-CASING-001
**Domains-Touched:** [engineering, automation]

## Functional Requirements

| ID | Requirement | Priority | Source | Spec | Domain | Evidence Type |
|----|-------------|----------|--------|------|--------|---------------|
| REQ-F-001 | `to_pascal_case_identifier` normalizes all-caps, snake_case, kebab-case, camelCase, and delimiters into valid PascalCase | P0 | BRIEF-CASING-001 | SPEC-CASING-001 | engineering | test (`tests/test_pascalcase_storage.py`) |
| REQ-F-002 | `cli add` canonicalizes `name` before validation and stores canonical PascalCase `.json` and `.pyi` stubs | P0 | BRIEF-CASING-001 | SPEC-CASING-001 | engineering | test (`tests/test_pascalcase_storage.py`) |
| REQ-F-003 | `cli refresh` auto-migrates existing servers and token files with non-canonical stems to PascalCase with collision guard | P0 | BRIEF-CASING-001 | SPEC-CASING-001 | engineering | test (`tests/test_pascalcase_storage.py`) |
| REQ-F-004 | CLI commands `remove`, `inspect`, `update`, `refresh` resolve server names case-insensitively | P0 | BRIEF-CASING-001 | SPEC-CASING-001 | engineering | test (`tests/test_pascalcase_storage.py`) |
| REQ-F-005 | `mcp-gway list` and Code Mode meta-tools expose and bind canonical PascalCase names | P1 | BRIEF-CASING-001 | SPEC-CASING-001 | engineering | test (`tests/test_cli.py`, `tests/test_code_mode.py`) |

## Non-Functional Requirements

| ID | Requirement | Category | Target |
|----|-------------|----------|--------|
| REQ-NF-001 | Test suite green + strict lint parity | Reliability | Full `uv run pytest` pass, `ruff check` + `ruff format --check` clean |
| REQ-NF-002 | Local-first security & atomicity | Security | Zero secrets in logs, atomic file writes via `secure_atomic_write_text`, collision protection |

## Domain Controls (only touched domains)

| Domain | Control | Owner |
|--------|---------|-------|
| engineering | Single canonical PascalCase normalizer in `code_mode.py`; case-insensitive resolution helper in `cli.py`; atomic renames in `registry.py` | vasquez |
| automation/ops | CI validation of casing matrices and migration regression suites | automation owner |
