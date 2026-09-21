# Implementation Plan: SPEC-TEST-PERF-001

**Agent:** Engineering Specialist  
**Date:** 2026-09-20  
**Approved By:** Engineering Domain Owner, Automation Domain Owner  
**Domains-Touched:** [engineering, automation]  

## Steps

| Step | Description | Target / Files | Evidence Location | Est. Effort |
|------|-------------|----------------|-------------------|-------------|
| 1 | Optimize SSE disconnect test by monkeypatching `MAX_IDLE_SECONDS` to 0.05s (REQ-001) | `tests/test_obsfeat007.py` | `tests/test_obsfeat007.py::test_ac005_sse_disconnect_counted` | 0.25h |
| 2 | Reduce sandbox timeout stub sleeps from 10s to 0.8s and 0.5s (REQ-002) | `tests/test_sandbox.py`, `tests/test_edgecases_sandbox.py` | `tests/test_sandbox.py::test_execute_slow_callback_raises_timeout`<br>`tests/test_sandbox.py::test_execute_timeout_error_message_includes_details`<br>`tests/test_edgecases_sandbox.py::test_sandbox_timeout` | 0.25h |
| 3 | Fix DNS timeout monkeypatch target to `SSRF_DNS_TIMEOUT` (REQ-003) | `tests/test_p0_round2_hardening.py` | `tests/test_p0_round2_hardening.py::test_round2_dns_timeout_fail_closed` | 0.25h |
| 4 | Verify full test suite (562 tests in < 8.0s), ruff lint/format, and record evidence matrix (REQ-004, REQ-005) | `docs/specs/40_workspace/engineering/TEST_MATRIX.md` | `uv run pytest --durations=25`, `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/` | 0.25h |

Each step maps to one commit per execute-spec task and REQ-ID.

## Order of Operations

1. Step 1 resolves the largest single hang (~300s in SSE idle timeout wait) in `tests/test_obsfeat007.py`.
2. Step 2 resolves the cumulative 30s ThreadPool teardown hang across sandbox timeout tests in `tests/test_sandbox.py` and `tests/test_edgecases_sandbox.py`.
3. Step 3 resolves the 3.0s delay in `tests/test_p0_round2_hardening.py` by targeting the active `SSRF_DNS_TIMEOUT` symbol.
4. Step 4 runs full quality checks (ruff linter and formatter, complete pytest suite of 562 tests, wall-clock timing validation < 8.0s, and git diff verification ensuring zero changes to `src/mcp_gway/`). Produces `TEST_MATRIX.md`.

Dependencies: Steps 1, 2, and 3 are independent test optimizations that together achieve the overall < 8.0s performance gate required by Step 4 (REQ-004).

## Rollback Points

- After Step 1: Revert `tests/test_obsfeat007.py` (`git checkout HEAD -- tests/test_obsfeat007.py`).
- After Step 2: Revert sandbox test files (`git checkout HEAD -- tests/test_sandbox.py tests/test_edgecases_sandbox.py`).
- After Step 3: Revert DNS timeout test (`git checkout HEAD -- tests/test_p0_round2_hardening.py`).
- Complete rollback: `git checkout HEAD -- tests/` cleanly restores previous test state without affecting production code.

## Quality Gates

- [x] Engineering: Lint (`uv run ruff check src/ tests/`), Format check (`uv run ruff format --check src/ tests/`), Tests (`uv run pytest` passing 562/562 in < 8.0s), Security (0 production changes in `src/mcp_gway/`).
- [x] Automation/ops: CI test execution duration optimization validated, zero hang on CI runners.
