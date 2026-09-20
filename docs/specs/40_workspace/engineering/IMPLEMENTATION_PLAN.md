# IMPLEMENTATION_PLAN — Server Naming Capitalization Normalization (SPEC-SERVER-CAPS-001)

**Spec Reference:** `SPEC-SERVER-CAPS-001`  
**Execution Mode:** `single`  
**Owner:** vasquez (CTO)  
**Date:** 2026-09-19  

---

## Steps & Order

| Step | Target File | Action | Evidence / Verification |
|---|---|---|---|
| **1** | `src/mcp_gway/code_mode.py` | Add `to_pascal_case_identifier(name: str) -> str` | `pytest tests/test_code_mode.py::test_to_pascal_case_identifier` |
| **2** | `src/mcp_gway/code_mode.py` | Update `_inject_tools` with dual binding | `pytest tests/test_code_mode.py::test_sandbox_has_server_structs` |
| **3** | `src/mcp_gway/code_mode.py` | Update `refresh` to automatically manage capitalized aliases | `pytest tests/test_code_mode.py::test_refresh_automatic_capitalization` |
| **4** | `src/mcp_gway/registry.py` | Update `_generate_pyi` stub comments with capitalized server name | `pytest tests/test_registry.py::test_pyi_usage_comment_capitalized` |
| **5** | `src/mcp_gway/gateway.py` | Update tool schema docstrings with capitalized examples | Code inspection + schema validation |
| **6** | `tests/test_code_mode.py` | Add comprehensive unit & integration tests | `pytest tests/test_code_mode.py` |
| **7** | `tests/test_registry.py` | Add test asserting PascalCase in `.pyi` header | `pytest tests/test_registry.py` |
| **8** | Full Suite & Linter | Run `pytest -v`, `ruff check`, `ruff format --check` | 100% green |
