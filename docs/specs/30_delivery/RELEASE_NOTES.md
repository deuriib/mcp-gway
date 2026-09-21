# Release Notes: Test Suite Performance & Zero-Hang Optimization

**Date:** 2026-09-20  
**Release Manager:** orchestrator / operations owner function  
**Specs Included:** `SPEC-TEST-PERF-001` (Test Suite Performance & Zero-Hang Optimization)  
**Domains-Touched:** [engineering, automation]  
**Ship Type:** rollout (CI & test performance optimization)  

---

## Highlights

- **Elimination of SSE Disconnect 300s Hang (`test_ac005_sse_disconnect_counted`)**:
  - Injected scoped monkeypatch of `MAX_IDLE_SECONDS = 0.05` in `tests/test_obsfeat007.py`.
  - The SSE idle generator exits cleanly in 50ms rather than blocking on the 300s default idle timeout. Test duration dropped from ~300.0s to 0.06s.
- **Elimination of 30s Sandbox Teardown Delay**:
  - Bounded stub callback `time.sleep(10)` to 0.8s and 0.5s in `tests/test_sandbox.py` and `tests/test_edgecases_sandbox.py`.
  - Exiting the sandbox `ThreadPoolExecutor(max_workers=1)` context manager no longer blocks thread shutdown for 10s per test. Tests execute in ~0.8s and ~0.5s.
- **DNS Timeout Monkeypatch Alignment**:
  - Aligned monkeypatch in `tests/test_p0_round2_hardening.py` to target `SSRF_DNS_TIMEOUT` (instead of `_SSRF_DNS_TIMEOUT`), dropping execution time from 3.0s to 0.05s.
- **Radical Test Suite Acceleration**:
  - Entire suite of 562 tests runs in **8.98 seconds** (down from > 340 seconds / 5.5 minutes).
  - 100% pass rate (562/562 passed).
  - 100% clean formatting and linting (`ruff`).
  - Zero modifications to runtime production code in `src/mcp_gway/`.

---

## Changes

### Fixes
- `tests/test_obsfeat007.py`: Added `monkeypatch.setattr("mcp_gway.gateway.MAX_IDLE_SECONDS", 0.05)` to `test_ac005_sse_disconnect_counted`.
- `tests/test_sandbox.py`: Bounded stub sleep in `test_execute_slow_callback_raises_timeout` and `test_execute_timeout_error_message_includes_details`.
- `tests/test_edgecases_sandbox.py`: Bounded stub sleep in `test_sandbox_timeout`.
- `tests/test_p0_round2_hardening.py`: Fixed monkeypatch symbol in `test_round2_dns_timeout_fail_closed`.

---

## Rollback / Undo

- Revert commit via `git revert <commit-hash>`.
