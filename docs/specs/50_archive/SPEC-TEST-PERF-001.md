# Spec: Test Suite Performance & Zero-Hang Optimization

**ID:** SPEC-TEST-PERF-001
**Owner:** Engineering domain owner
**Domains-Touched:** [engineering, automation]
**Brief Reference:** BRIEF-TEST-PERF-001
**Status:** approved
**Priority:** P0
**Execution_Mode:** multi-subagents

---

## 1. Context

During test suite verification and continuous integration (CI) profiling for MCP Gateway, the test suite (562 tests) experiences severe multi-minute execution hangs and artificial latency bottlenecks across specific test modules:

1. **`test_ac005_sse_disconnect_counted` in `tests/test_obsfeat007.py` hangs for ~300s (5 minutes):**
   - In `src/mcp_gway/gateway.py`, the SSE stream generator `_mcp_sse` awaits incoming queue messages via `asyncio.wait_for(info.queue.get(), timeout=MAX_IDLE_SECONDS)`.
   - `MAX_IDLE_SECONDS` defaults to `SSRF_IDLE_TIMEOUT` (300 seconds).
   - In `test_ac005_sse_disconnect_counted`, the ASGI `TestClient` exits its `with c.stream("GET", "/mcp")` context manager. Because the HTTP client disconnect does not immediately terminate the background ASGI event-loop generator without active queue activity, the generator remains suspended awaiting the 300s timeout to trigger an idle transition.
   - Consequently, the disconnect counter assertion `gw.metrics.sum("gateway_sse_disconnects_total") >= 1` and disconnect log emission (`reason="idle"`) are blocked for the full 300 seconds, artificially bottlenecking local and CI runners.

2. **Sandbox timeout tests in `tests/test_sandbox.py` and `tests/test_edgecases_sandbox.py` hang 10s each (~30s cumulative):**
   - Tests `test_execute_slow_callback_raises_timeout` and `test_execute_timeout_error_message_includes_details` in `tests/test_sandbox.py`, as well as `test_sandbox_timeout_kills_infinite_loop` in `tests/test_edgecases_sandbox.py`, define stub callback functions containing `time.sleep(10)` to test sandbox timeout triggers (configured at `timeout=0.3` or `timeout=0.5`).
   - Starlark sandbox execution executes Python callables inside a worker thread / `ThreadPoolExecutor`. While the sandbox timeout mechanism correctly aborts execution and raises `ExecutionError` after 0.3s/0.5s, the worker thread executing `time.sleep(10)` continues running in the background.
   - When the executor or test teardown completes, thread synchronization blocks until the worker thread finishes sleeping for the full 10 seconds. With 3 tests sleeping 10 seconds, this adds 30 seconds of wasted execution time.

3. **`test_round2_dns_timeout_fail_closed` in `tests/test_p0_round2_hardening.py` hangs for 3s:**
   - In `src/mcp_gway/models.py`, `_aresolve_host_ips` guards asynchronous DNS resolution using `asyncio.wait_for(..., timeout=SSRF_DNS_TIMEOUT)`.
   - In `models.py`, `SSRF_DNS_TIMEOUT = 3.0`, and an alias `_SSRF_DNS_TIMEOUT = SSRF_DNS_TIMEOUT` is defined.
   - In `test_round2_dns_timeout_fail_closed`, the test executes `monkeypatch.setattr(M, "_SSRF_DNS_TIMEOUT", 0.05)`. However, `_aresolve_host_ips` references the public symbol `SSRF_DNS_TIMEOUT`, leaving the active timeout at 3.0 seconds.
   - As a result, the test blocks for 3.0 seconds waiting for `asyncio.wait_for` to time out on simulated slow DNS resolution.

Resolving these three defects via test-level monkeypatching and bounded callback sleeps eliminates ~333 seconds of test suite hang without any modification to production code in `src/mcp_gway/`.

---

## 2. Requirements

- **REQ-001**: `test_ac005_sse_disconnect_counted` monkeypatches `MAX_IDLE_SECONDS` in `mcp_gway.gateway` to `0.05`s so that the SSE idle disconnect transition triggers and registers in `< 0.2`s, without modifying production code.
- **REQ-002**: Sandbox timeout tests in `tests/test_sandbox.py` (`test_execute_slow_callback_raises_timeout`, `test_execute_timeout_error_message_includes_details`) and `tests/test_edgecases_sandbox.py` (`test_sandbox_timeout_kills_infinite_loop`) reduce stub sleep duration from `10`s to a bounded duration (e.g. `0.8`s) that reliably exceeds the sandbox timeout (`0.3`s/`0.5`s) without blocking `ThreadPoolExecutor` shutdown for 10s.
- **REQ-003**: `test_round2_dns_timeout_fail_closed` in `tests/test_p0_round2_hardening.py` monkeypatches `SSRF_DNS_TIMEOUT` (in `mcp_gway.models`) to `0.05`s instead of the unused `_SSRF_DNS_TIMEOUT`, ensuring fail-closed DNS timeout verification completes in `< 0.2`s.
- **REQ-004**: Overall test suite execution passes 100% (562/562 tests passing) with total suite execution time strictly under 8.0s on standard execution environments.
- **REQ-005**: Zero regression in production code under `src/mcp_gway/` (production runtime logic, default timeouts, and security policies remain 100% unaltered).

