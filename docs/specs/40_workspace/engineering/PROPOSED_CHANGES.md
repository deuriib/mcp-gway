# PROPOSED_CHANGES — Server Naming Capitalization Normalization (SPEC-SERVER-CAPS-001)

**Spec Reference:** `SPEC-SERVER-CAPS-001`  
**Owner:** vasquez (CTO, engineering chain owner)  
**Date:** 2026-09-19  
**Execution Mode:** `single` (engineering-only direct execution)  
**DOMAINS:** `[engineering, security]`  
**Skills cited:** `frame-ship:using-frame-ship` → `frame-ship:propose-changes` → `frame-ship:execute-spec` → `frame-ship:quality-gate` → `frame-ship:verify-handoff` → `frame-ship:ship-release`  

---

## 1. Summary of Proposed Changes

Implements server naming normalization to PascalCase / Capitalization (`Server.tool`) in Code Mode.
Introduces a deterministic identifier normalizer (`to_pascal_case_identifier`), establishes dual binding in `StarlarkSandbox` (`Server` capitalized primary + original lowercase alias for zero breaking changes), automatically synchronizes capitalized bindings during dynamic `CodeMode.refresh()`, and aligns `.pyi` virtual stub documentation and gateway tool schema descriptions.

---

## 2. REQ-ID Traceability

| REQ-ID | Target File | Action | Description |
|---|---|---|---|
| **REQ-F-001** | `src/mcp_gway/code_mode.py` | Add Function | Add `to_pascal_case_identifier(name: str) -> str` handling hyphens, underscores, dots, and digits |
| **REQ-F-002** | `src/mcp_gway/code_mode.py` | Modify | Dual binding in `CodeMode._inject_tools`: inject both original server name and PascalCase alias into sandbox |
| **REQ-F-003** | `src/mcp_gway/code_mode.py` | Modify | Dynamic `CodeMode.refresh()`: auto-detect and sync PascalCase and lowercase aliases on add/remove |
| **REQ-F-004** | `src/mcp_gway/registry.py` | Modify | `Registry._generate_pyi`: update `# Usage:` and sanitized names comment to use PascalCase `{cap_name}.tool_name` |
| **REQ-F-005** | `src/mcp_gway/gateway.py` | Modify | Update `listToolFiles`, `executeToolCode` schema docstrings with capitalized examples |
| **REQ-NF-001** | `tests/test_code_mode.py` | Modify | Unit/Integration tests: `to_pascal_case_identifier`, dual binding execution, refresh auto-capitalization |
| **REQ-NF-002** | `tests/test_registry.py` | Modify | Verification of `# Usage: <PascalCase>.tool_name` in generated `.pyi` stubs |
| **REQ-NF-003** | Entire repo | Verify | Backward compatibility: existing lowercase `server.tool` calls continue working with zero breaking changes |

---

## 3. Risk Assessment

- **R-001 (Name collision):** Two servers normalizing to the same PascalCase name. Mitigated by registering original names first, logging if collision occurs; underlying configs resolve independently.
- **R-002 (Keyword collision):** Handled by prepending `_` if starting with a digit or if empty string (`_Server`).
- **R-003 (Blast Radius):** Isolated strictly to Code Mode sandbox injection and `.pyi` comment presentation. CLI storage and remote HTTP routes untouched.
