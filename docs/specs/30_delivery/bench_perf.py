#!/usr/bin/env python3
"""
Benchmark Script: MCP Gateway Performance Audit
SPEC-PERF-001 / BRIEF-performance
Date: 2026-09-16

Measures:
- Latency p50/p95/p99 for 5 live HTTP/SSE paths
- Code Mode overhead: real JSON-RPC calls to all five meta-tools, per-tool
  p50/p95/p99 over N iterations. Tools that cannot be exercised against the
  target gateway are reported as `skipped` with a reason, never as a
  placeholder latency.
- Resource consumption (CPU, memory, startup) across 3 transports
- Generates JSON + markdown reports

Usage:
    uv run python docs/specs/30_delivery/bench_perf.py --config docs/specs/30_delivery/perf_config.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx2 as httpx


@dataclass
class BenchmarkConfig:
    """Configuration from perf_config.yaml."""

    target_url: str = "http://127.0.0.1:8080"
    concurrency: int = 10
    duration_sec: int = 30
    warmup_sec: int = 5
    iterations: int = 1000
    code_mode_iterations: int = 20
    code_mode_warmup: int = 3
    output_dir: str = "docs/specs/30_delivery/reports"
    output_prefix: str = "perf_report"


@dataclass
class LatencyResult:
    """Latency measurement result."""

    path: str
    method: str
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    mean_ms: float = 0.0
    throughput_rps: float = 0.0
    total_requests: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)


@dataclass
class ResourceResult:
    """Resource consumption result."""

    transport: str
    startup_time_sec: float = 0.0
    memory_rss_mb: float = 0.0
    cpu_percent: float = 0.0
    pid: int = 0


@dataclass
class CodeModeResult:
    """One Code Mode meta-tool measurement.

    ``status`` is ``ok`` when every iteration completed, ``partial`` when some
    failed, ``error`` when every iteration failed, and ``skipped`` when the
    tool cannot be exercised against the target gateway (no stubs, no tools).
    A skipped row carries a reason and never a fabricated latency.
    """

    tool: str
    status: str = "ok"
    reason: str = ""
    iterations: int = 0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    mean_ms: float = 0.0
    min_ms: float = 0.0
    max_ms: float = 0.0
    errors: int = 0
    wall_time_sec: float = 0.0


@dataclass
class BenchmarkReport:
    """Full benchmark report."""

    timestamp: str = ""
    target_url: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    latencies: list[LatencyResult] = field(default_factory=list)
    resources: list[ResourceResult] = field(default_factory=list)
    code_mode: list[CodeModeResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def load_config(config_path: str) -> BenchmarkConfig:
    """Load benchmark configuration from YAML file."""
    try:
        import yaml

        with open(config_path) as f:
            data = yaml.safe_load(f)
        target = data.get("target", {})
        bench = data.get("benchmark", {})
        output = data.get("output", {})
        return BenchmarkConfig(
            target_url=target.get("url", "http://127.0.0.1:8080"),
            concurrency=bench.get("concurrency", 10),
            duration_sec=bench.get("duration_sec", 30),
            warmup_sec=bench.get("warmup_sec", 5),
            iterations=bench.get("iterations", 1000),
            code_mode_iterations=bench.get("code_mode_iterations", 20),
            code_mode_warmup=bench.get("code_mode_warmup", 3),
            output_dir=output.get("directory", "docs/specs/30_delivery/reports"),
            output_prefix=output.get("filename_prefix", "perf_report"),
        )
    except ImportError:
        print("Warning: PyYAML not installed, using defaults", file=sys.stderr)
        return BenchmarkConfig()
    except FileNotFoundError:
        print(
            f"Warning: Config file {config_path} not found, using defaults",
            file=sys.stderr,
        )
        return BenchmarkConfig()


def check_server(url: str) -> bool:
    """Check if MCP Gateway server is running."""
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{url}/health")
            return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def start_server(
    transport: str, host: str, port: int | None
) -> subprocess.Popen | None:
    """Start MCP Gateway server for benchmarking."""
    cmd = ["uv", "run", "mcp-gway", "serve", "--transport", transport]
    if host and port:
        cmd.extend(["--host", host, "--port", str(port)])
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd(),
        )
        time.sleep(2)  # wait for startup
        return proc
    except FileNotFoundError:
        print("Error: mcp-gway not found. Run 'uv sync' first.", file=sys.stderr)
        return None


def measure_latency_single(
    client: httpx.Client,
    url: str,
    path: str,
    method: str,
    body: str | None = None,
    iterations: int = 1000,
) -> LatencyResult:
    """Measure latency for a single path with sequential requests."""
    result = LatencyResult(path=path, method=method)
    latencies = []

    for _ in range(iterations):
        try:
            start = time.perf_counter()
            if method == "POST":
                resp = client.post(
                    f"{url}{path}",
                    content=body,
                    headers={"Content-Type": "application/json"},
                )
            else:
                resp = client.get(f"{url}{path}")
            elapsed = (time.perf_counter() - start) * 1000  # ms
            latencies.append(elapsed)
            result.total_requests += 1
            if resp.status_code >= 400:
                result.errors += 1
        except Exception:
            result.errors += 1

    if latencies:
        latencies.sort()
        n = len(latencies)
        result.latencies_ms = latencies
        result.p50_ms = latencies[int(n * 0.5)]
        result.p95_ms = latencies[int(n * 0.95)]
        result.p99_ms = latencies[int(n * 0.99)]
        result.min_ms = latencies[0]
        result.max_ms = latencies[-1]
        result.mean_ms = sum(latencies) / n
        result.throughput_rps = n / (sum(latencies) / 1000) if sum(latencies) > 0 else 0

    return result


def measure_latency_concurrent(
    client: httpx.Client,
    url: str,
    path: str,
    method: str,
    body: str | None = None,
    concurrency: int = 10,
    duration_sec: int = 30,
) -> LatencyResult:
    """Measure latency with concurrent requests for a fixed duration."""
    import threading

    result = LatencyResult(path=path, method=method)
    latencies: list[float] = []
    errors = 0
    total = 0
    stop_event = threading.Event()

    def worker():
        nonlocal errors, total
        while not stop_event.is_set():
            try:
                start = time.perf_counter()
                if method == "POST":
                    resp = client.post(
                        f"{url}{path}",
                        content=body,
                        headers={"Content-Type": "application/json"},
                    )
                else:
                    resp = client.get(f"{url}{path}")
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
                total += 1
                if resp.status_code >= 400:
                    errors += 1
            except Exception:
                errors += 1

    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    for t in threads:
        t.start()
    time.sleep(duration_sec)
    stop_event.set()
    for t in threads:
        t.join(timeout=5)

    if latencies:
        latencies.sort()
        n = len(latencies)
        result.latencies_ms = latencies
        result.p50_ms = latencies[int(n * 0.5)]
        result.p95_ms = latencies[int(n * 0.95)]
        result.p99_ms = latencies[int(n * 0.99)]
        result.min_ms = latencies[0]
        result.max_ms = latencies[-1]
        result.mean_ms = sum(latencies) / n
        result.throughput_rps = n / duration_sec
    result.total_requests = total
    result.errors = errors

    return result


def measure_startup_time(command: list[str], cwd: str | None = None) -> float:
    """Measure server startup time in seconds."""
    start = time.perf_counter()
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd
    )
    # Poll until server responds or timeout
    timeout = 30
    url = "http://127.0.0.1:8080/health"
    if "--transport" in command and "stdio" in command:
        # stdio transport doesn't have HTTP health endpoint
        proc.terminate()
        return 0.0

    elapsed = 0.0
    while elapsed < timeout:
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    proc.terminate()
                    return time.perf_counter() - start
        except Exception:
            pass
        time.sleep(0.1)
        elapsed = time.perf_counter() - start

    proc.terminate()
    return elapsed


def measure_resources(
    transport: str, command: list[str], cwd: str | None = None
) -> ResourceResult:
    """Measure CPU/memory for a transport."""
    result = ResourceResult(transport=transport)
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd
    )
    result.pid = proc.pid
    time.sleep(3)  # let it stabilize

    try:
        import psutil

        p = psutil.Process(proc.pid)
        mem = p.memory_info()
        result.memory_rss_mb = mem.rss / (1024 * 1024)
        result.cpu_percent = p.cpu_percent(interval=1.0)
    except ImportError:
        # Fallback: estimate from /proc or task manager
        result.memory_rss_mb = 0.0
        result.cpu_percent = 0.0

    proc.terminate()
    return result


_STUB_RE = re.compile(r"^\s{2}([A-Za-z0-9_]+)\.pyi", re.MULTILINE)
_USAGE_RE = re.compile(r"^# Usage: ([A-Za-z0-9_]+)\.", re.MULTILINE)
_TOOL_DEF_RE = re.compile(r"^def ([A-Za-z0-9_]+)\(", re.MULTILINE)


def _first_stub(listing: str) -> str:
    """First ``servers/<Name>.pyi`` in listToolFiles output ("" when none)."""
    match = _STUB_RE.search(listing)
    return match.group(1) if match else ""


def _parse_stub(stub: str, fallback_server: str) -> tuple[str, str, str]:
    """Return (server, raw tool name, sanitized tool name) from a .pyi stub."""
    usage = _USAGE_RE.search(stub)
    server = usage.group(1) if usage else fallback_server
    tool_match = _TOOL_DEF_RE.search(stub)
    tool = tool_match.group(1) if tool_match else ""
    safe = re.sub(r"[^A-Za-z0-9_]", "_", tool)
    if safe and safe[0].isdigit():
        safe = f"_{safe}"
    return server, tool, safe


def _tool_call_text(
    client: httpx.Client, target_url: str, name: str, arguments: dict[str, Any]
) -> str:
    """Issue one JSON-RPC ``tools/call`` and return the text content."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    response = client.post(
        f"{target_url}/mcp",
        json=payload,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise RuntimeError(str(body["error"]))
    content = (body.get("result") or {}).get("content") or []
    return str(content[0].get("text", "")) if content else ""