---

## 3. Acceptance Criteria

- [ ] **AC-001**: `test_ac005_sse_disconnect_counted` passes in `< 0.2`s, correctly incrementing `gateway_sse_disconnects_total` and logging `"SSE session ended"` with `reason="idle"` via `monkeypatch.setattr(gw_module, "MAX_IDLE_SECONDS", 0.05)`.
- [ ] **AC-002**: Sandbox timeout tests in `tests/test_sandbox.py` and `tests/test_edgecases_sandbox.py` complete in `<= 1.0`s each while verifying that timeouts (`0.3`s and `0.5`s) raise `ExecutionError` with full timeout diagnostics.
- [ ] **AC-003**: `test_round2_dns_timeout_fail_closed` passes in `< 0.2`s, validating that slow DNS resolution fails closed when `SSRF_DNS_TIMEOUT` is monkeypatched to `0.05`s.
- [ ] **AC-004**: Running `uv run pytest` executes all 562 tests with 100% pass rate in total suite wall-clock time under 8.0 seconds.
- [ ] **AC-005**: `git diff src/mcp_gway/` is completely empty; all optimizations are strictly contained within test files and fixtures.

---

## 4. Contracts & Interfaces

### Test Isolation Contract
- Tests requiring reduced timeouts must use pytest's `monkeypatch` fixture.
- Monkeypatching must target the exact module where the symbol is referenced during runtime execution:
  - `mcp_gway.gateway.MAX_IDLE_SECONDS` for SSE idle timeout simulation.
  - `mcp_gway.models.SSRF_DNS_TIMEOUT` for asynchronous DNS resolution timeout simulation.
- Pytest guarantees restoration of monkeypatched attributes upon test completion, preventing state leakage across test cases.

### Bounded Concurrency Sleep Contract
- Threaded stub callbacks intended to provoke timeouts in `sandbox.py` must use a sleep duration $T_{sleep}$ satisfying:
  $$T_{timeout} < T_{sleep} \le T_{timeout} + 0.5\text{s}$$
  For sandbox tests with $T_{timeout} \in \{0.3\text{s}, 0.5\text{s}\}$, $T_{sleep} = 0.8\text{s}$ ensures deterministic timeout triggering while capping thread lifecycle at $800\text{ms}$.

---

## 5. Out of Scope

- Modifying default production constants (`SSRF_IDLE_TIMEOUT = 300`, `SSRF_DNS_TIMEOUT = 3.0`) in `src/mcp_gway/models.py` or `src/mcp_gway/gateway.py`.
- Altering Starlark sandbox timeout enforcement logic or thread pool management in `src/mcp_gway/sandbox.py`.
- Refactoring SSE streaming protocol or Starlette ASGI transport handlers.
- Modifying test assertions, expected exceptions, or test coverage scope.

---

## 6. Dependencies

- `pytest` with `monkeypatch` fixture.
- `starlette.testclient.TestClient` for ASGI HTTP/SSE streaming tests.
- `mcp_gway.gateway.Gateway`, `mcp_gway.sandbox.Sandbox`, `mcp_gway.models`.

---

## 7. Traceability

| Requirement | Acceptance Criterion | Proposed Change | Evidence |
|-------------|---------------------|-----------------|----------|
| REQ-001 | AC-001 | PROPOSED_CHANGES.md | `tests/test_obsfeat007.py::test_ac005_sse_disconnect_counted` |
| REQ-002 | AC-002 | PROPOSED_CHANGES.md | `tests/test_sandbox.py::test_execute_slow_callback_raises_timeout`<br>`tests/test_sandbox.py::test_execute_timeout_error_message_includes_details`<br>`tests/test_edgecases_sandbox.py::test_sandbox_timeout_kills_infinite_loop` |
| REQ-003 | AC-003 | PROPOSED_CHANGES.md | `tests/test_p0_round2_hardening.py::test_round2_dns_timeout_fail_closed` |
| REQ-004 | AC-004 | PROPOSED_CHANGES.md | `uv run pytest` execution report (562 passed in < 8.0s) |
| REQ-005 | AC-005 | PROPOSED_CHANGES.md | `git diff src/mcp_gway/` (zero changes in production) |

Singleton: per lane, create-if-missing else update-in-place, never suffix — one UPPER_SNAKE canonical per type (`SPEC-TEST-PERF-001.md`).
