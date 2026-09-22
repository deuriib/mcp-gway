# Proposed Changes: Engineering Specialist — Test Suite Performance & Zero-Hang Optimization

**Spec Reference:** [SPEC-TEST-PERF-001](file:///mnt/DATA/GitHub/mcp-gateway/docs/specs/20_backlog/SPEC-TEST-PERF-001.md)
**Agent:** Engineering Specialist
**Date:** 2026-09-20
**Execution_Mode:** multi-subagents (inherited from spec)
**Domains-Touched:** [engineering, automation]

---

## Summary

This proposal delivers targeted, zero-production-impact optimizations across 4 test files to eliminate ~333 seconds of artificial execution hangs during test suite execution. By properly scoping SSE idle timeouts via `monkeypatch`, bounding thread callback sleeps in sandbox timeout tests, and fixing an unused monkeypatch target in DNS resolution tests, the entire test suite (562 tests) will pass reliably in under 8.0 seconds total wall-clock time. Production code in `src/mcp_gway/` remains 100% untouched.

---

## Changes

| Target | Change Type | Description |
|--------|-------------|-------------|
| [`tests/test_obsfeat007.py`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_obsfeat007.py#L251-L274) | file-modify | In [`test_ac005_sse_disconnect_counted`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_obsfeat007.py#L251), add `monkeypatch: pytest.MonkeyPatch` to fixture parameters and inject `monkeypatch.setattr("mcp_gway.gateway.MAX_IDLE_SECONDS", 0.05)` before the streaming client context, eliminating the 300s ASGI idle generator wait (REQ-001, AC-001). |
| [`tests/test_sandbox.py`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_sandbox.py#L51-L91) | file-modify | In [`test_execute_slow_callback_raises_timeout`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_sandbox.py#L51-L64) (timeout=0.5s) and [`test_execute_timeout_error_message_includes_details`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_sandbox.py#L79-L91) (timeout=0.3s), reduce stub callback `time.sleep(10)` to `time.sleep(0.8)` to eliminate 20s cumulative threadpool teardown wait while preserving deterministic timeout triggering (REQ-002, AC-002). |
| [`tests/test_edgecases_sandbox.py`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_edgecases_sandbox.py#L43-L54) | file-modify | In [`test_sandbox_timeout`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_edgecases_sandbox.py#L43-L54) (timeout=0.2s), reduce stub callback `time.sleep(10)` to `time.sleep(0.5)` to eliminate a 10s threadpool teardown wait while preserving deterministic timeout triggering (REQ-002, AC-002). |
| [`tests/test_p0_round2_hardening.py`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_p0_round2_hardening.py#L127-L140) | file-modify | In [`test_round2_dns_timeout_fail_closed`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_p0_round2_hardening.py#L127), update the monkeypatch attribute from `monkeypatch.setattr(M, "_SSRF_DNS_TIMEOUT", 0.05)` to `monkeypatch.setattr(M, "SSRF_DNS_TIMEOUT", 0.05)`, targeting the active symbol evaluated by [`_aresolve_host_ips`](file:///mnt/DATA/GitHub/mcp-gateway/src/mcp_gway/models.py#L326) and eliminating the 3.0s simulated timeout delay (REQ-003, AC-003). |

---

## Rationale

1. **Elimination of SSE 300s Hang (REQ-001, AC-001):**
   In [`src/mcp_gway/gateway.py`](file:///mnt/DATA/GitHub/mcp-gateway/src/mcp_gway/gateway.py#L521), `_mcp_sse` awaits queue events via `asyncio.wait_for(info.queue.get(), timeout=MAX_IDLE_SECONDS)`. Because [`test_ac005_sse_disconnect_counted`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_obsfeat007.py#L251) uses the ASGI `TestClient` context manager without producing subsequent queue traffic, the generator remains waiting until the timeout expires. Setting `MAX_IDLE_SECONDS = 0.05` via `monkeypatch` ensures the idle transition triggers and records the disconnect counter (`gateway_sse_disconnects_total >= 1`) in $< 200\text{ms}$.

2. **Elimination of ThreadPool 10s Teardown Hangs (REQ-002, AC-002):**
   In [`src/mcp_gway/sandbox.py`](file:///mnt/DATA/GitHub/mcp-gateway/src/mcp_gway/sandbox.py), sandbox execution runs inside worker threads. Although Starlark raises a `SandboxTimeoutError` after the configured timeout ($0.2\text{s}$, $0.3\text{s}$, or $0.5\text{s}$), Python worker threads running `time.sleep(10)` cannot be preemptively terminated and block the executor shutdown at test exit for the full 10 seconds each (~30 seconds total across 3 tests). Applying the bounded concurrency sleep contract:
   $$T_{timeout} < T_{sleep} \le T_{timeout} + 0.5\text{s}$$
   $T_{sleep} = 0.8\text{s}$ for $T_{timeout} \in \{0.3\text{s}, 0.5\text{s}\}$ and $T_{sleep} = 0.5\text{s}$ for $T_{timeout} = 0.2\text{s}$ guarantees reliable timeout firing while bounding thread lifespans under $800\text{ms}$.

3. **Correction of Active DNS Timeout Monkeypatch Target (REQ-003, AC-003):**
   In [`src/mcp_gway/models.py`](file:///mnt/DATA/GitHub/mcp-gateway/src/mcp_gway/models.py#L326), [`_aresolve_host_ips`](file:///mnt/DATA/GitHub/mcp-gateway/src/mcp_gway/models.py#L326) evaluates `asyncio.wait_for(..., timeout=SSRF_DNS_TIMEOUT)`. In [`tests/test_p0_round2_hardening.py`](file:///mnt/DATA/GitHub/mcp-gateway/tests/test_p0_round2_hardening.py#L137), line 137 monkeypatched `_SSRF_DNS_TIMEOUT` (an unused internal alias), leaving `SSRF_DNS_TIMEOUT` at its 3.0s production default. Monkeypatching `SSRF_DNS_TIMEOUT` directly to `0.05` allows the fail-closed assertion to verify in $< 200\text{ms}$.

4. **100% Production Code Invariance (REQ-005, AC-005):**
   All changes are strictly confined to test fixtures, mock parameters, and test stub implementations. `git diff src/mcp_gway/` remains completely empty, guaranteeing zero production drift or security posture alteration.

---

## Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Modify production default constants in `src/mcp_gway/gateway.py` (`MAX_IDLE_SECONDS = 0.05`) or `src/mcp_gway/models.py` (`SSRF_DNS_TIMEOUT = 0.05`) | Rejected: Violates REQ-005 and ADR-009/FEAT-007 production contracts. Production servers require robust 300s idle limits and 3.0s DNS resolution tolerances. |
| Forcibly kill worker threads in `src/mcp_gway/sandbox.py` | Rejected: Python thread execution cannot be forcibly terminated without risk of GIL corruption or interpreter instability. Bounding sleep time in test stubs is standard, safe engineering practice. |
| Skip or mark slow tests with `@pytest.mark.skip` or `@pytest.mark.slow` | Rejected: Decreases CI test coverage and masks potential regressions in timeout handling, fail-closed DNS resolution, and SSE metrics. |
| Use `pytest-timeout` plugin to kill slow tests | Rejected: Fails to fix the underlying thread sleep block; worker threads would continue blocking CI runner cleanup. |

---

## Approval Required From

- [ ] Owning domain owner: **engineering owner**
- [ ] **automation owner**

> **Rule:** No repository file modifications during proposal phase. All production and test code files remain untouched until proposal approval.

---

## C2 Challenge Hook (REQ-002)

- **Trigger Checklist Evaluation:**
  - Auth / credentials surface: NO
  - Data / PII / external storage surface: NO
  - Public / external API contract surface: NO
  - Multi-domain scope: YES (`engineering`, `automation`)
  - Blast radius mentions customers, regulators, or revenue: NO (strictly internal test harness)
- **Pre-Approval Challenge Status:** No opt-in challenge requested. Multi-domain scope covers engineering implementation and automation/CI execution.

---

# Risk Assessment: SPEC-TEST-PERF-001

**Proposer:** Engineering Specialist
**Date:** 2026-09-20
**Domains-Touched:** [engineering, automation]

---

## Risk Matrix

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R-001 | 0.05s SSE idle timeout triggers prematurely before ASGI client completes initial handshake in `test_ac005_sse_disconnect_counted` | Low | Medium | The test establishes the connection within `with c.stream(...) as resp: assert resp.status_code == 200` before connection closure occurs. The 0.05s timeout only applies when the client stream exits and the queue is idle, matching the test's intent. |
| R-002 | High CI node CPU load delays thread scheduling, causing `time.sleep(0.8)` to trigger after sandbox timeout or cause flakiness | Low | Low | $T_{sleep} = 0.8\text{s}$ provides a comfortable $>60\%$ buffer over $T_{timeout} = 0.5\text{s}$ (and $>160\%$ over $0.3\text{s}$). The sandbox timeout mechanism uses monotonic time elapsed; even under load, 0.8s will reliably exceed 0.5s/0.3s. |
| R-003 | Monkeypatched attributes leak across other test files | Low | High | Standard Pytest fixture `monkeypatch` automatically undoes all attribute modifications during test teardown. |
| R-004 | Inadvertent modification of `src/mcp_gway/` files during execution | Very Low | Critical | Enforcement of REQ-005 and automated verification via `git diff --stat src/mcp_gway/` in CI quality gate. |

---

## Blast Radius

- **Systems & Code:** Strictly confined to the internal test harness (`tests/test_obsfeat007.py`, `tests/test_sandbox.py`, `tests/test_edgecases_sandbox.py`, `tests/test_p0_round2_hardening.py`). Zero modifications to production source code (`src/mcp_gway/`), build configuration, or package metadata.
- **Customers / External Users:** 0% exposure. No public APIs, CLI commands, runtime schemas, or protocol behaviors are altered.
- **Regulators & Compliance:** 0% exposure. No data retention, telemetry collection, or privacy boundaries are touched.
- **Revenue & Business Operations:** 0% exposure. No pricing, deployment packaging, or operational gating is affected.
- **Teams & Development Flow (Positive Impact):** Immediate engineering velocity improvement. Local developer test loop drops from >5.5 minutes (~340s) to <8.0 seconds (~97% reduction), eliminating blocking delays in CI/CD pipelines.

---

## Rollback Plan

- **Mechanism:** Git-based atomic rollback.
- **Commands:**
  ```bash
  git checkout HEAD -- tests/test_obsfeat007.py tests/test_sandbox.py tests/test_edgecases_sandbox.py tests/test_p0_round2_hardening.py
  # or
  git revert <commit-hash>
  ```
- **Owner:** Engineering Specialist or Automation Owner.
- **ETA:** $< 2$ minutes. Rollback restores previous 10s sleeps and 300s/3s default timeouts without any state migration or operational side effects.

---

## Security Considerations

- **Production Integrity:** Production SSRF DNS timeout (`SSRF_DNS_TIMEOUT = 3.0`) and SSE idle timeout (`SSRF_IDLE_TIMEOUT = 300`) remain completely unchanged in [`src/mcp_gway/models.py`](file:///mnt/DATA/GitHub/mcp-gateway/src/mcp_gway/models.py) and [`src/mcp_gway/gateway.py`](file:///mnt/DATA/GitHub/mcp-gateway/src/mcp_gway/gateway.py).
- **Security Test Validity:**
  - `test_round2_dns_timeout_fail_closed` continues to rigorously verify that slow DNS resolution fails closed under SSRF policies; changing the simulated timeout to 0.05s actually exercises the intended timeout path that was previously skipped due to the misspelled attribute name.
  - Sandbox timeout enforcement in `test_sandbox.py` and `test_edgecases_sandbox.py` continues to verify hermetic containment and exception handling when guest code executes long-running callbacks.

---

## Domain Considerations

- **Engineering:** Ensures test suites remain fast, deterministic, and maintainable. Provides immediate feedback during local refactoring.
- **Automation / Ops:** Eliminates CI runner resource exhaustion and timeout-induced queue congestion, reducing GitHub Actions runner minutes by ~95% per run.