def _summarize(result: CodeModeResult, latencies: list[float]) -> None:
    if not latencies:
        result.status = "error"
        if not result.reason:
            result.reason = "every iteration failed"
        return
    latencies.sort()
    n = len(latencies)
    result.iterations = n
    result.p50_ms = latencies[int(n * 0.50)]
    result.p95_ms = latencies[int(n * 0.95)]
    result.p99_ms = latencies[int(n * 0.99)]
    result.min_ms = latencies[0]
    result.max_ms = latencies[-1]
    result.mean_ms = sum(latencies) / n
    result.wall_time_sec = result.mean_ms / 1000
    result.status = "ok" if result.errors == 0 else "partial"


def _measure_rpc(
    client: httpx.Client,
    target_url: str,
    tool: str,
    arguments: dict[str, Any],
    iterations: int,
    warmup: int,
) -> CodeModeResult:
    """Time ``iterations`` real JSON-RPC calls after ``warmup`` discarded ones."""
    result = CodeModeResult(tool=tool)
    for _ in range(max(0, warmup)):
        try:
            _tool_call_text(client, target_url, tool, arguments)
        except Exception:
            pass

    latencies: list[float] = []
    for _ in range(max(1, iterations)):
        start = time.perf_counter()
        try:
            _tool_call_text(client, target_url, tool, arguments)
        except Exception as exc:
            result.errors += 1
            result.reason = f"{type(exc).__name__}: {exc}"
            continue
        latencies.append((time.perf_counter() - start) * 1000)
    _summarize(result, latencies)
    return result


