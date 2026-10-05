from __future__ import annotations

from mcp_gway.observability.tracing import (
    Tracer,
    format_traceparent,
    get_tracer,
    parse_traceparent,
    set_tracer,
)


def test_traceparent_roundtrip() -> None:
    trace_id = "a" * 32
    span_id = "b" * 16
    header = format_traceparent(trace_id, span_id)
    assert parse_traceparent(header) == (trace_id, span_id)


def test_traceparent_rejects_garbage() -> None:
    assert parse_traceparent(None) == (None, None)
    assert parse_traceparent("bogus") == (None, None)
    assert parse_traceparent("00-" + "0" * 32 + "-" + "1" * 16 + "-01") == (
        None,
        None,
    )


def test_nested_spans_share_trace() -> None:
    tracer = Tracer()
    with tracer.span("outer", kind="server") as outer:
        with tracer.span("tool x.y", kind="client") as inner:
            assert inner.trace_id == outer.trace_id
            assert inner.parent_id == outer.span_id
    spans = tracer.recent_spans(10)
    assert [s["name"] for s in spans] == ["tool x.y", "outer"]
    assert spans[0]["parent_id"] == spans[1]["span_id"]


def test_span_failure_marks_error() -> None:
    tracer = Tracer()
    try:
        with tracer.span("boom"):
            raise ValueError("nope")
    except ValueError:
        pass
    (span,) = tracer.recent_spans(10)
    assert span["status"] == "error"
    assert "ValueError" in (span["error"] or "")


def test_json_logs_carry_trace_ids(caplog: object) -> None:
    import json
    import logging

    from mcp_gway.observability.logging import JSONFormatter

    tracer = Tracer()
    previous = get_tracer()
    set_tracer(tracer)
    try:
        handler_logger = logging.getLogger("mcp_gway.test-tracing")
        handler_logger.handlers.clear()
        handler_logger.propagate = False
        import io

        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JSONFormatter())
        handler_logger.addHandler(handler)
        handler_logger.setLevel(logging.INFO)
        with tracer.span("logged-op"):
            handler_logger.info("hello")
        payload = json.loads(stream.getvalue().strip().splitlines()[-1])
        assert payload["trace_id"]
        assert payload["span_id"]
    finally:
        set_tracer(previous)


def test_http_request_emits_span() -> None:
    from starlette.testclient import TestClient

    from mcp_gway.gateway import Gateway
    from mcp_gway.registry import Registry

    tracer = Tracer()
    previous = get_tracer()
    set_tracer(tracer)
    try:
        gateway = Gateway(
            Registry(servers_dir=".tmp-tracing-servers"), host="127.0.0.1"
        )
        client = TestClient(gateway.app)
        response = client.get("/health")
        assert response.status_code == 200
        assert "traceparent" in response.headers
        spans = tracer.recent_spans(10)
        assert spans, "expected the HTTP span to be recorded"
        assert spans[-1]["name"] == "GET /health"
        assert spans[-1]["kind"] == "server"
    finally:
        set_tracer(previous)


def test_sandbox_execute_emits_span() -> None:
    tracer = Tracer()
    previous = get_tracer()
    set_tracer(tracer)
    try:
        from mcp_gway.sandbox import StarlarkSandbox

        sandbox = StarlarkSandbox()
        assert sandbox.execute("result = 1 + 1") == 2
        spans = tracer.recent_spans(10)
        assert spans and spans[-1]["name"] == "sandbox.execute"
    finally:
        set_tracer(previous)
