"""Bench script: Code Mode rows must be real measurements, never placeholders."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "specs"
    / "30_delivery"
    / "bench_perf.py"
)


def _load_bench() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bench_perf", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves ``cls.__module__`` through sys.modules during exec.
    sys.modules["bench_perf"] = module
    spec.loader.exec_module(module)
    return module


def test_first_stub_and_parse_stub() -> None:
    bench = _load_bench()

    listing = "servers/\n  Demo.pyi  # demo server\n  Other.pyi"
    assert bench._first_stub(listing) == "Demo"
    assert bench._first_stub("No servers connected.") == ""

    stub = (
        "# servers/Demo.pyi\n"
        "# Usage: Demo.echo(param=value)\n"
        'def echo(text: str = "hi") -> str: ...\n'
    )
    assert bench._parse_stub(stub, "Demo") == ("Demo", "echo", "echo")


def test_measure_skips_dependent_tools_without_stubs(monkeypatch) -> None:
    bench = _load_bench()
    calls: list[str] = []

    def fake(client, target_url, name, arguments):
        calls.append(name)
        assert name == "listToolFiles"
        return "No servers connected."

    monkeypatch.setattr(bench, "_tool_call_text", fake)

    rows = bench.measure_code_mode_overhead(
        "http://127.0.0.1:9", iterations=2, warmup=0
    )

    assert [row.tool for row in rows] == [
        "listToolFiles",
        "readToolFile",
        "getToolDocs",
        "executeTool",
        "callManyTool",
    ]
    assert rows[0].status == "ok"
    assert rows[0].iterations == 2
    assert calls == ["listToolFiles"] * 3  # one listing probe + two measured calls
    assert all(row.status == "skipped" for row in rows[1:])
    assert {row.reason for row in rows[1:]} == {"no server stubs on the target gateway"}


def test_measure_exercises_all_five_tools_with_a_stub(monkeypatch) -> None:
    bench = _load_bench()
    listing = "servers/\n  Demo.pyi  # demo server"
    stub = (
        "# servers/Demo.pyi\n"
        "# Usage: Demo.echo(param=value)\n"
        'def echo(text: str = "hi") -> str: ...\n'
    )
    seen: list[tuple[str, dict]] = []

    def fake(client, target_url, name, arguments):
        seen.append((name, arguments))
        if name == "listToolFiles":
            return listing
        if name == "readToolFile":
            return stub
        return '{"result": "ok"}'

    monkeypatch.setattr(bench, "_tool_call_text", fake)

    rows = bench.measure_code_mode_overhead(
        "http://127.0.0.1:9", iterations=3, warmup=1
    )

    assert [row.tool for row in rows] == [
        "listToolFiles",
        "readToolFile",
        "getToolDocs",
        "executeTool",
        "callManyTool",
    ]
    assert all(row.status == "ok" for row in rows)
    assert all(row.iterations == 3 for row in rows)
    assert ("getToolDocs", {"server": "Demo", "tool": "echo"}) in seen
    assert ("executeTool", {"code": "Demo.echo()"}) in seen
    call_many = next(args for name, args in seen if name == "callManyTool")
    assert len(call_many["calls"]) == 2


def test_measure_reports_error_when_listing_fails(monkeypatch) -> None:
    bench = _load_bench()

    def fake(client, target_url, name, arguments):
        raise RuntimeError("gateway down")

    monkeypatch.setattr(bench, "_tool_call_text", fake)

    rows = bench.measure_code_mode_overhead(
        "http://127.0.0.1:9", iterations=2, warmup=0
    )

    assert len(rows) == 1
    assert rows[0].tool == "listToolFiles"
    assert rows[0].status == "error"
    assert "gateway down" in rows[0].reason


def test_partial_measurement_keeps_only_real_latencies(monkeypatch) -> None:
    bench = _load_bench()
    state = {"n": 0}

    def flaky(client, target_url, name, arguments):
        state["n"] += 1
        if state["n"] % 2:
            raise RuntimeError("transient")
        return "{}"

    monkeypatch.setattr(bench, "_tool_call_text", flaky)
    row = bench._measure_rpc(None, "", "listToolFiles", {}, iterations=4, warmup=0)

    assert row.status == "partial"
    assert row.errors == 2
    assert row.iterations == 2
    assert row.p50_ms > 0


def test_report_serialization_includes_status_and_iterations(tmp_path) -> None:
    bench = _load_bench()
    report = bench.BenchmarkReport(timestamp="2026-11-03T00-00-00", target_url="x")
    report.code_mode = [
        bench.CodeModeResult(
            tool="executeTool",
            status="skipped",
            reason="no callable tool",
            iterations=0,
        )
    ]
    report.summary = {"code_mode_measured": 0, "code_mode_skipped": 1}

    json_path, md_path = bench.save_report(report, str(tmp_path), "perf")

    payload = (tmp_path / Path(json_path).name).read_text()
    markdown = (tmp_path / Path(md_path).name).read_text()
    assert '"status": "skipped"' in payload
    assert '"iterations": 0' in payload
    assert "| executeTool | skipped | 0 |" in markdown
    assert "no callable tool" in markdown


if __name__ == "__main__":
    pytest.main([__file__])