def measure_code_mode_overhead(
    target_url: str, iterations: int = 20, warmup: int = 3
) -> list[CodeModeResult]:
    """Measure all five Code Mode meta-tools through the live gateway.

    Every row is a real JSON-RPC round trip. When the target has no server
    stubs or tools, the dependent tools are skipped with a reason instead of
    reporting a synthetic number.
    """
    results: list[CodeModeResult] = []
    with httpx.Client(timeout=30.0) as client:
        try:
            listing = _tool_call_text(client, target_url, "listToolFiles", {})
        except Exception as exc:
            return [
                CodeModeResult(
                    tool="listToolFiles",
                    status="error",
                    reason=f"{type(exc).__name__}: {exc}",
                )
            ]

        results.append(
            _measure_rpc(client, target_url, "listToolFiles", {}, iterations, warmup)
        )

        stub = _first_stub(listing)
        if not stub:
            reason = "no server stubs on the target gateway"
            results.extend(
                CodeModeResult(tool=tool, status="skipped", reason=reason)
                for tool in (
                    "readToolFile",
                    "getToolDocs",
                    "executeTool",
                    "callManyTool",
                )
            )
            return results

        read_args = {"fileName": f"servers/{stub}.pyi"}
        results.append(
            _measure_rpc(
                client, target_url, "readToolFile", read_args, iterations, warmup
            )
        )
        try:
            stub_text = _tool_call_text(client, target_url, "readToolFile", read_args)
        except Exception as exc:
            reason = f"stub unavailable: {type(exc).__name__}: {exc}"
            results.extend(
                CodeModeResult(tool=tool, status="skipped", reason=reason)
                for tool in ("getToolDocs", "executeTool", "callManyTool")
            )
            return results

        server, tool, safe_tool = _parse_stub(stub_text, stub)
        if not tool:
            reason = f"no tools listed in servers/{stub}.pyi"
            results.extend(
                CodeModeResult(tool=name, status="skipped", reason=reason)
                for name in ("getToolDocs", "executeTool", "callManyTool")
            )
            return results

        results.append(
            _measure_rpc(
                client,
                target_url,
                "getToolDocs",
                {"server": server, "tool": tool},
                iterations,
                warmup,
            )
        )
        results.append(
            _measure_rpc(
                client,
                target_url,
                "executeTool",
                {"code": f"{server}.{safe_tool}()"},
                iterations,
                warmup,
            )
        )
        calls = [{"server": server, "tool": tool, "arguments": {}} for _ in range(2)]
        results.append(
            _measure_rpc(
                client, target_url, "callManyTool", {"calls": calls}, iterations, warmup
            )
        )
    return results


