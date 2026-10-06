# Observability — Logs, Metrics, Health

Built-in observability with zero vendor lock-in. Key features:
- **Structured JSON logs:** Standard library `json` (no `structlog` dependency). Sensitive values are masked with `***`.
- **Vendored metrics:** Self-contained `MetricsRegistry` (no `prometheus_client` dependency). Exposes Prometheus-compatible text at `/metrics`.
- **Health probes:** `/health`, `/ready`, and `/live` for liveness/readiness checks.
- **Request correlation:** `X-Request-ID` (or `X-Correlation-ID`) echoed on responses and included in logs; auto-generated if absent.
- **Local-first gating:** `/metrics` never leaks secrets. When exposed on non-loopback, appropriate warnings and guards apply; serving on non-loopback without `MCP_GWAY_ALLOW_REMOTE=1` exits with code 2.

**Health & Metrics:**

```bash
curl -s http://127.0.0.1:8080/health | jq
# {"status":"ok","version":"4.5.6","checks":{"registry":"ok","routes":"ok"},"uptime_seconds":42}
curl -s http://127.0.0.1:8080/ready | jq   # 200 ready / 503 not_ready (registry/routes/event_loop checks)
curl -s http://127.0.0.1:8080/live | jq    # 200 alive — no FS I/O, <5ms
curl -s http://127.0.0.1:8080/metrics | head -n 20
# # HELP mcp_gway_http_requests_total Total HTTP requests
# # TYPE mcp_gway_http_requests_total counter
# mcp_gway_http_requests_total{method="GET",path="/health",status="200"} 7
```

**Correlation & JSON logs:**

```bash
curl -s -H "X-Request-ID: demo123" http://127.0.0.1:8080/health -D - | grep -i X-Request-ID
# X-Request-ID: demo123  ← echo on every response; json log line also has "request_id":"demo123"
uv run mcp-gway serve --transport http --port 8080 2>&1 | head   # each line valid JSON: timestamp, level, logger, message, request_id, method, path, status, duration_ms
```

- `X-Request-ID` or `X-Correlation-ID` accepted, sanitized to `^[A-Za-z0-9_-]{1,64}$`, truncated; auto `uuid4` if absent.
- Labels bounded: `path` collapsed to `/mcp` or `/mcp/messages` (SSE alias to the same `_mcp_post` handler, not a separate endpoint; all other routes recorded as-is), server sanitized `[^A-Za-z0-9_]`→`_` 32 chars.
- Metrics: `http_requests_total`, `http_request_duration_seconds` (buckets 0.005..5), `mcp_tool_calls_total{server,tool,status}`, `discovery_duration_seconds`, `sandbox_execute_total{status}`, `registry_operations_total{op}`, `gateway_sessions_active`.

**FEAT-007 hardening (v2.2.1):** process/build lifecycle, stdio coverage, upstream telemetry, cardinality cap.

- Lifecycle: `build_info{version}`, `process_start_time_seconds`, `uptime_seconds` (heartbeat, 30s tick), `lifetime_seconds` (set at shutdown) + a JSON `gateway shutdown summary` (uptime + totals) on exit.
- stdio (`serve --transport stdio`, default): per-request `stdio_requests_total{method,status}` + `stdio_request_duration_seconds{method}` and a JSON access log (`transport:"stdio"`, same shape as HTTP).
- Upstream CodeMode calls (tool execution): `upstream_tool_calls_total{server,tool,status}` (`ok`/`timeout`/`error`), `upstream_tool_duration_seconds{server,tool}`; opt-in retries counted in `upstream_retries_total{server}`.
- Corruption visibility: `code_mode_servers_skipped_total{reason}` + structured WARN + degraded banner hint (`mcp-gway refresh <name>`) when a server fails injection at startup.
- Label cardinality hard-capped per metric (`_MAX_LABEL_COMBOS=200`); overflow coalesces into a reserved `_other` series so a label storm cannot grow memory without bound.
- Slow-request WARN: requests over `_SLOW_REQUEST_THRESHOLD_MS` (1000) additionally log a `slow request` JSON line with duration.
- CLI structured outcomes: `cli <action> <status>` JSON events — WARNING always emitted, INFO only when `MCP_GWAY_LOG_LEVEL` is set (zero operator noise by default).
- New opt-in flag: `mcp-gway add --retry-on-transport-error` — retries exactly once ONLY when the transport/connect phase fails (never after the tool call starts; non-idempotency-safe, ADR-012 decision 9). Default off → zero behavior change.

**Local-first gating:** `/metrics` never leaks secrets; `serve` on non-loopback without `MCP_GWAY_ALLOW_REMOTE=1` exits 2; `X-Warning: exposed` only on `GET /metrics` → `403` (src/mcp_gway/observability/health.py:127-139).
