# Test / Evidence Matrix: SPEC-TEST-PERF-001

**Agent:** Engineering Specialist
**Date:** 2026-09-20
**Domains-Touched:** [engineering, automation]

| REQ-ID | Evidence ID | Description | Type | Status | Duration | Commit |
|--------|-------------|-------------|------|--------|----------|--------|
| REQ-001 | T-PERF-001 | `tests/test_obsfeat007.py::test_ac005_sse_disconnect_counted` monkeypatches `MAX_IDLE_SECONDS` to 0.05s, verifying idle disconnect transition in < 0.2s | Unit | pass | 0.06s call | `71baee7` |
| REQ-002 | T-PERF-002 | `tests/test_sandbox.py::test_execute_slow_callback_raises_timeout` (0.8s sleep vs 0.5s timeout) verifies timeout raises `SandboxTimeoutError` without 10s wait | Unit | pass | 0.80s call | `04545e8` |
| REQ-002 | T-PERF-003 | `tests/test_sandbox.py::test_execute_timeout_error_message_includes_details` (0.8s sleep vs 0.3s timeout) verifies timeout error details without 10s wait | Unit | pass | 0.80s call | `04545e8` |
| REQ-002 | T-PERF-004 | `tests/test_edgecases_sandbox.py::test_sandbox_timeout` (0.5s sleep vs 0.2s timeout) verifies timeout raises without 10s wait | Unit | pass | 0.50s call | `04545e8` |
| REQ-003 | T-PERF-005 | `tests/test_p0_round2_hardening.py::test_round2_dns_timeout_fail_closed` monkeypatches `SSRF_DNS_TIMEOUT` to 0.05s, verifying fail-closed DNS timeout in < 0.2s | Unit | pass | 0.05s call | `d56844a` |
| REQ-004 | T-PERF-006 | Full test suite execution: all 562 tests passing with zero failures and total suite runtime under 8.0s (7.87s on `pytest -q`) | Integration | pass | 7.87s suite | `86b3faf` |
| REQ-005 | E-PERF-007 | Production code zero drift check: `git diff HEAD~3 src/mcp_gway/` returns 0 modified files | Review | pass | N/A | `86b3faf` |

Types: `Unit | Integration | E2E | Review | Sign-off | Attestation | Launch-check | Filing-proof`. Code REQs use tests; non-code REQs use review/sign-off/attestation with artifact path — REQ-ID trace mandatory for all 8 domains. See `references/testing-template.md` for standard directory paths, coverage thresholds, and Frame→Ship methodology fit.

## Detailed Test Timings (Before vs After)

| Test / Metric | Pre-Optimization Baseline | Post-Optimization Result | Improvement |
|---|---|---|---|
| `test_ac005_sse_disconnect_counted` | ~300.0s (hang awaiting idle timeout) | 0.06s call (0.24s total test) | **99.9% faster (-299.9s)** |
| `test_execute_slow_callback_raises_timeout` | 10.0s (thread sleep) | 0.80s call | **92.0% faster (-9.2s)** |
| `test_execute_timeout_error_message_includes_details` | 10.0s (thread sleep) | 0.80s call | **92.0% faster (-9.2s)** |
| `test_sandbox_timeout` | 10.0s (thread sleep) | 0.50s call | **95.0% faster (-9.5s)** |
| `test_round2_dns_timeout_fail_closed` | 3.0s (production DNS timeout wait) | 0.05s call | **98.3% faster (-2.95s)** |
| **Total Test Suite (562 tests)** | **~340.0s (> 5.5 min)** | **7.87s** | **~97.7% reduction (-332.1s)** |

## Quality Gate Verification

- **Lint (`uv run ruff check src/ tests/`):** PASS (All checks passed!)
- **Format (`uv run ruff format --check src/ tests/`):** PASS (73 files already formatted)
- **Suite Pass Rate:** 562 / 562 tests passed (100%)
- **Production Drift Check (`git diff HEAD~3 src/mcp_gway/`):** PASS (0 files modified under `src/mcp_gway/`)

## Coverage Summary

- Unit coverage: 100% of targeted timeout/SSE/DNS test branches verified
- Integration coverage: 100% (full suite 562/562 passed)
- Evidence coverage: 5/5 REQ-IDs with verified test execution traces and diff checks
- Acceptance criteria covered: 5/5 (AC-001, AC-002, AC-003, AC-004, AC-005)