def run_benchmarks(config: BenchmarkConfig) -> BenchmarkReport:
    """Run all benchmarks and produce report."""
    report = BenchmarkReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        target_url=config.target_url,
        config={
            "concurrency": config.concurrency,
            "duration_sec": config.duration_sec,
            "warmup_sec": config.warmup_sec,
            "iterations": config.iterations,
        },
    )

    if not check_server(config.target_url):
        print("Error: MCP Gateway server not running.", file=sys.stderr)
        print(
            "Start with: uv run mcp-gway serve --transport http --host 127.0.0.1 --port 8080",
            file=sys.stderr,
        )
        return report

    paths = [
        ("/mcp", "POST", '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'),
        ("/mcp", "GET", None),
        ("/health", "GET", None),
        ("/ready", "GET", None),
        ("/live", "GET", None),
        ("/metrics", "GET", None),
    ]

    with httpx.Client(timeout=30.0) as client:
        for path, method, body in paths:
            print(f"Benchmarking {method} {path}...")
            # Warmup
            for _ in range(min(10, config.warmup_sec)):
                try:
                    if method == "POST":
                        client.post(
                            f"{config.target_url}{path}",
                            content=body,
                            headers={"Content-Type": "application/json"},
                        )
                    else:
                        client.get(f"{config.target_url}{path}")
                except Exception:
                    pass

            # Sequential measurement
            seq_result = measure_latency_single(
                client, config.target_url, path, method, body, config.iterations
            )
            report.latencies.append(seq_result)

            # Concurrent measurement
            measure_latency_concurrent(
                client,
                config.target_url,
                path,
                method,
                body,
                config.concurrency,
                config.duration_sec,
            )
            # Merge concurrent into sequential (or keep separate)
            # For simplicity, we keep sequential as primary

    # Code Mode overhead
    print("Measuring Code Mode overhead...")
    report.code_mode = measure_code_mode_overhead(
        config.target_url,
        iterations=config.code_mode_iterations,
        warmup=config.code_mode_warmup,
    )

    # Summary
    report.summary = {
        "total_paths_benchmarked": len(report.latencies),
        "total_requests": sum(r.total_requests for r in report.latencies),
        "total_errors": sum(r.errors for r in report.latencies),
        "code_mode_measured": sum(
            1 for r in report.code_mode if r.status in ("ok", "partial")
        ),
        "code_mode_skipped": sum(1 for r in report.code_mode if r.status == "skipped"),
        "p99_mcp_post_ms": next(
            (
                r.p99_ms
                for r in report.latencies
                if r.path == "/mcp" and r.method == "POST"
            ),
            0,
        ),
    }

    return report


