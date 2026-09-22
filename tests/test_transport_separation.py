"""Contract tests for transport separation (SPEC-TRANSPORT-SEPARATION-001).

REQ-TRANSPORT-001..004 and 008: ``Gateway`` accepts only ``http``|``sse``,
each transport exposes a mutually-exclusive ``/mcp`` surface with no cross
fallback, and the selected transport is published on ``app.state``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from starlette.routing import Route
from starlette.testclient import TestClient

from mcp_gway.gateway import Gateway
from mcp_gway.registry import Registry

_PING = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}


def _gw(tmp_path: Path, transport: str = "http") -> Gateway:
    """Build a Gateway over a minimal (empty) registry for one transport."""
    return Gateway(Registry(servers_dir=tmp_path / "srv"), transport=transport)


def _mcp_surface(gw: Gateway) -> set[tuple[str, str]]:
    """(path, method) pairs bound to the ``/mcp*`` routes of an app."""
    return {
        (route.path, method)
        for route in gw.app.routes
        if isinstance(route, Route)
        for method in route.methods or set()
        if route.path.startswith("/mcp")
    }


def test_unknown_transport_rejected(tmp_path: Path) -> None:
    """REQ-TRANSPORT-001: only ``http``|``sse`` accepted; else ValueError.

    Rejects ``stdio`` too — it is a valid ``serve`` transport but never a
    Gateway transport, so construction must fail before any side effect.
    """
    reg = Registry(servers_dir=tmp_path / "srv")
    for bad in ("stdio", "bogus", "HTTP", ""):
        with pytest.raises(ValueError, match="unknown transport"):
            Gateway(reg, transport=bad)


def test_http_routes_and_post_works(tmp_path: Path) -> None:
    """REQ-TRANSPORT-002: ``transport="http"`` serves JSON-RPC via POST /mcp."""
    gw = _gw(tmp_path, transport="http")
    c = TestClient(gw.app)
    r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 200
    data = r.json()
    assert "result" in data
    names = [tool["name"] for tool in data["result"]["tools"]]
    assert "listToolFiles" in names


def test_http_get_not_allowed(tmp_path: Path) -> None:
    """REQ-TRANSPORT-002: ``transport="http"`` gates GET /mcp to 405 + Allow: POST."""
    gw = _gw(tmp_path, transport="http")
    c = TestClient(gw.app)
    r = c.get("/mcp")
    assert r.status_code == 405
    assert r.headers["allow"] == "POST"
    assert "detail" in r.json()


def test_http_messages_404(tmp_path: Path) -> None:
    """REQ-TRANSPORT-002: ``transport="http"`` exposes no /mcp/messages (404)."""
    gw = _gw(tmp_path, transport="http")
    c = TestClient(gw.app)
    r = c.post("/mcp/messages", json=_PING)
    assert r.status_code == 404


def test_sse_routes_and_messages_works(tmp_path: Path) -> None:
    """REQ-TRANSPORT-003: ``transport="sse"`` serves JSON-RPC via POST /mcp/messages."""
    gw = _gw(tmp_path, transport="sse")
    c = TestClient(gw.app)
    r = c.post("/mcp/messages", json=_PING)
    assert r.status_code == 200
    assert r.json()["result"] == {}


def test_sse_post_not_allowed(tmp_path: Path) -> None:
    """REQ-TRANSPORT-003: ``transport="sse"`` gates POST /mcp to 405 + Allow: GET."""
    gw = _gw(tmp_path, transport="sse")
    c = TestClient(gw.app)
    r = c.post("/mcp", json=_PING)
    assert r.status_code == 405
    assert r.headers["allow"] == "GET"


def test_sse_stream_route(tmp_path: Path) -> None:
    """REQ-TRANSPORT-003: ``transport="sse"`` binds GET /mcp to the SSE stream.

    Asserted against the route table instead of consuming the stream so the
    test can never hang on an open event stream.
    """
    gw = _gw(tmp_path, transport="sse")
    stream_routes = [
        route
        for route in gw.app.routes
        if isinstance(route, Route)
        and route.path == "/mcp"
        and "GET" in (route.methods or set())
    ]
    assert len(stream_routes) == 1
    assert stream_routes[0].endpoint.__name__ == "_mcp_sse"


def test_no_cross_transport_fallback(tmp_path: Path) -> None:
    """REQ-TRANSPORT-004: http and sse surfaces are mutually exclusive.

    Neither transport answers the other's request: /mcp/messages exists only
    on sse, and each un-served /mcp method returns 405 rather than falling
    back across transports.
    """
    http_gw = _gw(tmp_path, transport="http")
    sse_gw = _gw(tmp_path, transport="sse")

    http_surface = _mcp_surface(http_gw)
    sse_surface = _mcp_surface(sse_gw)
    assert ("/mcp/messages", "POST") in sse_surface
    assert all(path != "/mcp/messages" for path, _ in http_surface)

    http_c = TestClient(http_gw.app)
    sse_c = TestClient(sse_gw.app)
    r = http_c.get("/mcp")
    assert (r.status_code, r.headers["allow"]) == (405, "POST")
    r = sse_c.post("/mcp", json=_PING)
    assert (r.status_code, r.headers["allow"]) == (405, "GET")
    assert http_c.post("/mcp/messages", json=_PING).status_code == 404
    assert sse_c.post("/mcp/messages", json=_PING).status_code == 200


def test_app_state_transport(tmp_path: Path) -> None:
    """REQ-TRANSPORT-008: ``app.state.transport`` exposes the selected transport."""
    assert _gw(tmp_path, transport="http").app.state.transport == "http"
    assert _gw(tmp_path, transport="sse").app.state.transport == "sse"
