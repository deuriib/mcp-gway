# Readability Review: SPEC-TEST-PERF-001

**Reviewer:** review-readability
**Date:** 2026-09-20
**Domain:** engineering
**Verdict:** pass
**Findings:** 0

## Summary
The changes are clean, idiomatic Python and pytest fixtures:
1. `tests/test_obsfeat007.py`: Clear addition of `monkeypatch: pytest.MonkeyPatch` and `monkeypatch.setattr("mcp_gway.gateway.MAX_IDLE_SECONDS", 0.05)` with informative inline comments explaining the rationale.
2. `tests/test_sandbox.py` and `tests/test_edgecases_sandbox.py`: Reduction of dummy `time.sleep(10)` to bounded values (0.8s and 0.5s) that unambiguously exceed sandbox timeouts (0.3s, 0.5s, 0.2s) without obfuscating intent.
3. `tests/test_p0_round2_hardening.py`: Correction of monkeypatch attribute name from `_SSRF_DNS_TIMEOUT` to `SSRF_DNS_TIMEOUT`.

Naming conventions, type annotations, and ruff format compliance are fully satisfied.