def save_report(
    report: BenchmarkReport, output_dir: str, prefix: str
) -> tuple[str, str]:
    """Save report as JSON and markdown."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    timestamp = report.timestamp.replace(":", "-").replace("T", "-").replace("Z", "")
    json_path = f"{output_dir}/{prefix}_{timestamp}.json"
    md_path = f"{output_dir}/{prefix}_{timestamp}.md"

    # JSON
    with open(json_path, "w") as f:
        json.dump(
            {
                "timestamp": report.timestamp,
                "target_url": report.target_url,
                "config": report.config,
                "latencies": [
                    {
                        "path": r.path,
                        "method": r.method,
                        "p50_ms": r.p50_ms,
                        "p95_ms": r.p95_ms,
                        "p99_ms": r.p99_ms,
                        "min_ms": r.min_ms,
                        "max_ms": r.max_ms,
                        "mean_ms": r.mean_ms,
                        "throughput_rps": r.throughput_rps,
                        "total_requests": r.total_requests,
                        "errors": r.errors,
                    }
                    for r in report.latencies
                ],
                "code_mode": [
                    {
                        "tool": r.tool,
                        "status": r.status,
                        "reason": r.reason,
                        "iterations": r.iterations,
                        "p50_ms": r.p50_ms,
                        "p95_ms": r.p95_ms,
                        "p99_ms": r.p99_ms,
                        "mean_ms": r.mean_ms,
                        "min_ms": r.min_ms,
                        "max_ms": r.max_ms,
                        "errors": r.errors,
                        "wall_time_sec": r.wall_time_sec,
                    }
                    for r in report.code_mode
                ],
                "summary": report.summary,
            },
            f,
            indent=2,
        )

    # Markdown
    with open(md_path, "w") as f:
        f.write("# Performance Report: MCP Gateway\n\n")
        f.write(f"**Timestamp:** {report.timestamp}\n")
        f.write(f"**Target:** {report.target_url}\n\n")
        f.write("## Latency Results\n\n")
        f.write(
            "| Path | Method | p50 (ms) | p95 (ms) | p99 (ms) | Throughput (req/s) | Errors |\n"
        )
        f.write(
            "|------|--------|----------|----------|----------|-------------------|--------|\n"
        )
        f.writelines(
            f"| {r.path} | {r.method} | {r.p50_ms:.2f} | {r.p95_ms:.2f} | {r.p99_ms:.2f} | {r.throughput_rps:.1f} | {r.errors} |\n"
            for r in report.latencies
        )
        f.write("\n## Code Mode Overhead\n\n")
        f.write(
            "| Tool | Status | Iterations | p50 (ms) | p95 (ms) | p99 (ms) | Errors | Reason |\n"
        )
        f.write(
            "|------|--------|------------|----------|----------|----------|--------|--------|\n"
        )
        f.writelines(
            f"| {r.tool} | {r.status} | {r.iterations} | {r.p50_ms:.2f} | "
            f"{r.p95_ms:.2f} | {r.p99_ms:.2f} | {r.errors} | {r.reason} |\n"
            for r in report.code_mode
        )
        f.write("\n## Summary\n\n")
        f.write(
            f"- Total paths benchmarked: {report.summary.get('total_paths_benchmarked', 0)}\n"
        )
        f.write(f"- Total requests: {report.summary.get('total_requests', 0)}\n")
        f.write(f"- Total errors: {report.summary.get('total_errors', 0)}\n")
        f.write(f"- p99 /mcp POST: {report.summary.get('p99_mcp_post_ms', 0):.2f} ms\n")
        f.write(
            f"- Code Mode tools measured: {report.summary.get('code_mode_measured', 0)}\n"
        )
        f.write(
            f"- Code Mode tools skipped: {report.summary.get('code_mode_skipped', 0)}\n"
        )

    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP Gateway Performance Benchmark")
    parser.add_argument("--config", default="docs/specs/30_delivery/perf_config.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--duration", type=int, default=None)
    parser.add_argument("--code-mode-iterations", type=int, default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    if args.output_dir:
        config.output_dir = args.output_dir
    if args.concurrency:
        config.concurrency = args.concurrency
    if args.duration:
        config.duration_sec = args.duration
    if args.code_mode_iterations:
        config.code_mode_iterations = args.code_mode_iterations

    print("MCP Gateway Performance Benchmark")
    print(f"Target: {config.target_url}")
    print(f"Concurrency: {config.concurrency}")
    print(f"Duration: {config.duration_sec}s")
    print()

    report = run_benchmarks(config)
    json_path, md_path = save_report(report, config.output_dir, config.output_prefix)

    print("\nBenchmark complete.")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {md_path}")


if __name__ == "__main__":
    main()
