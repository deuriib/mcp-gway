# IMPLEMENTATION_PLAN — Universal Casing & PascalCase Exposure (SPEC-CASING-001)

**Spec Reference:** `docs/specs/20_backlog/SPEC-CASING-001.md`  
**Execution Mode:** `multi-subagents`  
**Owner:** vasquez (CTO)  
**Date:** 2026-09-20  

---

## Steps & Order

| Step | Target File | Action | Evidence / Verification |
|---|---|---|---|
| **1** | `src/mcp_gway/code_mode.py` | Upgrade `to_pascal_case_identifier` to split camelCase, delimiters, and title-case acronyms/tokens | `pytest tests/test_pascalcase_storage.py::test_to_pascal_case_variants` |
| **2** | `src/mcp_gway/cli.py` | (a) Enhance `_resolve_saved_name` to match exact, canonical PascalCase, and casefold; (b) wire `_resolve_saved_name` into `remove`, `inspect`, and `update` | `pytest tests/test_pascalcase_storage.py::test_cli_case_insensitive_*` |
| **3** | `tests/test_pascalcase_storage.py` | Expand test matrix for all casing variants (`GITHUB`, `WEATHER_SERVICE`, `myServer`, `my-server`, `123server`), CLI commands, and refresh auto-migration | `pytest tests/test_pascalcase_storage.py` |
| **4** | Full Suite & Linter | Run `pytest -v`, `ruff check src/ tests/`, `ruff format --check src/ tests/` | 100% green |
