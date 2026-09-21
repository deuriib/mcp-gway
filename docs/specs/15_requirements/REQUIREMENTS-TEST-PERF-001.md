# Requirements Index: Test Suite Performance & Zero-Hang Optimization

**Owner:** Engineering domain owner  
**Brief Reference:** BRIEF-TEST-PERF-001  
**Domains-Touched:** [engineering, automation]  

## Functional Requirements

| ID | Requirement | Priority | Source | Spec | Domain | Evidence Type |
|----|-------------|----------|--------|------|--------|---------------|
| REQ-F-001 | `test_ac005_sse_disconnect_counted` monkeypatches `MAX_IDLE_SECONDS` to 0.05s so idle transition happens in < 0.2s without changing production code | P0 | BRIEF-TEST-PERF-001 | SPEC-TEST-PERF-001 | engineering | test (`tests/test_obsfeat007.py`) |
| REQ-F-002 | Sandbox timeout tests in `tests/test_sandbox.py` and `tests/test_edgecases_sandbox.py` reduce stub sleep to bounded time (0.8s) exceeding timeout (0.3s/0.5s) without blocking `ThreadPoolExecutor` shutdown for 10s | P0 | BRIEF-TEST-PERF-001 | SPEC-TEST-PERF-001 | engineering | test (`tests/test_sandbox.py`, `tests/test_edgecases_sandbox.py`) |
| REQ-F-003 | `test_round2_dns_timeout_fail_closed` monkeypatches `SSRF_DNS_TIMEOUT` (in `models.py`) to 0.05s instead of unused `_SSRF_DNS_TIMEOUT` | P0 | BRIEF-TEST-PERF-001 | SPEC-TEST-PERF-001 | engineering | test (`tests/test_p0_round2_hardening.py`) |

## Non-Functional Requirements

| ID | Requirement | Category | Target |
|----|-------------|----------|--------|
| REQ-NF-001 | Overall test suite execution passes 100% (562/562) with total suite time strictly under 8.0s | Performance / CI Budget | Wall-clock time < 8.0s for 562 tests |
| REQ-NF-002 | Zero regression in production code under `src/mcp_gway/` | Reliability / Zero Prod Impact | `git diff src/mcp_gway/` is empty (0 lines changed) |
| REQ-NF-003 | Test isolation guarantees zero side effects or state leaks across test boundaries via pytest `monkeypatch` fixtures | Test Isolation / Reliability | Automatic cleanup upon test exit; no shared mutable state leakage |

## Domain Controls (only touched domains)

| Domain | Control | Owner |
|--------|---------|-------|
| engineering | Test fixture isolation via `monkeypatch`, precise module target attribution (`mcp_gway.gateway.MAX_IDLE_SECONDS`, `mcp_gway.models.SSRF_DNS_TIMEOUT`), and bounded stub concurrency lifetimes | Engineering domain owner |
| automation/ops | Zero-hang CI execution guard, suite duration budget gating (< 8.0s), 100% pass verification on 562 tests | Automation owner + Engineering domain owner |
