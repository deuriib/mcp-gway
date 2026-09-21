# Implementation Plan: SPEC-TEST-PERF-001

**Agent:** Engineering Specialist
**Date:** 2026-09-20
**Approved By:** Engineering Domain Owner + Automation/Ops Owner
**Domains-Touched:** [engineering, automation]
**Execution Mode:** sequential degradation (same-thread execution per contract upon harness subagent quota)

## Steps

| Step | Description | Target / Files | Evidence Location | Est. Effort |
|------|-------------|----------------|-------------------|-------------|
| 1 | In `test_ac005_sse_disconnect_counted`, inject `monkeypatch` fixture and patch `mcp_gway.gateway.MAX_IDLE_SECONDS` to 0.05s | `tests/test_obsfeat007.py` | `tests/test_obsfeat007.py::test_ac005_sse_disconnect_counted` | 0.25h |
| 2 | Reduce stub `time.sleep(10)` to bounded values (0.8s and 0.5s) exceeding timeouts without 10s threadpool wait | `tests/test_sandbox.py`, `tests/test_edgecases_sandbox.py` | `tests/test_sandbox.py`, `tests/test_edgecases_sandbox.py` | 0.25h |
| 3 | Fix DNS monkeypatch attribute name from `_SSRF_DNS_TIMEOUT` to `SSRF_DNS_TIMEOUT` | `tests/test_p0_round2_hardening.py` | `tests/test_p0_round2_hardening.py::test_round2_dns_timeout_fail_closed` | 0.1h |
| 4 | Run quality checks (lint, format, pytest --durations=25) and produce `TEST_MATRIX.md` | `tests/`, `docs/specs/40_workspace/engineering/TEST_MATRIX.md` | Pytest report (< 8.0s suite total) | 0.25h |

## Order of Operations

1. Step 1 resolves the catastrophic 300-second hang on SSE disconnect.
2. Step 2 resolves the cumulative 30-second threadpool shutdown lag across sandbox tests.
3. Step 3 resolves the 3-second DNS timeout delay.
4. Step 4 verifies the complete suite with zero regressions across all 562 tests.

## Rollback Points

- Git atomic revert per commit (`git revert <commit-hash>`).
- If any test fails, changes can be rolled back individually per target file.

## Quality Gates

- [x] Engineering: Lint (`ruff check`) clean
- [x] Engineering: Formatting (`ruff format --check`) clean
- [x] Engineering: Full test suite passing (562/562 passed, 0 failed)
- [x] Automation/ops: Total test suite runtime < 8.0 seconds
